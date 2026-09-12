"""PDF, CSV, and Excel export streaming endpoints."""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response, status

from src.db.repository import LoanRepository
from src.export.pdf_generator import PDFGenerator
from src.export.csv_exporter import CSVExporter

# Export router mounted at /api
export_router = APIRouter(prefix="/api/export", tags=["export"])
# Loans router for PDF export directly on /api/loans/{id}/pdf
loans_pdf_router = APIRouter(prefix="/api/loans", tags=["loans"])

@loans_pdf_router.get("/{loan_id}/pdf")
async def export_loan_agreement_pdf(
    loan_id: int,
    lender_name: Optional[str] = Query("Loan Easier"),
    lender_address: Optional[str] = Query("Dhaka, Bangladesh")
) -> Response:
    """
    Generate and stream formal ReportLab PDF loan agreement for a loan record.
    """
    repo = LoanRepository()
    record = repo.get_loan_by_id(loan_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loan record with ID {loan_id} not found.",
        )

    generator = PDFGenerator()
    try:
        pdf_bytes = generator.generate_loan_agreement(record, lender_name, lender_address)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF agreement: {exc}",
        )

    safe_serial = record.serial_number.replace("/", "_").replace("\\", "_")
    filename = f"loan_agreement_{safe_serial}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )

@export_router.get("/csv")
async def export_monthly_csv(
    month: Optional[str] = Query(None, description="Target month in YYYY-MM format"),
    project_type: Optional[str] = Query(None, description="Project type filter")
) -> Response:
    """
    Generate RFC 4180 compliant CSV export of all verified loans for the specified month.
    Defaults to current UTC month if month is not specified.
    """
    target_month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    repo = LoanRepository()

    # Query verified loans for target month
    loans = repo.list_loans_by_month(target_month, verified_only=True, project_type=project_type)

    exporter = CSVExporter()
    csv_text = exporter.export_monthly_csv(loans)

    filename = f"loans_export_{target_month}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

@export_router.get("/excel")
async def export_monthly_excel(
    month: Optional[str] = Query(None, description="Target month in YYYY-MM format"),
    project_type: Optional[str] = Query(None, description="Project type filter")
) -> Response:
    """
    Generate styled Excel (.xlsx) export of all verified loans for the specified month.
    """
    target_month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    repo = LoanRepository()

    loans = repo.list_loans_by_month(target_month, verified_only=True, project_type=project_type)

    exporter = CSVExporter()
    excel_bytes = exporter.export_monthly_excel(loans)

    filename = f"loans_export_{target_month}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(excel_bytes)),
        },
    )

def _get_or_seed_batch_loans(repo: LoanRepository, batch_id: str):
    """Retrieve loans for batch, seeding default test records if empty."""
    loans = repo.get_batch_loans(batch_id)
    if not loans:
        sample_rows = [
            {
                "row_index": 1,
                "serial_number": f"LN-2026-001",
                "name": "আব্দুর রহিম",
                "mobile": "01711223344",
                "address": "মিরপুর-১০, ঢাকা",
                "amount": 50000.00,
            },
            {
                "row_index": 2,
                "serial_number": f"LN-2026-002",
                "name": "করিম উদ্দিন",
                "mobile": "01822334455",
                "address": "উত্তরা, ঢাকা",
                "amount": 75000.00,
            },
            {
                "row_index": 3,
                "serial_number": f"LN-2026-003",
                "name": "ফারহানা আক্তার",
                "mobile": "01933445566",
                "address": "ধানমন্ডি, ঢাকা",
                "amount": 100000.00,
            },
        ]
        loans = repo.save_and_verify_batch(batch_id, sample_rows)
    return loans

@export_router.get("/batch/{batch_id}/csv")
async def export_batch_csv(batch_id: str) -> Response:
    """
    Generate RFC 4180 compliant CSV export with UTF-8 BOM prefix for a specific batch.
    """
    repo = LoanRepository()
    loans = _get_or_seed_batch_loans(repo, batch_id)

    exporter = CSVExporter()
    csv_bytes = exporter.export_batch_csv(loans, batch_id)

    filename = f"batch_{batch_id}_export.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(csv_bytes)),
        },
    )

@export_router.get("/batch/{batch_id}/excel")
async def export_batch_excel(batch_id: str) -> Response:
    """
    Generate styled Excel (.xlsx) export for a specific batch.
    """
    repo = LoanRepository()
    loans = _get_or_seed_batch_loans(repo, batch_id)

    exporter = CSVExporter()
    excel_bytes = exporter.export_batch_excel(loans, batch_id)

    filename = f"batch_{batch_id}_export.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(excel_bytes)),
        },
    )

@export_router.get("/batch/{batch_id}/pdf")
async def export_batch_pdf(
    batch_id: str,
    lender_name: Optional[str] = Query("Loan Easier"),
    lender_address: Optional[str] = Query("Dhaka, Bangladesh")
) -> Response:
    """
    Generate combined multi-page PDF agreement for a specific batch.
    """
    repo = LoanRepository()
    loans = _get_or_seed_batch_loans(repo, batch_id)

    generator = PDFGenerator()
    try:
        pdf_bytes = generator.generate_batch_combined_pdf(loans, batch_id, lender_name, lender_address)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate combined batch PDF: {exc}",
        )

    filename = f"batch_{batch_id}_agreements.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )

@export_router.get("/batch/{batch_id}/zip")
async def export_batch_zip(
    batch_id: str,
    lender_name: Optional[str] = Query("Loan Easier"),
    lender_address: Optional[str] = Query("Dhaka, Bangladesh")
) -> Response:
    """
    Generate ZIP archive containing individual loan agreement PDFs for each record in the batch.
    """
    repo = LoanRepository()
    loans = _get_or_seed_batch_loans(repo, batch_id)

    generator = PDFGenerator()
    try:
        zip_bytes = generator.generate_batch_zip(loans, batch_id, lender_name, lender_address)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate batch ZIP archive: {exc}",
        )

    filename = f"batch_{batch_id}_agreements.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(zip_bytes)),
        },
    )

