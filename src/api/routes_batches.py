"""Batch loan verification and management API routes."""

import sqlite3
import logging
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, status, Body

from src.db.models import BatchVerificationRequest, BatchResponse, LoanRecord
from src.db.repository import LoanRepository

logger = logging.getLogger("loan_ocr.routes_batches")
router = APIRouter(prefix="/api/batches", tags=["batches"])

@router.post("/{batch_id}/verify", status_code=status.HTTP_200_OK)
async def verify_batch(
    batch_id: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """
    Submit Human-in-the-Loop verification for an entire batch.
    Atomically updates/persists all records and marks them verified inside
    a single SQLite transaction with rollback on failure.
    """
    repo = LoanRepository()
    records = payload.get("records") or payload.get("rows") or []
    deleted_ids = payload.get("deleted_ids") or []

    # Validate non-empty row list if batch has no existing records
    if not records and not deleted_ids:
        # Check if batch already has records
        existing = repo.get_batch_loans(batch_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Batch verification payload contains no records to persist.",
            )
        records = [r.model_dump() for r in existing]

    try:
        updated_records = repo.save_and_verify_batch(
            batch_id=batch_id,
            rows=records,
            deleted_ids=deleted_ids,
        )
    except sqlite3.IntegrityError as ie:
        logger.error(f"Integrity constraint violation verifying batch {batch_id}: {ie}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Database constraint violation: {ie}",
        )
    except Exception as exc:
        logger.error(f"Failed to atomically verify batch {batch_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify batch: {exc}",
        )

    records_data = [r.model_dump() for r in updated_records]
    return {
        "success": True,
        "batch_id": batch_id,
        "verified_count": len(updated_records),
        "total_rows": len(updated_records),
        "records": records_data,
        "rows": records_data,
    }

@router.get("/{batch_id}")
async def get_batch(batch_id: str) -> Dict[str, Any]:
    """
    Retrieve all loan records and metadata associated with a batch.
    """
    repo = LoanRepository()
    loans = repo.get_batch_loans(batch_id)

    records_data = [l.model_dump() for l in loans]
    first_image = None
    for l in loans:
        if l.image_path:
            first_image = l.image_path
            break

    return {
        "batch_id": batch_id,
        "total_rows": len(loans),
        "records": records_data,
        "rows": records_data,
        "image_path": first_image,
    }
