"""Loan Agreement PDF Generator utilizing Playwright and HTML Templates."""

import io
import zipfile
from datetime import datetime, timezone
from typing import List

from jinja2 import Template
from playwright.sync_api import sync_playwright

from src.db.models import LoanRecord
from src.export.html_templates import LOAN_AGREEMENT_TEMPLATE, BATCH_SUMMARY_TEMPLATE


class PDFGenerator:
    """Generates legally structured, professional PDF Loan Agreements with flawless Bengali rendering."""

    def __init__(self) -> None:
        self.loan_template = Template(LOAN_AGREEMENT_TEMPLATE)
        self.batch_template = Template(BATCH_SUMMARY_TEMPLATE)

    def _render_loan_html(self, loan: LoanRecord, lender_name: str, lender_address: str) -> str:
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        html = self.loan_template.render(
            loan=loan, 
            current_date=current_date,
            lender_name=lender_name,
            lender_address=lender_address,
            project_type=loan.project_type
        )
        return html
        
    def _extract_body_inner_html(self, html: str) -> str:
        """Extract just the contents of <body> to embed in the combined document."""
        start = html.find("<body>")
        end = html.find("</body>")
        if start != -1 and end != -1:
            return html[start+6:end]
        return html

    def _generate_pdf_in_thread(self, html: str) -> bytes:
        import concurrent.futures
        def run_playwright():
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_content(html)
                pdf_bytes = page.pdf(format="Letter", margin={"top": "40px", "bottom": "40px", "left": "40px", "right": "40px"})
                browser.close()
                return pdf_bytes
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(run_playwright).result()

    def generate_loan_agreement(self, loan: LoanRecord, lender_name: str = "Loan Easier", lender_address: str = "Dhaka, Bangladesh") -> bytes:
        """Generate PDF loan agreement for a loan record and return raw PDF bytes."""
        html = self._render_loan_html(loan, lender_name, lender_address)
        return self._generate_pdf_in_thread(html)

    def generate_batch_combined_pdf(self, loans: List[LoanRecord], batch_id: str, lender_name: str = "Loan Easier", lender_address: str = "Dhaka, Bangladesh") -> bytes:
        """
        Generate combined multi-page PDF agreement for a batch:
        Page 1: Executive Summary Table with batch totals.
        Page 2+: Individual loan agreement pages.
        """
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        total_amount = sum(float(l.amount) for l in loans)
        
        # Render individual loan HTMLs to embed
        loan_htmls = [self._extract_body_inner_html(self._render_loan_html(loan, lender_name, lender_address)) for loan in loans]
        
        project_type = loans[0].project_type if loans else "loan"

        html = self.batch_template.render(
            loans=loans,
            batch_id=batch_id,
            current_date=current_date,
            total_amount=total_amount,
            loan_htmls=loan_htmls,
            lender_name=lender_name,
            lender_address=lender_address,
            project_type=project_type
        )
        
        return self._generate_pdf_in_thread(html)

    def generate_batch_zip(self, loans: List[LoanRecord], batch_id: str, lender_name: str = "Loan Easier", lender_address: str = "Dhaka, Bangladesh") -> bytes:
        """
        Generate a ZIP archive containing individual loan agreement PDFs
        for each loan record in the batch.
        """
        zip_buffer = io.BytesIO()
        
        import concurrent.futures
        def run_playwright_zip():
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for idx, loan in enumerate(loans, start=1):
                        loan_html = self._render_loan_html(loan, lender_name, lender_address)
                        page.set_content(loan_html)
                        pdf_bytes = page.pdf(format="Letter", margin={"top": "40px", "bottom": "40px", "left": "40px", "right": "40px"})
                        
                        safe_serial = str(loan.serial_number).replace("/", "_").replace("\\", "_")
                        filename = f"loan_agreement_{idx:03d}_{safe_serial}.pdf"
                        zf.writestr(filename, pdf_bytes)
                        
                browser.close()
                
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(run_playwright_zip).result()
            
        return zip_buffer.getvalue()
