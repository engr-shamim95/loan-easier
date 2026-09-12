"""Tests for Acceptance Criteria 2 (AC2): Form Modification & Local SQLite Persistence.

AC2: Modify a field in the verification form payload, submit verification/update,
and verify the updated data is persisted locally in SQLite.
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from src.db.models import LoanRecord, VerificationPayload

class TestAC2VerificationSave:
    """Test suite covering AC2 human-in-the-loop field edits and SQLite persistence."""

    def test_modify_fields_and_verify_e2e_persistence(
        self, client: TestClient, sample_loan_record: LoanRecord, loan_repo
    ):
        """
        AC2 Primary Test:
        1. Start with an unverified draft loan in SQLite (created by sample_loan_record).
        2. Modify fields: change amount from 25000.00 to 30000.00, update name and address.
        3. Submit verification update via POST /api/loans/{id}/verify.
        4. Verify API response confirms verified=True and new field values.
        5. Verify local SQLite directly via LoanRepository to guarantee persistent storage.
        """
        loan_id = sample_loan_record.id
        assert sample_loan_record.verified is False

        # Prepare modified payload
        modified_payload = {
            "serial_number": sample_loan_record.serial_number,
            "name": "Jane M. Doe-Updated",
            "mobile": "+1-555-999-0000",
            "address": "999 Innovation Parkway, Suite 400, Springfield, IL 62704",
            "amount": 30000.00,
        }

        response = client.post(f"/api/loans/{loan_id}/verify", json=modified_payload)
        assert response.status_code in (200, 204), f"Verification failed: {response.text}"

        resp_data = response.json()
        assert resp_data["name"] == "Jane M. Doe-Updated"
        assert float(resp_data["amount"]) == 30000.00
        assert resp_data["mobile"] == "+1-555-999-0000"
        assert resp_data["verified"] is True
        assert resp_data.get("verified_at") is not None

        # Verify directly in SQLite via repository
        persisted = loan_repo.get_loan_by_id(loan_id)
        assert persisted is not None, f"Loan {loan_id} not found in SQLite"
        assert persisted.name == "Jane M. Doe-Updated"
        assert float(persisted.amount) == 30000.00
        assert persisted.address == "999 Innovation Parkway, Suite 400, Springfield, IL 62704"
        assert persisted.mobile == "+1-555-999-0000"
        assert persisted.verified is True
        assert persisted.verified_at is not None

        # Verify timestamp is valid ISO format
        dt = datetime.fromisoformat(persisted.verified_at)
        assert dt is not None

    def test_subsequent_get_reflects_updated_data(
        self, client: TestClient, sample_loan_record: LoanRecord
    ):
        """Verify that GET /api/loans/{id} returns the updated persisted record."""
        loan_id = sample_loan_record.id

        update_payload = {
            "amount": 42500.50,
            "name": "Marcus Aurelius",
        }
        client.post(f"/api/loans/{loan_id}/verify", json=update_payload)

        get_resp = client.get(f"/api/loans/{loan_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert float(data["amount"]) == 42500.50
        assert data["name"] == "Marcus Aurelius"
        assert data["verified"] is True

    def test_repository_atomic_update_and_verify(self, loan_repo, clean_loan_payload):
        """Unit contract test for LoanRepository.update_and_verify_loan."""
        from src.db.models import LoanCreate

        draft = loan_repo.create_loan(
            LoanCreate(
                serial_number="LN-REPO-TEST-01",
                name=clean_loan_payload["name"],
                mobile=clean_loan_payload["mobile"],
                address=clean_loan_payload["address"],
                amount=10000.0,
                ocr_engine_used="gcp_vision",
            )
        )
        assert draft.verified is False

        updated = loan_repo.update_and_verify_loan(
            draft.id,
            VerificationPayload(
                name="Verified Name",
                amount=15500.0,
            ),
        )

        assert updated.verified is True
        assert updated.name == "Verified Name"
        assert float(updated.amount) == 15500.0
        assert updated.verified_at is not None

        # Re-fetch from clean connection to verify WAL persistence
        refetched = loan_repo.get_loan_by_id(draft.id)
        assert refetched.verified is True
        assert float(refetched.amount) == 15500.0
