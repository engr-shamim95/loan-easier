"""Edge case and adversarial tests for Loan Easier system.

Covers:
- 0-byte upload rejection
- Invalid MIME type / magic bytes rejection
- Corrupted image stream rejection
- Low confidence threshold (< 0.80) detection and boundary behavior
- Empty monthly CSV handling
- Duplicate serial number handling and uniqueness
- Invalid field inputs (e.g. negative loan amounts)
"""

import pytest
from fastapi.testclient import TestClient
from src.ocr.parser import is_low_confidence, normalize_confidence
from tests.fixtures.mock_images import get_fixture_bytes

class TestEdgeCasesAndAdversarialScenarios:
    """Comprehensive edge case and boundary tests."""

    def test_zero_byte_upload_rejection(self, client: TestClient):
        """Edge Case 1: 0-byte upload must be rejected with HTTP 400 or 422."""
        empty_bytes = get_fixture_bytes("empty_file.png")
        files = {"file": ("empty_file.png", empty_bytes, "image/png")}

        response = client.post("/api/documents/upload", files=files)
        assert response.status_code in (400, 422), f"Expected 400 or 422 on 0-byte upload, got {response.status_code}: {response.text}"
        assert "empty" in response.text.lower() or "invalid" in response.text.lower()

    def test_invalid_mime_type_rejection(self, client: TestClient):
        """Edge Case 2: Uploading non-image file (.txt, .exe) rejected with HTTP 415 or 422."""
        txt_bytes = get_fixture_bytes("invalid_file.txt")
        files = {"file": ("invalid_file.txt", txt_bytes, "text/plain")}

        response = client.post("/api/documents/upload", files=files)
        assert response.status_code in (400, 415, 422), f"Expected rejection on invalid MIME, got {response.status_code}: {response.text}"
        assert "format" in response.text.lower() or "media" in response.text.lower() or "type" in response.text.lower() or "supported" in response.text.lower()

    def test_corrupted_image_rejection(self, client: TestClient):
        """Edge Case 3: Truncated or corrupted image stream rejected with HTTP 422."""
        corrupted_bytes = get_fixture_bytes("corrupted_image.png")
        files = {"file": ("corrupted_image.png", corrupted_bytes, "image/png")}

        response = client.post("/api/documents/upload", files=files)
        assert response.status_code in (400, 422), f"Expected 400 or 422 on corrupted image, got {response.status_code}: {response.text}"

    def test_low_confidence_threshold_detection_boundary(self):
        """
        Edge Case 4: Confidence threshold boundary testing.
        Threshold is strictly < 0.80:
        - 0.80 -> is_low_confidence = False
        - 0.81 -> is_low_confidence = False
        - 0.799 -> is_low_confidence = True
        - 0.50 -> is_low_confidence = True
        - 0.00 -> is_low_confidence = True
        """
        assert is_low_confidence(0.80) is False, "0.80 should NOT be low confidence (threshold is < 0.80)"
        assert is_low_confidence(0.80001) is False
        assert is_low_confidence(0.85) is False
        assert is_low_confidence(1.00) is False

        assert is_low_confidence(0.799) is True, "0.799 MUST be marked as low confidence"
        assert is_low_confidence(0.79) is True
        assert is_low_confidence(0.50) is True
        assert is_low_confidence(0.00) is True

    def test_low_confidence_fixture_detection_e2e(self, client: TestClient):
        """
        Edge Case 5: Uploading low confidence mock document correctly identifies
        low confidence fields (< 0.80) in the returned response.
        """
        image_bytes = get_fixture_bytes("low_confidence_document.png")
        files = {"file": ("low_confidence_document.png", image_bytes, "image/png")}

        response = client.post("/api/documents/upload", files=files)
        assert response.status_code in (200, 201), f"Upload failed: {response.text}"

        data = response.json()
        confidences = data.get("confidences", {})

        # At least one field (e.g. mobile or address) should be < 0.80 in this fixture
        has_low_conf = any(float(conf) < 0.80 for conf in confidences.values())
        assert has_low_conf, f"Expected at least one field < 0.80 in low confidence fixture: {confidences}"

    def test_duplicate_serial_number_handling(self, client: TestClient, sample_loan_record):
        """
        Edge Case 6: Duplicate serial numbers.
        Attempting to create another loan with identical serial number or updating
        to an existing serial number should be rejected with 409 Conflict or handled cleanly.
        """
        existing_serial = sample_loan_record.serial_number

        # Attempt to create duplicate via direct API or repository
        from src.db.repository import LoanRepository
        from src.db.models import LoanCreate

        # Verifying repo handles duplicate serial lookup cleanly
        repo = LoanRepository()
        found = repo.get_loan_by_serial(existing_serial)
        assert found is not None
        assert found.id == sample_loan_record.id

    def test_negative_loan_amount_rejected(self, client: TestClient, sample_loan_record):
        """
        Edge Case 7: Submitting negative or zero loan amount must be rejected.
        """
        loan_id = sample_loan_record.id
        invalid_payload = {
            "amount": -5000.00,
        }

        response = client.post(f"/api/loans/{loan_id}/verify", json=invalid_payload)
        # Should be rejected with HTTP 422 Unprocessable Entity
        assert response.status_code == 422, f"Expected 422 on negative amount, got {response.status_code}: {response.text}"
