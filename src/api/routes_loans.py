"""Loan management, retrieval, and verification endpoints."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from src.db.models import LoanRecord, VerificationPayload
from src.db.repository import LoanRepository

router = APIRouter(prefix="/api/loans", tags=["loans"])

@router.get("/{loan_id}", response_model=LoanRecord)
async def get_loan(loan_id: int) -> LoanRecord:
    """Fetch single loan record by ID."""
    repo = LoanRepository()
    record = repo.get_loan_by_id(loan_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loan record with ID {loan_id} not found.",
        )
    return record

@router.post("/{loan_id}/verify", response_model=LoanRecord)
async def verify_loan(loan_id: int, payload: VerificationPayload) -> LoanRecord:
    """
    Submit Human-in-the-Loop verification edits.
    Updates modified fields and marks record as verified with audit timestamp.
    """
    repo = LoanRepository()
    record = repo.get_loan_by_id(loan_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loan record with ID {loan_id} not found.",
        )

    # Validate amount if provided
    if payload.amount is not None and payload.amount <= 0:
        raise HTTPException(
            status_code=422,
            detail="Loan amount must be a positive number greater than zero.",
        )

    try:
        updated = repo.update_and_verify_loan(loan_id, payload)
        return updated
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update and verify loan record: {exc}",
        )

@router.get("", response_model=List[LoanRecord])
async def list_loans(
    verified_only: bool = Query(False, description="Filter for verified loans only"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> List[LoanRecord]:
    """Retrieve paginated list of loans with optional verified filter."""
    repo = LoanRepository()
    return repo.list_loans(verified_only=verified_only, limit=limit, offset=offset)
