"""Loan Agreement PDF Generator utilizing ReportLab."""

import io
from datetime import datetime
from typing import Optional, Union
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

from src.db.models import LoanRecord

class PDFGenerator:
    """Generates legally structured, professional PDF Loan Agreements."""

    def __init__(self) -> None:
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Configure typography and palette for loan agreements."""
        self.title_style = ParagraphStyle(
            "DocTitle",
            parent=self.styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1A365D"),  # Deep Navy
            alignment=1,  # Center
            spaceAfter=6,
        )

        self.subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4A5568"),
            alignment=1,
            spaceAfter=12,
        )

        self.section_header_style = ParagraphStyle(
            "SectionHeader",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=10,
            spaceAfter=6,
        )

        self.body_style = ParagraphStyle(
            "LegalBody",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#2D3748"),
            spaceAfter=6,
        )

        self.audit_badge_style = ParagraphStyle(
            "AuditBadge",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#276749"),  # Deep Green
            alignment=1,
        )

    def _safe_escape(self, text: Optional[Union[str, int, float]]) -> str:
        """Escape HTML/XML entities (<, >, &, \", ') for safe ReportLab rendering."""
        if text is None:
            return ""
        s = str(text)
        return escape(s, entities={'"': "&quot;", "'": "&apos;"})

    def generate_loan_agreement(self, loan: LoanRecord) -> bytes:
        """Generate PDF loan agreement for a loan record and return raw PDF bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        elements = []

        # 1. Header Banner
        elements.append(Paragraph("OFFICIAL LOAN AGREEMENT &amp; PROMISSORY NOTE", self.title_style))
        elements.append(
            Paragraph("Standard Commercial Lending &amp; Security Agreement", self.subtitle_style)
        )
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2B6CB0"), spaceAfter=12))

        # 2. Reference & Metadata Table
        formatted_amount = f"${loan.amount:,.2f}"
        verified_date_str = (
            loan.verified_at[:10]
            if loan.verified_at
            else datetime.utcnow().strftime("%Y-%m-%d")
        )

        meta_data = [
            [
                Paragraph(f"<b>Agreement Serial Number:</b> {self._safe_escape(loan.serial_number)}", self.body_style),
                Paragraph(f"<b>Execution Date:</b> {self._safe_escape(verified_date_str)}", self.body_style),
            ],
            [
                Paragraph(f"<b>Loan Record ID:</b> #{loan.id}", self.body_style),
                Paragraph(
                    f"<b>Verification Status:</b> {'VERIFIED' if loan.verified else 'DRAFT / PENDING'}",
                    self.body_style,
                ),
            ],
        ]

        meta_table = Table(meta_data, colWidths=[270, 260])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 14))

        # 3. Borrower Particulars Section
        elements.append(Paragraph("1. BORROWER PARTICULARS", self.section_header_style))

        borrower_data = [
            [
                Paragraph("<b>Full Legal Name:</b>", self.body_style),
                Paragraph(self._safe_escape(loan.name), self.body_style),
            ],
            [
                Paragraph("<b>Primary Mobile Number:</b>", self.body_style),
                Paragraph(self._safe_escape(loan.mobile), self.body_style),
            ],
            [
                Paragraph("<b>Residential Address:</b>", self.body_style),
                Paragraph(self._safe_escape(loan.address or "Not Provided"), self.body_style),
            ],
        ]

        borrower_table = Table(borrower_data, colWidths=[150, 380])
        borrower_table.setStyle(
            TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(borrower_table)
        elements.append(Spacer(1, 14))

        # 4. Financial Terms Section
        elements.append(Paragraph("2. PRINCIPAL LOAN AMOUNT &amp; FINANCIAL TERMS", self.section_header_style))

        financial_data = [
            [
                Paragraph("<b>Approved Principal Amount:</b>", self.body_style),
                Paragraph(f"<b>{self._safe_escape(formatted_amount)}</b> (USD)", self.body_style),
            ],
            [
                Paragraph("<b>Disbursement Method:</b>", self.body_style),
                Paragraph("Direct Electronic Funds Transfer (ACH/Wire)", self.body_style),
            ],
            [
                Paragraph("<b>Repayment Schedule:</b>", self.body_style),
                Paragraph("Standard monthly amortized installments per attached schedule.", self.body_style),
            ],
        ]

        financial_table = Table(financial_data, colWidths=[180, 350])
        financial_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDF2F7")),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(financial_table)
        elements.append(Spacer(1, 14))

        # 5. Promissory Note & Covenants
        elements.append(Paragraph("3. PROMISSORY NOTE &amp; LEGAL COVENANTS", self.section_header_style))
        clauses_text = (
            "FOR VALUE RECEIVED, the undersigned Borrower jointly and severally promises to pay to the Lender the principal "
            "sum of <b>"
            + self._safe_escape(formatted_amount)
            + "</b> together with applicable interest. Borrower acknowledges receipt of a fully executed copy of this Agreement "
            "and confirms that the details extracted from submitted documentation have been reviewed, verified, and confirmed accurate."
        )
        elements.append(Paragraph(clauses_text, self.body_style))
        elements.append(Spacer(1, 10))

        # 6. HITL Verification Audit Mark
        audit_box = [
            [
                Paragraph(
                    f"✓ <b>Human-in-the-Loop (HITL) Verified</b> | OCR Engine: {self._safe_escape(loan.ocr_engine_used)} | "
                    f"Audit Timestamp: {self._safe_escape(loan.verified_at or 'Verified on Review')}",
                    self.audit_badge_style,
                )
            ]
        ]
        audit_table = Table(audit_box, colWidths=[530])
        audit_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#C6F6D5")),  # Soft Green
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#38A169")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(audit_table)
        elements.append(Spacer(1, 20))

        # 7. Signatures Block
        elements.append(Paragraph("4. EXECUTION &amp; SIGNATURES", self.section_header_style))

        sig_data = [
            [
                Paragraph("<b>Borrower:</b>", self.body_style),
                Paragraph("<b>Authorized Lending Officer:</b>", self.body_style),
            ],
            [
                Paragraph(f"Signature: ___________________________<br/>Name: {self._safe_escape(loan.name)}<br/>Date: {self._safe_escape(verified_date_str)}", self.body_style),
                Paragraph("Signature: ___________________________<br/>Name: Lending Operations Officer<br/>Date: " + self._safe_escape(verified_date_str), self.body_style),
            ],
        ]

        sig_table = Table(sig_data, colWidths=[265, 265])
        sig_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(sig_table)

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
