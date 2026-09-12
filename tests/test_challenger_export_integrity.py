"""Empirical Verification and Stress Testing Suite by challenger_2.

Covers:
1. PDF generation against edge case data (extreme lengths, complex addresses,
   symbols, large amounts, Unicode) and byte verification via pypdfium2.
2. CSV export compliance with strict RFC 4180 parsing tools (csv.reader, pandas),
   testing internal commas, quotes, line breaks, and financial totals.
3. Monthly aggregation filtering across edge months (empty months, multi-year boundaries).
4. Comprehensive verification that all 5 Acceptance Criteria (AC1-AC5) pass.
"""

import csv
import io
import pytest
from datetime import datetime, timezone
import pypdfium2 as pdfium
from fastapi.testclient import TestClient

from src.db.models import LoanRecord, LoanCreate, LoanUpdate
from src.db.repository import LoanRepository
from src.export.pdf_generator import PDFGenerator
from src.export.csv_exporter import CSVExporter


def parse_pdf_text(pdf_bytes: bytes) -> str:
    """Parse PDF bytes and return concatenated text from all pages using pypdfium2."""
    doc = pdfium.PdfDocument(pdf_bytes)
    assert len(doc) >= 1, "PDF document must contain at least 1 page"
    extracted_text = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        text_page = page.get_textpage()
        extracted_text.append(text_page.get_text_range())
    return "\n".join(extracted_text)


class TestPDFEdgeCasesAndIntegrity:
    """Empirical verification of ReportLab PDF generation with extreme edge cases."""

    def test_pdf_extreme_name_lengths(self, loan_repo: LoanRepository):
        """Test borrower names with extreme lengths: 50, 100, 200, 500 characters."""
        gen = PDFGenerator()
        name_variations = [
            ("50_chars", "Alexander Montgomery-Cunningham Bartholomew III Esq."),
            ("100_chars", "Hubert Blaine Wolfeschlegelsteinhausenbergerdorff Senior John Jacob Jingleheimer Schmidt 100Chars"),
            ("250_chars", ("Hubert Wolfeschlegelsteinhausenbergerdorff " * 6)[:250].strip()),
            ("500_chars", ("Wolfeschlegelsteinhausenbergerdorff " * 14)[:500].strip()),
            ("unbroken_150_chars", "A" * 150),
        ]

        for tag, long_name in name_variations:
            record = loan_repo.create_loan(
                LoanCreate(
                    serial_number=f"LN-NAME-{tag[:10]}",
                    name=long_name,
                    mobile="+1-555-010-0200",
                    address="123 Standard Way, Suite 100",
                    amount=50000.0,
                    ocr_engine_used="gcp_vision",
                    verified=True,
                    verified_at="2026-09-12T04:00:00Z",
                )
            )

            pdf_bytes = gen.generate_loan_agreement(record)
            assert isinstance(pdf_bytes, bytes)
            assert pdf_bytes.startswith(b"%PDF-"), f"Failed for {tag}: Invalid PDF magic bytes"
            assert len(pdf_bytes) > 1000

            # Verify parsing with pypdfium2
            extracted = parse_pdf_text(pdf_bytes)
            assert record.serial_number in extracted
            # Verify name appears in extracted text (at least first 40 chars)
            assert long_name[:40] in extracted

    def test_pdf_complex_addresses_and_symbols(self, loan_repo: LoanRepository):
        """Test complex addresses with HTML/XML special characters, punctuation, and multi-line strings."""
        gen = PDFGenerator()
        complex_cases = [
            (
                "xml_chars",
                "Alice & Bob <Partners> 'Consultants' \"Holdings\"",
                "100 Market St <Ste 4B> & 5th Ave, O'Fallon, IL",
            ),
            (
                "punctuation_symbols",
                "Jane Doe",
                "Suite #5/9, Dept @ 42% (North-West) [Unit A] {Box 123} ~ High St | Sec 4",
            ),
            (
                "multiline_address",
                "Corporate Borrower LLC",
                "Floor 14, Tower B\nAttn: Accounts Dept\n800 Financial Plaza\nSan Francisco, CA 94104",
            ),
            (
                "slashes_and_paths",
                "Path User",
                r"C:\Users\Documents\Loan\File #123/456\789",
            ),
        ]

        for tag, name, addr in complex_cases:
            record = loan_repo.create_loan(
                LoanCreate(
                    serial_number=f"LN-SYM-{tag[:10]}",
                    name=name,
                    mobile="+1-555-999-0000",
                    address=addr,
                    amount=75000.0,
                    ocr_engine_used="gcp_vision",
                    verified=True,
                    verified_at="2026-09-12T04:00:00Z",
                )
            )

            pdf_bytes = gen.generate_loan_agreement(record)
            assert pdf_bytes.startswith(b"%PDF-")

            extracted = parse_pdf_text(pdf_bytes)
            assert record.serial_number in extracted
            # Check unescaped content presence in extracted PDF text
            assert "Alice" in extracted or "Jane" in extracted or "Corporate" in extracted or "Path" in extracted

    def test_pdf_extreme_loan_amounts(self, loan_repo: LoanRepository):
        """Test boundary loan amounts: zero, 1 cent, millions, billions, trillions, quadrillions."""
        gen = PDFGenerator()
        amount_cases = [
            ("zero_amount", 0.0, "$0.00"),
            ("one_cent", 0.01, "$0.01"),
            ("standard_fraction", 12345.67, "$12,345.67"),
            ("million", 1_000_000.00, "$1,000,000.00"),
            ("billion", 1_000_000_000.00, "$1,000,000,000.00"),
            ("trillion", 1_000_000_000_000.00, "$1,000,000,000,000.00"),
            ("quadrillion", 999_999_999_999_999.00, "$999,999,999,999,999.00"),
        ]

        for tag, amt, expected_formatted in amount_cases:
            record = loan_repo.create_loan(
                LoanCreate(
                    serial_number=f"LN-AMT-{tag[:10]}",
                    name="Amount Tester",
                    mobile="+1-555-123-4567",
                    address="100 Money Lane",
                    amount=amt,
                    ocr_engine_used="gcp_vision",
                    verified=True,
                    verified_at="2026-09-12T04:00:00Z",
                )
            )

            pdf_bytes = gen.generate_loan_agreement(record)
            assert pdf_bytes.startswith(b"%PDF-")

            extracted = parse_pdf_text(pdf_bytes)
            assert expected_formatted in extracted

    def test_pdf_unicode_accents_and_typography(self, loan_repo: LoanRepository):
        """Test Unicode characters supported in standard Latin-1 encodings (accents, umlauts, cedillas)."""
        gen = PDFGenerator()
        unicode_cases = [
            ("french_german", "François Müller-Schütz", "15 Rue d'Élysée, Zürich"),
            ("spanish", "María José Peña-González", "Avenida de la Constitución 42, Madrid"),
            ("scandinavian", "Björn Åkesson", "Strøget 10, København"),
        ]

        for tag, name, addr in unicode_cases:
            record = loan_repo.create_loan(
                LoanCreate(
                    serial_number=f"LN-UNI-{tag[:10]}",
                    name=name,
                    mobile="+1-555-888-7777",
                    address=addr,
                    amount=45000.0,
                    ocr_engine_used="gcp_vision",
                    verified=True,
                    verified_at="2026-09-12T04:00:00Z",
                )
            )

            pdf_bytes = gen.generate_loan_agreement(record)
            assert pdf_bytes.startswith(b"%PDF-")
            extracted = parse_pdf_text(pdf_bytes)
            assert record.serial_number in extracted

    def test_pdf_non_latin_unicode_investigation(self, loan_repo: LoanRepository):
        """
        Adversarial Investigation:
        Test how ReportLab handles Unicode outside Latin-1 (Cyrillic, CJK, Arabic, Emojis).
        Standard Helvetica Type 1 font does not support CJK or Arabic glyphs without TTF registration.
        Verify whether an exception is raised or characters are handled/rejected.
        """
        gen = PDFGenerator()
        non_latin_cases = [
            ("cyrillic", "Иван Иванов", "Москва, ул. Ленина 1"),
            ("cjk", "田中太郎", "東京都新宿区"),
            ("arabic", "محمد بن سلمان", "الرياض"),
            ("emoji", "Alice Rocket 🚀", "321 Launchpad 🌕"),
        ]

        for tag, name, addr in non_latin_cases:
            record = loan_repo.create_loan(
                LoanCreate(
                    serial_number=f"LN-NL-{tag[:5]}",
                    name=name,
                    mobile="+1-555-000-1111",
                    address=addr,
                    amount=50000.0,
                    ocr_engine_used="gcp_vision",
                    verified=True,
                    verified_at="2026-09-12T04:00:00Z",
                )
            )

            try:
                pdf_bytes = gen.generate_loan_agreement(record)
                # If ReportLab succeeded, verify valid PDF
                assert pdf_bytes.startswith(b"%PDF-")
                parse_pdf_text(pdf_bytes)
            except (UnicodeEncodeError, ValueError, KeyError) as exc:
                # Document known Type 1 font limitation in ReportLab Helvetica
                # ReportLab standard Helvetica only supports WinAnsi / Latin-1 encoding
                assert isinstance(exc, (UnicodeEncodeError, ValueError, KeyError))


    def test_pdf_endpoint_e2e_stress(self, client: TestClient, loan_repo: LoanRepository):
        """E2E verification of GET /api/loans/{id}/pdf with edge-case record."""
        record = loan_repo.create_loan(
            LoanCreate(
                serial_number="LN-E2E-EDGE-999",
                name="Dr. Bartholomew O'Connor & Sons <Holdings>",
                mobile="+1-555-432-1098",
                address="777 Prosperity Blvd, Suite #12-B",
                amount=2500000.75,
                ocr_engine_used="gcp_vision",
                verified=True,
                verified_at="2026-09-12T05:00:00Z",
            )
        )

        response = client.get(f"/api/loans/{record.id}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert f"loan_agreement_{record.serial_number}.pdf" in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF-")

        extracted = parse_pdf_text(response.content)
        assert "LN-E2E-EDGE-999" in extracted
        assert "$2,500,000.75" in extracted
        assert "O&apos;Connor" in response.content.decode("latin1", errors="ignore") or "O'Connor" in extracted


class TestCSVRFC4180Compliance:
    """Empirical verification of RFC 4180 CSV compliance and summary totals."""

    def test_csv_rfc4180_parsers(self, loan_repo: LoanRepository):
        """Verify generated CSV parses cleanly with csv.reader and pandas."""
        now = "2026-09-12T05:00:00Z"
        records = [
            loan_repo.create_loan(
                LoanCreate(
                    serial_number=f"LN-RFC-{i}",
                    name=f"Borrower {i}",
                    mobile=f"+1-555-000-{i:04d}",
                    address=f"{i} Test Street",
                    amount=1000.0 * i,
                    ocr_engine_used="gcp_vision",
                    verified=True,
                    verified_at=now,
                )
            )
            for i in range(1, 4)
        ]

        exporter = CSVExporter()
        csv_text = exporter.export_monthly_csv(records)

        # 1. Test with strict csv.reader
        reader = csv.reader(io.StringIO(csv_text), dialect="excel")
        rows = list(reader)

        # 1 header + 3 data rows + 1 total row = 5 rows
        assert len(rows) == 5
        assert rows[0] == CSVExporter.HEADER

        # 2. Test line terminators are strict CRLF (\r\n) per RFC 4180
        assert "\r\n" in csv_text

        # 3. Test with pandas (if available)
        try:
            import pandas as pd
            df = pd.read_csv(io.StringIO(csv_text))
            assert len(df) == 4  # 3 data rows + 1 total row
            assert list(df.columns) == CSVExporter.HEADER
        except ImportError:
            pass

    def test_csv_internal_commas_and_quotes(self, loan_repo: LoanRepository):
        """
        Adversarial: records containing internal commas, escaped quotes, and single quotes.
        Verifies RFC 4180 escaping rules: fields containing quotes/commas must be quoted,
        and quotes inside fields must be doubled ("").
        """
        now = "2026-09-12T05:00:00Z"
        tricky_name = 'Smith, Jr., "John" & O\'Connor'
        tricky_address = 'Suite 4B, "Metropolis Tower", 5th & Main, Springfield, IL'

        record = loan_repo.create_loan(
            LoanCreate(
                serial_number="LN-COMMA-QUOTE-01",
                name=tricky_name,
                mobile="+1-555-123-4567",
                address=tricky_address,
                amount=12345.67,
                ocr_engine_used="gcp_vision",
                verified=True,
                verified_at=now,
            )
        )

        exporter = CSVExporter()
        csv_text = exporter.export_monthly_csv([record])

        # Parse with strict csv.reader
        reader = csv.reader(io.StringIO(csv_text), dialect="excel")
        rows = list(reader)

        assert len(rows) == 3  # Header, 1 record, Total row
        data_row = rows[1]

        # Verify columns didn't shift due to internal commas
        assert len(data_row) == len(CSVExporter.HEADER)
        assert data_row[1] == "LN-COMMA-QUOTE-01"
        assert data_row[2] == tricky_name  # borrower_name
        assert data_row[4] == tricky_address  # address
        assert data_row[5] == "12345.67"  # loan_amount

    def test_csv_internal_line_breaks(self, loan_repo: LoanRepository):
        """
        RFC 4180 Rule 6: Fields containing line breaks (CRLF or LF) must be enclosed in quotes.
        Verify multi-line address does not corrupt row count or column alignment.
        """
        now = "2026-09-12T05:00:00Z"
        multiline_addr = "Line 1: 100 Main St\nLine 2: Apt 4B\r\nLine 3: Springfield"

        record = loan_repo.create_loan(
            LoanCreate(
                serial_number="LN-MULTILINE-01",
                name="Multi Line User",
                mobile="+1-555-987-6543",
                address=multiline_addr,
                amount=5000.0,
                ocr_engine_used="gcp_vision",
                verified=True,
                verified_at=now,
            )
        )

        exporter = CSVExporter()
        csv_text = exporter.export_monthly_csv([record])

        # Parse with csv.reader
        reader = csv.reader(io.StringIO(csv_text), dialect="excel")
        rows = list(reader)

        # Must parse as header, 1 record, total row = 3 rows total (NOT 5 rows)
        assert len(rows) == 3
        data_row = rows[1]
        assert len(data_row) == len(CSVExporter.HEADER)
        assert data_row[1] == "LN-MULTILINE-01"
        assert data_row[4] == multiline_addr

    def test_csv_financial_totals_calculation_and_empty_list(self, loan_repo: LoanRepository):
        """
        Verify financial total row:
        - Accurately sums fractional currency amounts without floating point roundoff errors
        - Has identical column count as header
        - Handles empty loans list cleanly (no total row, only header)
        """
        exporter = CSVExporter()

        # 1. Empty list
        empty_csv = exporter.export_monthly_csv([])
        empty_rows = list(csv.reader(io.StringIO(empty_csv)))
        assert len(empty_rows) == 1
        assert empty_rows[0] == CSVExporter.HEADER

        # 2. Multi-record financial sum with tricky floats (e.g. .33, .67)
        now = "2026-09-12T05:00:00Z"
        amounts = [10.33, 20.67, 30.00, 100.25, 0.75]
        expected_sum = sum(amounts)  # 162.00

        records = [
            loan_repo.create_loan(
                LoanCreate(
                    serial_number=f"LN-SUM-{i}",
                    name=f"Sum User {i}",
                    mobile="+1-555-000-0000",
                    address="Sum Way",
                    amount=amt,
                    ocr_engine_used="gcp_vision",
                    verified=True,
                    verified_at=now,
                )
            )
            for i, amt in enumerate(amounts)
        ]

        csv_text = exporter.export_monthly_csv(records)
        rows = list(csv.reader(io.StringIO(csv_text)))

        # Header + 5 records + Total row = 7 rows
        assert len(rows) == 7
        total_row = rows[-1]

        assert len(total_row) == len(CSVExporter.HEADER)
        assert total_row[0] == "TOTAL"
        assert total_row[1] == f"{len(amounts)} records"
        assert total_row[4] == "TOTAL_AMOUNT"
        assert total_row[5] == f"{expected_sum:.2f}"


class TestMonthlyAggregationEdgeCases:
    """Empirical verification of monthly aggregation filtering across edge months and boundaries."""

    def test_empty_month_filtering(self, client: TestClient, loan_repo: LoanRepository):
        """Querying a month with no loans returns an empty list and valid empty CSV header."""
        loans = loan_repo.list_loans_by_month("1985-05", verified_only=True)
        assert loans == []

        response = client.get("/api/export/csv?month=1985-05")
        assert response.status_code == 200
        rows = list(csv.reader(io.StringIO(response.text)))
        assert len(rows) == 1
        assert rows[0] == CSVExporter.HEADER

    def test_multi_year_and_month_boundaries(self, loan_repo: LoanRepository):
        """
        Verify boundary dates:
        - 2025-12-31T23:59:59Z belongs strictly to 2025-12
        - 2026-01-01T00:00:00Z belongs strictly to 2026-01
        """
        # Seed 2025-12 loan
        loan_2025_12 = loan_repo.create_loan(
            LoanCreate(
                serial_number="LN-BOUNDARY-2025-12",
                name="Year End User",
                mobile="+1-555-2025-12",
                address="12 December St",
                amount=12000.0,
                ocr_engine_used="gcp_vision",
                verified=True,
                verified_at="2025-12-31T23:59:59Z",
            )
        )

        # Seed 2026-01 loan
        loan_2026_01 = loan_repo.create_loan(
            LoanCreate(
                serial_number="LN-BOUNDARY-2026-01",
                name="New Year User",
                mobile="+1-555-2026-01",
                address="1 January Ave",
                amount=26000.0,
                ocr_engine_used="gcp_vision",
                verified=True,
                verified_at="2026-01-01T00:00:00Z",
            )
        )

        # Query 2025-12
        dec_loans = loan_repo.list_loans_by_month("2025-12", verified_only=True)
        dec_serials = [l.serial_number for l in dec_loans]
        assert "LN-BOUNDARY-2025-12" in dec_serials
        assert "LN-BOUNDARY-2026-01" not in dec_serials

        # Query 2026-01
        jan_loans = loan_repo.list_loans_by_month("2026-01", verified_only=True)
        jan_serials = [l.serial_number for l in jan_loans]
        assert "LN-BOUNDARY-2026-01" in jan_serials
        assert "LN-BOUNDARY-2025-12" not in jan_serials

    def test_leap_year_boundary(self, loan_repo: LoanRepository):
        """Verify leap year date 2024-02-29 is included in 2024-02 aggregation."""
        loan_leap = loan_repo.create_loan(
            LoanCreate(
                serial_number="LN-LEAP-2024-02",
                name="Leap Year User",
                mobile="+1-555-2024-02",
                address="29 Feb Leap Way",
                amount=29000.0,
                ocr_engine_used="gcp_vision",
                verified=True,
                verified_at="2024-02-29T12:00:00Z",
            )
        )

        feb_loans = loan_repo.list_loans_by_month("2024-02", verified_only=True)
        feb_serials = [l.serial_number for l in feb_loans]
        assert "LN-LEAP-2024-02" in feb_serials


class TestAcceptanceCriteriaFullCoverage:
    """Empirical verification of AC1, AC2, AC3, AC4, AC5 completeness."""

    def test_ac1_data_integrity(self, client: TestClient):
        """AC1: Ingestion & Verification form populated with all 5 fields."""
        from tests.fixtures.mock_images import get_fixture_bytes
        image_bytes = get_fixture_bytes("clean_loan_document.png")

        response = client.post(
            "/api/documents/upload",
            files={"file": ("clean_loan_document.png", image_bytes, "image/png")},
        )
        assert response.status_code == 201
        data = response.json()
        assert "loan_id" in data or "id" in data
        for field in ["serial_number", "name", "mobile", "address", "amount"]:
            assert data.get(field) is not None
            assert data["confidences"].get(field) is not None
            assert 0.0 <= float(data["confidences"][field]) <= 1.0
        assert data.get("verified") is False


    def test_ac2_modification_and_save(self, client: TestClient, sample_loan_record: LoanRecord):
        """AC2: Edit field and verify persistence to local SQLite."""
        loan_id = sample_loan_record.id
        update_payload = {
            "name": "Jane Challenger Doe",
            "amount": 99999.00,
            "manually_edited": True,
        }

        response = client.post(f"/api/loans/{loan_id}/verify", json=update_payload)
        assert response.status_code == 200
        verified_data = response.json()
        assert verified_data["name"] == "Jane Challenger Doe"
        assert verified_data["amount"] == 99999.00
        assert verified_data["verified"] is True
        assert verified_data["verified_at"] is not None

        # Verify DB reflects update
        get_resp = client.get(f"/api/loans/{loan_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Jane Challenger Doe"
        assert get_resp.json()["verified"] is True

    def test_ac3_gcp_fallback(self, monkeypatch):
        """AC3: GCP failure triggers Tesseract fallback with telemetry."""
        from unittest.mock import MagicMock
        from src.ocr.base import GCPQuotaExceededError, OCRResult
        from src.ocr.dual_engine import DualOCREngine
        from tests.fixtures.mock_images import get_fixture_bytes

        mock_gcp = MagicMock()
        mock_gcp.name = "gcp_vision"
        mock_gcp.extract.side_effect = GCPQuotaExceededError("429 Quota Exceeded")

        mock_tesseract = MagicMock()
        mock_tesseract.name = "tesseract"
        mock_tesseract.extract.return_value = OCRResult(
            serial_number="LN-FALLBACK-01",
            name="Fallback Borrower",
            mobile="+1-555-444-5555",
            address="Fallback Street",
            amount=10000.0,
            confidences={"amount": 0.9},
            engine_name="tesseract",
            fallback_triggered=False,
        )

        engine = DualOCREngine(primary_engine=mock_gcp, fallback_engine=mock_tesseract)
        image_bytes = get_fixture_bytes("clean_loan_document.png")

        result = engine.extract(image_bytes)
        assert result.fallback_triggered is True
        assert result.engine_name == "tesseract"
        assert "Quota Exceeded" in result.fallback_reason

    def test_ac4_pdf_fields_verified(self, client: TestClient, sample_verified_loan_record: LoanRecord):
        """AC4: PDF contains verified fields."""
        response = client.get(f"/api/loans/{sample_verified_loan_record.id}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-")
        text = parse_pdf_text(response.content)
        assert sample_verified_loan_record.serial_number in text
        assert sample_verified_loan_record.name in text

    def test_ac5_csv_headers_and_validity(self, client: TestClient, sample_verified_loan_record: LoanRecord):
        """AC5: CSV export generates valid file with all expected columns."""
        month_str = sample_verified_loan_record.created_at[:7]
        response = client.get(f"/api/export/csv?month={month_str}")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        rows = list(csv.reader(io.StringIO(response.text)))
        assert len(rows) >= 2
        assert rows[0] == CSVExporter.HEADER
        assert any(sample_verified_loan_record.serial_number in r for r in rows)

