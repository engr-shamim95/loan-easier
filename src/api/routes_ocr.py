"""OCR and document upload endpoints."""

import io
import os
import uuid
import logging
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from PIL import Image

from src.config import (
    UPLOADS_DIR,
    MAX_UPLOAD_SIZE,
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    OCR_FORCE_FALLBACK,
)
from src.db.models import LoanCreate
from src.db.repository import LoanRepository
from src.ocr.dual_engine import DualOCREngine

logger = logging.getLogger("loan_ocr.routes_ocr")
router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Ingest and Extract Document",
    description="Accepts an image upload, performs OCR, and creates a draft record.",
)
async def upload_document(
    file: UploadFile = File(...),
    project_type: str = Form("loan")
) -> Dict[str, Any]:
    """
    Ingest a loan document image, execute Dual OCR extraction,
    archive the image, and persist an initial draft loan record.
    """
    # 1. Validate file presence and filename
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file missing filename.",
        )

    ext = Path(file.filename).suffix.lower()
    content_type = (file.content_type or "").lower()

    # 2. Validate MIME type and file extension
    is_allowed_mime = content_type in ALLOWED_MIME_TYPES
    is_allowed_ext = ext in ALLOWED_EXTENSIONS

    if not is_allowed_mime and not is_allowed_ext:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file format '{ext or content_type}'. Allowed types: PNG, JPEG, TIFF, BMP, WebP.",
        )

    # 3. Read file stream and validate size
    image_bytes = await file.read()
    if not image_bytes or len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    if len(image_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowable size of {MAX_UPLOAD_SIZE // (1024 * 1024)}MB.",
        )

    # 4. Validate binary integrity
    is_image = ext in {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}
    if is_image:
        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            pil_image.verify()
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Unable to decode or verify image integrity: {exc}",
            )

    # 5. Archive file safely to data/uploads
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{uuid.uuid4().hex[:12]}_{Path(file.filename).name}"
    archive_path = UPLOADS_DIR / safe_filename
    archive_path.write_bytes(image_bytes)
    
    # Text File Parsing
    if not is_image:
        from src.ocr.text_parser import parse_csv, parse_json, parse_markdown
        try:
            if ext == ".csv":
                batch_result = parse_csv(image_bytes)
            elif ext == ".json":
                batch_result = parse_json(image_bytes)
            elif ext == ".md":
                batch_result = parse_markdown(image_bytes)
            else:
                raise ValueError(f"Unknown text format: {ext}")
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Failed to parse text file: {exc}")
            
        # Jump directly to tabular saving logic
        pass 
    else:
        # 6. Execute Dual OCR Extraction
        import src.config
        force_fallback = getattr(src.config, "OCR_FORCE_FALLBACK", False) or (
            os.getenv("OCR_FORCE_FALLBACK", "").lower() in ("true", "1")
        )
    
        ocr_engine = DualOCREngine(force_fallback=force_fallback)
    
        # 7. Route based on document structure: Multi-Row Tabular vs. Single Record Form
        if DualOCREngine.is_tabular_image(pil_image, file.filename):
            logger.info(f"Tabular document detected: {file.filename}. Invoking extract_tabular.")
            try:
                batch_result = ocr_engine.extract_tabular(image_bytes)
            except Exception as exc:
                logger.error(f"Tabular OCR extraction completely failed: {exc}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"OCR processing failed across all available engines: {exc}",
                )
        else:
            batch_result = None

    if not is_image or (is_image and batch_result is not None):

        repo = LoanRepository()
        persisted_records = []
        for row in batch_result.rows:
            row_dict = row.to_dict()
            row_dict["verified"] = False
            default_serial = str(row.serial_number.value or f"LN-DRAFT-{uuid.uuid4().hex[:8].upper()}")
            default_name = str(row.name.value or "Pending Review")
            default_amount = float(row.amount.value) if row.amount.value is not None else 0.0

            loan_create = LoanCreate(
                batch_id=batch_result.batch_id,
                row_index=row.row_index,
                project_type=project_type,
                serial_number=default_serial,
                name=default_name,
                mobile=str(row.mobile.value or ""),
                address=str(row.address.value or ""),
                amount=default_amount,
                image_path=f"uploads/{safe_filename}",
                raw_ocr_data={"batch_id": batch_result.batch_id, "row_index": row.row_index, "cells": row_dict.get("cells")},
                confidences=row_dict.get("confidences", {}),
                ocr_engine_used=batch_result.engine_name,
                verified=False,
            )
            try:
                persisted = repo.create_loan(loan_create)
                row_dict["id"] = persisted.id
                row_dict["loan_id"] = persisted.id
            except Exception as exc:
                logger.error(f"Failed to persist draft batch row in SQLite: {exc}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database persistence failure: {exc}",
                )
            persisted_records.append(row_dict)

        first_record = persisted_records[0] if persisted_records else {}
        return {
            "batch_id": batch_result.batch_id,
            "records": persisted_records,
            "rows": persisted_records,
            "total_rows": len(persisted_records),
            "engine_used": batch_result.engine_name,
            "ocr_engine_used": batch_result.engine_name,
            "engine_name": batch_result.engine_name,
            "fallback_triggered": batch_result.fallback_triggered,
            "fallback_reason": batch_result.fallback_reason,
            "execution_time_ms": batch_result.execution_time_ms,
            "image_path": f"uploads/{safe_filename}",
            "raw_text": batch_result.raw_text,
            "is_tabular": True,
            "project_type": project_type,
            # Backwards compatibility fields for single-record consumers
            "id": first_record.get("id"),
            "loan_id": first_record.get("loan_id"),
            "serial_number": first_record.get("serial_number"),
            "name": first_record.get("name"),
            "mobile": first_record.get("mobile"),
            "address": first_record.get("address"),
            "amount": first_record.get("amount"),
            "confidences": first_record.get("confidences", {}),
            "verified": False,
        }

    # Single-record document ingestion
    try:
        ocr_result = ocr_engine.extract(image_bytes)
    except Exception as exc:
        logger.error(f"OCR extraction completely failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OCR processing failed across all available engines: {exc}",
        )

    # Persist unverified draft loan record in SQLite
    repo = LoanRepository()
    default_serial = ocr_result.serial_number or f"LN-DRAFT-{uuid.uuid4().hex[:8].upper()}"
    default_name = ocr_result.name or "Pending Review"
    default_amount = ocr_result.amount if ocr_result.amount is not None else 0.0

    loan_create = LoanCreate(
        serial_number=default_serial,
        project_type=project_type,
        name=default_name,
        mobile=ocr_result.mobile or "",
        address=ocr_result.address or "",
        amount=default_amount,
        image_path=f"uploads/{safe_filename}",
        raw_ocr_data=ocr_result.raw_ocr_data,
        confidences=ocr_result.confidences,
        ocr_engine_used=ocr_result.engine_name,
        verified=False,
    )

    try:
        persisted = repo.create_loan(loan_create)
    except Exception as exc:
        logger.error(f"Failed to persist draft loan record in SQLite: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database persistence failure: {exc}",
        )

    # Return comprehensive payload for HITL verification form
    return {
        "id": persisted.id,
        "loan_id": persisted.id,
        "serial_number": persisted.serial_number,
        "name": persisted.name,
        "mobile": persisted.mobile,
        "address": persisted.address,
        "amount": persisted.amount,
        "confidences": persisted.confidences,
        "ocr_engine_used": persisted.ocr_engine_used,
        "engine_name": persisted.ocr_engine_used,
        "fallback_triggered": ocr_result.fallback_triggered,
        "fallback_reason": ocr_result.fallback_reason,
        "verified": persisted.verified,
        "image_path": persisted.image_path,
        "raw_text": ocr_result.raw_text,
        "is_tabular": False,
        "project_type": persisted.project_type,
    }
