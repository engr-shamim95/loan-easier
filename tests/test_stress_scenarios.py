"""Empirical stress test suite for Loan Easier application.

Authored by challenger_1 to stress-test:
1. Concurrency: Rapid concurrent document uploads, verifications, and mixed workloads.
2. Dual OCR failover stress: High-load rapid switching between GCP Vision and Tesseract.
3. Corrupted and malformed image payloads: Truncated byte streams, spoofed headers, oversized files, and decompression bombs.
4. In-memory SQLite transaction race conditions: Empirical contention behavior in shared memory vs disk WAL.
"""

import io
import time
import pytest
import concurrent.futures
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from src.api.app import app
from src.config import MAX_UPLOAD_SIZE
from src.db.models import LoanCreate, LoanUpdate
from src.db.repository import LoanRepository
from src.ocr.base import (
    BaseOCREngine,
    OCRResult,
    GCPQuotaExceededError,
    GCPConnectionError,
    GCPAuthError,
    AllOCREnginesFailedError,
)
from src.ocr.dual_engine import DualOCREngine
from tests.fixtures.mock_images import get_fixture_bytes


class TestConcurrencyStress:
    """Stress test concurrent API endpoints and database operations."""

    def test_concurrent_document_uploads(self, client: TestClient):
        """Verify 25 rapid concurrent document uploads succeed with unique IDs and no data loss."""
        image_bytes = get_fixture_bytes("clean_loan_document.png")
        num_requests = 25

        def upload_worker(i: int):
            filename = f"concurrent_doc_{i:03d}.png"
            files = {"file": (filename, image_bytes, "image/png")}
            resp = client.post("/api/documents/upload", files=files)
            return resp.status_code, resp.json() if resp.status_code == 201 else resp.text

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(upload_worker, i) for i in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        status_codes = [r[0] for r in results]
        assert all(sc == 201 for sc in status_codes), f"Not all uploads succeeded: {status_codes}"

        loan_ids = [r[1]["id"] for r in results]
        assert len(set(loan_ids)) == num_requests, f"Duplicate loan IDs detected under concurrency: {loan_ids}"

    def test_concurrent_loan_verifications(self, client: TestClient):
        """Verify 25 rapid concurrent verifications against different loans."""
        # Pre-create 25 loans
        repo = LoanRepository()
        loan_ids = []
        for i in range(25):
            created = repo.create_loan(
                LoanCreate(
                    serial_number=f"LN-CONC-VERIFY-{i:03d}",
                    name=f"Borrower {i}",
                    mobile="+1-555-111-2222",
                    amount=1000.0 + i,
                    ocr_engine_used="gcp_vision",
                    verified=False,
                )
            )
            loan_ids.append(created.id)

        def verify_worker(lid: int):
            payload = {
                "name": f"Verified Borrower {lid}",
                "amount": 5000.0 + lid,
            }
            resp = client.post(f"/api/loans/{lid}/verify", json=payload)
            return resp.status_code, resp.json() if resp.status_code == 200 else resp.text

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(verify_worker, lid) for lid in loan_ids]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(r[0] == 200 for r in results), f"Verification failures under concurrency: {results}"

        # Verify all records are marked verified
        for lid in loan_ids:
            record = repo.get_loan_by_id(lid)
            assert record is not None
            assert record.verified is True
            assert record.verified_at is not None

    def test_concurrent_same_loan_verifications(self, client: TestClient):
        """Verify 20 concurrent update/verification requests targeting the exact SAME loan record."""
        repo = LoanRepository()
        target = repo.create_loan(
            LoanCreate(
                serial_number="LN-HOTSPOT-001",
                name="Hotspot Target",
                mobile="+1-555-999-0000",
                amount=2000.0,
                ocr_engine_used="gcp_vision",
                verified=False,
            )
        )

        def hotspot_worker(i: int):
            payload = {"amount": float(3000 + i), "name": f"Contender {i}"}
            resp = client.post(f"/api/loans/{target.id}/verify", json=payload)
            return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(hotspot_worker, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All concurrent writes to the same row should succeed via SQLite WAL serialized writes
        assert all(sc == 200 for sc in results), f"Hotspot update collision error: {results}"

        final = repo.get_loan_by_id(target.id)
        assert final.verified is True
        assert final.amount >= 3000.0

    def test_mixed_concurrent_workload(self, client: TestClient):
        """Verify mixed concurrent read/write operations (uploads, verifications, fetches, exports)."""
        image_bytes = get_fixture_bytes("clean_loan_document.png")
        repo = LoanRepository()

        # Seed initial loan for reads/exports
        seed = repo.create_loan(
            LoanCreate(
                serial_number="LN-SEED-MIXED",
                name="Seed Borrower",
                mobile="+1-555-333-4444",
                amount=7500.0,
                ocr_engine_used="gcp_vision",
                verified=True,
                verified_at="2026-09-12T00:00:00Z",
            )
        )

        operations = []

        def do_upload(i):
            resp = client.post(
                "/api/documents/upload",
                files={"file": (f"mixed_{i}.png", image_bytes, "image/png")},
            )
            return "upload", resp.status_code

        def do_get(i):
            resp = client.get(f"/api/loans/{seed.id}")
            return "get", resp.status_code

        def do_pdf(i):
            resp = client.get(f"/api/loans/{seed.id}/pdf")
            return "pdf", resp.status_code

        def do_csv(i):
            resp = client.get("/api/export/csv?month=2026-09")
            return "csv", resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            futures = []
            for i in range(8):
                futures.append(executor.submit(do_upload, i))
                futures.append(executor.submit(do_get, i))
                futures.append(executor.submit(do_pdf, i))
                futures.append(executor.submit(do_csv, i))

            for f in concurrent.futures.as_completed(futures):
                operations.append(f.result())

        for op_type, status in operations:
            expected = 201 if op_type == "upload" else 200
            assert status == expected, f"Operation {op_type} failed with status {status}"


class TestDualOCRFailoverStress:
    """Stress test failover and fallback telemetry under high concurrency."""

    def test_rapid_failover_switching_under_load(self):
        """
        Verify 60 concurrent requests rapidly alternating between GCP Vision success
        and various GCP failure modes (429 quota, connection timeout, 401 auth, forced fallback).
        Confirms complete thread isolation of telemetry and results.
        """
        class MockGCPDynamic(BaseOCREngine):
            def __init__(self):
                self._counter = 0

            @property
            def name(self) -> str:
                return "gcp_vision"

            def is_available(self) -> bool:
                return True

            def extract(self, image_bytes: bytes) -> OCRResult:
                self._counter += 1
                mode = self._counter % 4
                if mode == 1:
                    raise GCPQuotaExceededError("Rate limit exceeded (HTTP 429)")
                elif mode == 2:
                    raise GCPConnectionError("Socket connect timeout (503)")
                elif mode == 3:
                    raise GCPAuthError("Invalid credentials (HTTP 401)")
                else:
                    return OCRResult(
                        serial_number="LN-PRIMARY-OK",
                        name="Primary Success",
                        amount=15000.0,
                        engine_name="gcp_vision",
                        confidences={"amount": 0.98},
                    )

        class MockTesseract(BaseOCREngine):
            @property
            def name(self) -> str:
                return "tesseract"

            def is_available(self) -> bool:
                return True

            def extract(self, image_bytes: bytes) -> OCRResult:
                return OCRResult(
                    serial_number="LN-FALLBACK-OK",
                    name="Fallback Success",
                    amount=15000.0,
                    engine_name="tesseract",
                    confidences={"amount": 0.85},
                )

        dual_engine = DualOCREngine(
            primary_engine=MockGCPDynamic(),
            fallback_engine=MockTesseract(),
        )
        img_bytes = get_fixture_bytes("clean_loan_document.png")

        def worker(i: int):
            result = dual_engine.extract(img_bytes)
            return (
                i,
                result.engine_name,
                result.fallback_triggered,
                result.fallback_reason,
                result.serial_number,
            )

        num_tasks = 60
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(worker, i) for i in range(num_tasks)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == num_tasks

        for i, engine_name, fb_triggered, fb_reason, serial in results:
            if fb_triggered:
                assert engine_name == "tesseract"
                assert serial == "LN-FALLBACK-OK"
                assert fb_reason is not None
                assert any(kw in fb_reason for kw in ["429", "503", "401", "Rate limit", "timeout", "credentials"])
            else:
                assert engine_name == "gcp_vision"
                assert serial == "LN-PRIMARY-OK"
                assert fb_reason is None

    def test_cascading_dual_failure_under_load(self):
        """Verify that when both primary and fallback fail under high load, clean 502 is raised."""
        class DeadPrimary(BaseOCREngine):
            @property
            def name(self) -> str:
                return "dead_primary"
            def is_available(self) -> bool:
                return False
            def extract(self, image_bytes: bytes) -> OCRResult:
                raise GCPQuotaExceededError("Primary is completely dead")

        class DeadFallback(BaseOCREngine):
            @property
            def name(self) -> str:
                return "dead_fallback"
            def is_available(self) -> bool:
                return False
            def extract(self, image_bytes: bytes) -> OCRResult:
                raise RuntimeError("Fallback crashed")

        failing_dual_engine = DualOCREngine(
            primary_engine=DeadPrimary(),
            fallback_engine=DeadFallback(),
        )

        def failing_worker(i: int):
            try:
                failing_dual_engine.extract(b"dummy")
                return False, None
            except AllOCREnginesFailedError as e:
                return True, str(e)
            except Exception as e:
                return False, f"Unexpected error type: {type(e)}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(failing_worker, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(r[0] is True for r in results), f"Expected AllOCREnginesFailedError, got: {results}"


class TestCorruptedAndMalformedPayloads:
    """Stress test image decoder and upload endpoint against adversarial inputs."""

    @pytest.mark.parametrize(
        "cut_offset",
        [1, 4, 8, 16, 32, 64, 128, 256, 512],
    )
    def test_truncated_byte_streams(self, client: TestClient, cut_offset: int):
        """Verify upload endpoint cleanly rejects truncated image streams with HTTP 422."""
        full_bytes = get_fixture_bytes("clean_loan_document.png")
        truncated = full_bytes[:cut_offset]

        resp = client.post(
            "/api/documents/upload",
            files={"file": (f"truncated_{cut_offset}.png", truncated, "image/png")},
        )
        assert resp.status_code == 422, f"Expected 422 on truncated stream at {cut_offset}B, got {resp.status_code}"
        assert "integrity" in resp.text.lower() or "decode" in resp.text.lower()

    def test_spoofed_magic_headers(self, client: TestClient):
        """Verify fake magic byte headers followed by noise/zeros are rejected with HTTP 422."""
        headers = [
            ("png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 512, "image/png"),
            ("jpeg", b"\xff\xd8\xff\xe0" + b"\xff" * 512, "image/jpeg"),
            ("tiff", b"II*\x00" + b"\xaa" * 512, "image/tiff"),
            ("bmp", b"BM" + b"\x00" * 512, "image/bmp"),
            ("webp", b"RIFF\x00\x00\x00\x00WEBP" + b"\x55" * 512, "image/webp"),
        ]

        for fmt, fake_data, mime in headers:
            resp = client.post(
                "/api/documents/upload",
                files={"file": (f"fake_magic.{fmt}", fake_data, mime)},
            )
            assert resp.status_code == 422, f"Expected 422 for spoofed {fmt} header, got {resp.status_code}: {resp.text}"

    def test_oversized_payload_rejection(self, client: TestClient):
        """Verify payloads exceeding MAX_UPLOAD_SIZE (15MB) are rejected with HTTP 413."""
        oversized = b"P" * (16 * 1024 * 1024)  # 16 MB
        resp = client.post(
            "/api/documents/upload",
            files={"file": ("oversized.png", oversized, "image/png")},
        )
        assert resp.status_code == 413
        assert "maximum allowable size" in resp.text

    def test_decompression_bomb_dos_rejection(self, client: TestClient):
        """
        Verify decompression bomb DOS attack (huge pixel dimensions) is caught
        and rejected cleanly with HTTP 422 without unhandled server crashes.
        """
        # Create small-byte PNG with 14000x14000 pixels (196M pixels > PIL limit)
        img = Image.new("L", (14000, 14000), color=255)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        bomb_bytes = buf.getvalue()

        resp = client.post(
            "/api/documents/upload",
            files={"file": ("decompression_bomb.png", bomb_bytes, "image/png")},
        )
        assert resp.status_code == 422
        assert "decompression bomb" in resp.text.lower() or "limit" in resp.text.lower()


class TestInMemorySQLiteConcurrency:
    """Stress test in-memory SQLite and contrast with disk-backed SQLite concurrency."""

    def test_disk_wal_concurrency_robustness(self, tmp_path: Path):
        """Verify disk-based SQLite in WAL mode smoothly handles 30 concurrent writers."""
        disk_db = tmp_path / "robustness_wal.db"
        repo = LoanRepository(db_path=disk_db)

        def worker(i: int):
            created = repo.create_loan(
                LoanCreate(
                    serial_number=f"LN-DISK-{i:04d}",
                    name=f"Borrower {i}",
                    mobile="+1-555-444-5555",
                    amount=2500.0 + i,
                    ocr_engine_used="gcp_vision",
                )
            )
            # Immediately update and verify
            updated = repo.update_and_verify_loan(
                created.id,
                LoanUpdate(amount=created.amount + 50.0),
            )
            return updated.id

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(worker, i) for i in range(30)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 30
        assert len(set(results)) == 30
        all_loans = repo.list_loans(limit=100)
        assert len(all_loans) == 30

    def test_in_memory_sqlite_race_condition_behavior(self):
        """
        EMPIRICAL OBSERVATION & EVIDENCE:
        SQLite shared-cache in-memory databases ('file:loan_memdb?mode=memory&cache=shared')
        use table-level locking instead of database-level locking.
        Under concurrent multithreaded transactions, SQLite immediately raises
        'OperationalError: database table is locked' because busy_timeout does not
        apply to table locks in shared-cache mode.

        This test empirically verifies the behavior and confirms that database integrity
        is preserved even when transactions collide.
        """
        import sqlite3
        repo = LoanRepository(db_path=":memory:")

        def in_mem_worker(i: int):
            try:
                repo.create_loan(
                    LoanCreate(
                        serial_number=f"LN-MEM-{i:04d}",
                        name=f"Borrower {i}",
                        mobile="+1-555-666-7777",
                        amount=1000.0 + i,
                        ocr_engine_used="gcp_vision",
                    )
                )
                return True, None
            except sqlite3.OperationalError as e:
                return False, f"sqlite3.OperationalError: {e}"
            except Exception as e:
                return False, f"Unexpected: {type(e).__name__}: {e}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(in_mem_worker, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        success_count = sum(1 for r in results if r[0] is True)
        collision_count = sum(1 for r in results if r[0] is False)

        # Document and verify the empirical lock collision behavior
        # Under 20 concurrent threads, table-level locking causes collisions
        assert collision_count > 0, "Expected table lock collisions in SQLite in-memory shared cache"
        table_locked_errors = [r[1] for r in results if r[1] and "database table is locked" in r[1]]
        assert len(table_locked_errors) == collision_count, f"Errors other than table lock: {results}"

        # CRITICAL VERIFICATION: Confirm that despite transaction aborts,
        # the in-memory database did not suffer corruption
        conn = repo._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            integrity = cursor.fetchall()
            cursor.close()
            assert integrity[0][0] == "ok", f"Integrity check failed: {integrity}"
        finally:
            repo._close_conn(conn)
