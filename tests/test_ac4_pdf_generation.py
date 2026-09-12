"""Tests for Acceptance Criteria 4 (AC4): Loan Agreement PDF Generation.

AC4: Generate PDF loan agreement and verify the PDF contains the expected verified fields.
"""

import io
import pytest
from fastapi.testclient import TestClient
import pypdfium2 as pdfium

from src.db.models import LoanRecord, LoanCreate

def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract full plain text from PDF bytes using pypdfium2."""
    doc = pdfium.PdfDocument(pdf_bytes)
    full_text = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        text_page = page.get_textpage()
        full_text.append(text_page.get_text_range())
    return "\n".join(full_text)

class TestAC4PDFGeneration:
    """Test suite covering AC4 loan agreement PDF generation and field validation."""

    def test_generate_pdf_endpoint_e2e(
        self, client: TestClient, sample_verified_loan_record: LoanRecord
    ):
        """
        AC4 Primary Test:
        1. Retrieve PDF via GET /api/loans/{id}/pdf for a verified loan record.
        2. Assert response status is 200.
        3. Assert Content-Type is 'application/pdf'.
        4. Assert body begins with %PDF- header.
        5. Extract text and verify all expected verified fields are present.
        """
        loan_id = sample_verified_loan_record.id

        response = client.get(f"/api/loans/{loan_id}/pdf")
        assert response.status_code == 200, f"PDF generation failed: {response.text}"
        assert "application/pdf" in response.headers.get("content-type", "")
        assert response.content.startswith(b"%PDF-"), "Response content does not have PDF header"

        # Extract and verify text
        pdf_text = extract_pdf_text(response.content)

        # Verify all 5 loan fields appear in the PDF
        assert sample_verified_loan_record.serial_number in pdf_text
        assert sample_verified_loan_record.name in pdf_text
        assert sample_verified_loan_record.mobile in pdf_text
        assert "Springfield" in pdf_text or sample_verified_loan_record.address in pdf_text
        assert "25,000" in pdf_text or "25000" in pdf_text

        # Verify agreement clauses and signature headers
        assert "LOAN AGREEMENT" in pdf_text.upper() or "PROMISSORY" in pdf_text.upper()

    def test_pdf_generator_unit_contract(self, loan_repo, clean_loan_payload):
        """Unit test for PDFGenerator.generate_loan_agreement contract."""
        from src.export.pdf_generator import PDFGenerator

        record = loan_repo.create_loan(
            LoanCreate(
                serial_number="LN-PDF-UNIT-01",
                name="Alexander Hamilton",
                mobile="+1-555-177-6123",
                address="57 Wall Street, New York, NY 10005",
                amount=75000.0,
                ocr_engine_used="gcp_vision",
                verified=True,
                verified_at="2026-09-12T04:00:00Z",
            )
        )

        generator = PDFGenerator()
        pdf_bytes = generator.generate_loan_agreement(record)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 500
        assert pdf_bytes.startswith(b"%PDF-")

        text = extract_pdf_text(pdf_bytes)
        assert "LN-PDF-UNIT-01" in text
        assert "Alexander Hamilton" in text
        assert "75,000" in text

    def test_pdf_generation_escapes_special_characters(self, loan_repo):
        """
        Adversarial Edge Case:
        Ensure XML special characters (<, >, &, \", ') in borrower details
        do not crash ReportLab flowables and are rendered safely.
        """
        from src.export.pdf_generator import PDFGenerator

        special_record = loan_repo.create_loan(
            LoanCreate(
                serial_number="LN-SPEC-CHARS-&<>",
                name="Alice & Bob <Partners> \"Consultants\"",
                mobile="+1-555-000-1111",
                address="100 M&M Road <Ste 4B> & 5th Ave",
                amount=50000.0,
                ocr_engine_used="gcp_vision",
                verified=True,
                verified_at="2026-09-12T04:00:00Z",
            )
        )

        generator = PDFGenerator()
        pdf_bytes = generator.generate_loan_agreement(special_record)
        assert pdf_bytes.startswith(b"%PDF-")

        text = extract_pdf_text(pdf_bytes)
        assert "LN-SPEC-CHARS-" in text
        assert "Alice" in text
        assert "Bob" in text

    def test_nonexistent_loan_pdf_returns_404(self, client: TestClient):
        """Edge Case: Requesting PDF for non-existent loan ID returns HTTP 404."""
        response = client.get("/api/loans/999999/pdf")
        assert response.status_code == 404
