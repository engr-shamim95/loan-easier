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
async def export_loan_agreement_pdf(loan_id: int) -> Response:
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
        pdf_bytes = generator.generate_loan_agreement(record)
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
) -> Response:
    """
    Generate RFC 4180 compliant CSV export of all verified loans for the specified month.
    Defaults to current UTC month if month is not specified.
    """
    target_month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    repo = LoanRepository()

    # Query verified loans for target month
    loans = repo.list_loans_by_month(target_month, verified_only=True)

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
) -> Response:
    """
    Generate styled Excel (.xlsx) export of all verified loans for the specified month.
    """
    target_month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    repo = LoanRepository()

    loans = repo.list_loans_by_month(target_month, verified_only=True)

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
