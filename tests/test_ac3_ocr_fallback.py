"""Tests for Acceptance Criteria 3 (AC3): Dual OCR Fallback Mechanism.

AC3: Trigger the fallback mechanism (mocking GCP failure e.g. quota limit,
connection error, or OCR_FORCE_FALLBACK=true), and verify Tesseract OCR is
invoked and recorded in telemetry.
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.ocr.base import (
    GCPQuotaExceededError,
    GCPConnectionError,
    GCPAuthError,
    AllOCREnginesFailedError,
    OCRResult,
)
from src.ocr.dual_engine import DualOCREngine
from tests.fixtures.mock_images import get_fixture_bytes

class TestAC3OCRFallback:
    """Test suite verifying GCP failure detection, automatic failover, and telemetry."""

    def test_gcp_quota_exceeded_triggers_tesseract_fallback(self):
        """
        AC3 Primary Unit Test:
        Mock primary GCP engine raising GCPQuotaExceededError (HTTP 429).
        Verify DualOCREngine catches it, invokes Tesseract, and records telemetry.
        """
        image_bytes = get_fixture_bytes("clean_loan_document.png")

        # Mock primary engine that raises GCPQuotaExceededError
        mock_gcp = MagicMock()
        mock_gcp.name = "gcp_vision"
        mock_gcp.extract.side_effect = GCPQuotaExceededError(
            "Google Cloud Vision API quota limit exceeded (HTTP 429 ResourceExhausted)"
        )

        # Mock fallback engine that succeeds
        mock_tesseract = MagicMock()
        mock_tesseract.name = "tesseract"
        mock_tesseract.extract.return_value = OCRResult(
            serial_number="LN-2026-9042",
            name="Jane Doe",
            mobile="+1-555-234-5678",
            address="742 Evergreen Terrace, Springfield, IL 62704",
            amount=25000.0,
            confidences={"serial_number": 0.90, "name": 0.88, "amount": 0.90},
            raw_text="Sample text",
            engine_name="tesseract",
            fallback_triggered=False,
        )

        dual_engine = DualOCREngine(primary_engine=mock_gcp, fallback_engine=mock_tesseract)
        result = dual_engine.extract(image_bytes)

        # Assert fallback was triggered and recorded in telemetry
        assert result.fallback_triggered is True
        assert result.engine_name == "tesseract"
        assert "quota" in result.fallback_reason.lower() or "429" in result.fallback_reason
        assert mock_gcp.extract.called
        assert mock_tesseract.extract.called

    def test_gcp_connection_error_triggers_tesseract_fallback(self):
        """Verify network/connection failure in GCP triggers Tesseract fallback."""
        image_bytes = get_fixture_bytes("clean_loan_document.png")

        mock_gcp = MagicMock()
        mock_gcp.name = "gcp_vision"
        mock_gcp.extract.side_effect = GCPConnectionError("Connection timeout to vision.googleapis.com:443")

        mock_tesseract = MagicMock()
        mock_tesseract.name = "tesseract"
        mock_tesseract.extract.return_value = OCRResult(
            serial_number="LN-2026-9042",
            name="Jane Doe",
            mobile="+1-555-234-5678",
            address="742 Evergreen Terrace",
            amount=25000.0,
            confidences={"serial_number": 0.90},
            engine_name="tesseract",
        )

        dual_engine = DualOCREngine(primary_engine=mock_gcp, fallback_engine=mock_tesseract)
        result = dual_engine.extract(image_bytes)

        assert result.fallback_triggered is True
        assert result.engine_name == "tesseract"
        assert "connection" in result.fallback_reason.lower() or "timeout" in result.fallback_reason.lower()

    def test_gcp_auth_error_triggers_tesseract_fallback(self):
        """Verify credential/auth error in GCP triggers Tesseract fallback."""
        image_bytes = get_fixture_bytes("clean_loan_document.png")

        mock_gcp = MagicMock()
        mock_gcp.name = "gcp_vision"
        mock_gcp.extract.side_effect = GCPAuthError("Could not automatically determine credentials")

        mock_tesseract = MagicMock()
        mock_tesseract.name = "tesseract"
        mock_tesseract.extract.return_value = OCRResult(
            serial_number="LN-2026-9042",
            name="Jane Doe",
            amount=25000.0,
            engine_name="tesseract",
        )

        dual_engine = DualOCREngine(primary_engine=mock_gcp, fallback_engine=mock_tesseract)
        result = dual_engine.extract(image_bytes)

        assert result.fallback_triggered is True
        assert result.engine_name == "tesseract"
        assert "credentials" in result.fallback_reason.lower()

    def test_force_fallback_configuration_flag(self):
        """Verify force_fallback=True bypasses primary engine and routes to Tesseract."""
        image_bytes = get_fixture_bytes("clean_loan_document.png")

        mock_gcp = MagicMock()
        mock_gcp.name = "gcp_vision"
        mock_tesseract = MagicMock()
        mock_tesseract.name = "tesseract"
        mock_tesseract.extract.return_value = OCRResult(
            serial_number="LN-2026-9042",
            engine_name="tesseract",
        )

        dual_engine = DualOCREngine(
            primary_engine=mock_gcp,
            fallback_engine=mock_tesseract,
            force_fallback=True,
        )
        result = dual_engine.extract(image_bytes)

        assert result.fallback_triggered is True
        assert result.engine_name == "tesseract"
        # Primary engine should NOT even have been called
        assert not mock_gcp.extract.called
        assert mock_tesseract.extract.called

    def test_e2e_upload_with_ocr_force_fallback_env(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, loan_repo
    ):
        """
        AC3 End-to-End Test via API:
        Set OCR_FORCE_FALLBACK=true environment variable and perform document upload.
        Verify:
        1. API returns success (200/201).
        2. Response telemetry indicates engine is 'tesseract' and fallback_triggered is True.
        3. Draft loan persisted in SQLite records ocr_engine_used as 'tesseract'.
        """
        monkeypatch.setenv("OCR_FORCE_FALLBACK", "true")
        monkeypatch.setattr("src.config.OCR_FORCE_FALLBACK", True)

        image_bytes = get_fixture_bytes("clean_loan_document.png")
        files = {"file": ("clean_loan_document.png", image_bytes, "image/png")}

        response = client.post("/api/documents/upload", files=files)
        assert response.status_code in (200, 201), f"Upload failed: {response.text}"

        data = response.json()
        assert data.get("ocr_engine_used") == "tesseract" or data.get("engine_name") == "tesseract"
        assert data.get("fallback_triggered") is True

        loan_id = data.get("id") or data.get("loan_id")
        persisted = loan_repo.get_loan_by_id(loan_id)
        assert persisted is not None
        assert persisted.ocr_engine_used == "tesseract"

    def test_both_engines_failing_raises_error(self):
        """Verify that when both primary and fallback engines fail, AllOCREnginesFailedError is raised."""
        image_bytes = get_fixture_bytes("clean_loan_document.png")

        mock_gcp = MagicMock()
        mock_gcp.name = "gcp_vision"
        mock_gcp.extract.side_effect = GCPQuotaExceededError("Quota exceeded")

        mock_tesseract = MagicMock()
        mock_tesseract.name = "tesseract"
        mock_tesseract.extract.side_effect = RuntimeError("Tesseract crash")

        dual_engine = DualOCREngine(primary_engine=mock_gcp, fallback_engine=mock_tesseract)

        with pytest.raises(AllOCREnginesFailedError) as exc_info:
            dual_engine.extract(image_bytes)

        assert "all ocr engines failed" in str(exc_info.value).lower()
