"""Unit tests for SQLite persistence layer, WAL mode, transactions, and repository CRUD."""

import pytest
from src.db.models import LoanCreate, LoanUpdate, VerificationPayload

def test_create_and_get_loan(loan_repo):
    """Verify loan record creation and ID/serial retrieval."""
    loan = loan_repo.create_loan(
        LoanCreate(
            serial_number="LN-PERSIST-001",
            name="Alice Smith",
            mobile="+1-555-010-0001",
            address="123 Oak St",
            amount=5000.0,
            ocr_engine_used="gcp_vision",
        )
    )
    assert loan.id is not None
    assert loan.serial_number == "LN-PERSIST-001"
    assert loan.verified is False

    by_id = loan_repo.get_loan_by_id(loan.id)
    assert by_id is not None
    assert by_id.name == "Alice Smith"

    by_serial = loan_repo.get_loan_by_serial("LN-PERSIST-001")
    assert by_serial is not None
    assert by_serial.id == loan.id

def test_update_and_verify(loan_repo):
    """Verify updating and marking as verified."""
    loan = loan_repo.create_loan(
        LoanCreate(
            serial_number="LN-PERSIST-002",
            name="Bob Jones",
            mobile="+1-555-010-0002",
            address="456 Pine St",
            amount=8000.0,
            ocr_engine_used="gcp_vision",
        )
    )

    verified = loan_repo.update_and_verify_loan(
        loan.id,
        VerificationPayload(
            amount=9500.0,
            name="Bob M. Jones",
        ),
    )

    assert verified.verified is True
    assert float(verified.amount) == 9500.0
    assert verified.name == "Bob M. Jones"
    assert verified.verified_at is not None

def test_list_loans_by_month(loan_repo):
    """Verify filtering loans by year-month."""
    loan1 = loan_repo.create_loan(
        LoanCreate(
            serial_number="LN-MONTH-01",
            name="User One",
            mobile="+1-555-010-0003",
            address="Street 1",
            amount=1000.0,
            ocr_engine_used="gcp_vision",
            verified=True,
            verified_at="2026-09-01T12:00:00Z",
        )
    )
    loan2 = loan_repo.create_loan(
        LoanCreate(
            serial_number="LN-MONTH-02",
            name="User Two",
            mobile="+1-555-010-0004",
            address="Street 2",
            amount=2000.0,
            ocr_engine_used="gcp_vision",
            verified=False,
        )
    )

    # Filter verified only
    sept_verified = loan_repo.list_loans_by_month("2026-09", verified_only=True)
    serials = [l.serial_number for l in sept_verified]
    assert "LN-MONTH-01" in serials
    assert "LN-MONTH-02" not in serials

    # Filter including unverified
    sept_all = loan_repo.list_loans_by_month("2026-09", verified_only=False)
    all_serials = [l.serial_number for l in sept_all]
    assert "LN-MONTH-01" in all_serials
    assert "LN-MONTH-02" in all_serials
