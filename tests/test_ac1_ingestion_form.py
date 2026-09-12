"""Tests for Acceptance Criteria 1 (AC1): Document Ingestion & Form Population.

AC1: Upload a mock image and simulate OCR extraction; verify extracted data
populates the verification form structure (serial_number, name, mobile, address, amount)
and field confidences correctly.
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from tests.fixtures.mock_images import get_fixture_bytes, get_fixture_path, SAMPLE_LOAN_DATA

class TestAC1IngestionAndFormPopulation:
    """Test suite covering AC1 ingestion and verification form population."""

    def test_upload_mock_image_e2e_success(self, client: TestClient):
        """
        AC1 Primary Test:
        Upload clean mock image to /api/documents/upload and verify:
        1. HTTP 200/201 response.
        2. Extracted fields contain serial_number, name, mobile, address, amount.
        3. Confidences dict contains all 5 fields normalized to [0.00, 1.00].
        4. Record is saved as unverified draft with a valid loan_id.
        """
        image_bytes = get_fixture_bytes("clean_loan_document.png")
        files = {
            "file": ("clean_loan_document.png", image_bytes, "image/png"),
        }

        response = client.post("/api/documents/upload", files=files)
        assert response.status_code in (200, 201), f"Upload failed: {response.text}"

        data = response.json()
        assert "id" in data or "loan_id" in data, "Response must include loan identifier"
        loan_id = data.get("id") or data.get("loan_id")
        assert isinstance(loan_id, int), "loan_id must be an integer"

        # Verify extracted field contents
        assert data.get("serial_number") == SAMPLE_LOAN_DATA["serial_number"]
        assert data.get("name") == SAMPLE_LOAN_DATA["name"]
        assert "555" in str(data.get("mobile"))
        assert "Evergreen" in str(data.get("address"))
        assert float(data.get("amount")) == 25000.0

        # Verify confidences structure and values
        confidences = data.get("confidences", {})
        assert isinstance(confidences, dict), "confidences must be a dictionary"
        for field in ["serial_number", "name", "mobile", "address", "amount"]:
            assert field in confidences, f"Field '{field}' missing from confidences"
            conf = float(confidences[field])
            assert 0.0 <= conf <= 1.0, f"Confidence for '{field}' ({conf}) not in [0.00, 1.00]"

        # Initial state must be unverified
        assert data.get("verified") is False or data.get("verified") == 0

    def test_form_retrieval_matches_uploaded_data(self, client: TestClient):
        """
        Verify that after upload, the HITL form can fetch the populated record
        via GET /api/loans/{id} with identical structure and confidences.
        """
        image_bytes = get_fixture_bytes("clean_loan_document.png")
        files = {"file": ("clean_loan_document.png", image_bytes, "image/png")}
        upload_resp = client.post("/api/documents/upload", files=files)
        assert upload_resp.status_code in (200, 201)
        loan_id = upload_resp.json().get("id") or upload_resp.json().get("loan_id")

        get_resp = client.get(f"/api/loans/{loan_id}")
        assert get_resp.status_code == 200, f"Failed to get loan: {get_resp.text}"

        form_data = get_resp.json()
        assert form_data["id"] == loan_id
        assert form_data["serial_number"] == SAMPLE_LOAN_DATA["serial_number"]
        assert form_data["name"] == SAMPLE_LOAN_DATA["name"]
        assert float(form_data["amount"]) == 25000.0
        assert form_data["verified"] is False or form_data["verified"] == 0

    def test_jpeg_format_ingestion_success(self, client: TestClient):
        """Verify that JPEG mock image upload also works seamlessly."""
        image_bytes = get_fixture_bytes("clean_loan_document.jpg")
        files = {"file": ("clean_loan_document.jpg", image_bytes, "image/jpeg")}
        response = client.post("/api/documents/upload", files=files)
        assert response.status_code in (200, 201), f"JPEG upload failed: {response.text}"
        data = response.json()
        assert data.get("serial_number") == SAMPLE_LOAN_DATA["serial_number"]

    def test_ocr_field_parser_contract(self):
        """
        Direct contract test for parser:
        Verifies parser extracts the 5 fields and computes normalized confidences.
        """
        from src.ocr.parser import parse_loan_fields, normalize_confidence, is_low_confidence

        raw_text = (
            "OFFICIAL LOAN AGREEMENT\n"
            "Serial Number: LN-2026-9042\n"
            "Borrower Name: Jane Doe\n"
            "Mobile: +1-555-234-5678\n"
            "Address: 742 Evergreen Terrace, Springfield, IL 62704\n"
            "Loan Amount: $25,000.00\n"
        )

        values, confidences = parse_loan_fields(raw_text)

        assert values["serial_number"] == "LN-2026-9042"
        assert values["name"] == "Jane Doe"
        assert "555" in values["mobile"]
        assert "742 Evergreen" in values["address"]
        assert values["amount"] == 25000.0

        for key in ["serial_number", "name", "mobile", "address", "amount"]:
            assert 0.0 <= confidences[key] <= 1.0
            # High quality text should have confidence >= 0.80
            assert confidences[key] >= 0.80
            assert not is_low_confidence(confidences[key])
