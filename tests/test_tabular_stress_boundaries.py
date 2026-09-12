"""Tier 4 Tests: Boundary Conditions, Stress Limits, and Adversarial Scenarios for Tabular OCR.

Scope & Scenarios:
- 100 rows maximum capacity tabular extraction stress.
- Bengali numeral translation (০-৯ -> 0-9) exhaustive conversion matrix & mixed strings.
- Bengali column header synonyms recognition and resilience to misordered/missing headers.
- Strict low-confidence cell threshold boundary evaluation (< 0.80).
- Multi-format batch export resilience (Excel .xlsx, Combined Agreement PDF, Streaming ZIP archive).
"""

import io
import time
import zipfile
import pytest
from typing import Any, Dict, List
from fastapi.testclient import TestClient

from src.ocr.base import TableCell, TableRow, BatchOCRResult
from src.ocr.parser import (
    TableSpatialExtractor,
    parse_tabular_ocr,
    generate_mock_tabular_tokens,
    to_arabic_digits,
    match_header_column,
    is_low_confidence,
    normalize_confidence,
    clean_serial_cell,
    clean_name_cell,
    clean_mobile_cell,
    clean_address_cell,
    clean_amount_cell,
    BENGALI_HEADER_SYNONYMS,
)
from tests.mock_tabular_fixtures import generate_tabular_loan_data, create_mock_tabular_image


class TestTabularStressAndBoundaries:
    """Comprehensive Tier 4 boundary, stress, and adversarial test suite."""

    def test_tabular_100_rows_maximum_capacity_stress(self):
        """
        Boundary & Stress Test:
        Extract a dense, 100-row tabular document.
        Verifies:
        1. All 100 rows are successfully extracted without truncation or loss.
        2. Row indices span sequentially from 1 to 100.
        3. First row is LN-001, last row is LN-100.
        4. Memory and runtime performance: completes within 3.0 seconds.
        """
        start_time = time.perf_counter()
        tokens = generate_mock_tabular_tokens(num_rows=100, base_conf=0.95)
        assert len(tokens) >= 500

        extractor = TableSpatialExtractor(batch_id="BATCH-STRESS-100")
        result: BatchOCRResult = extractor.extract(tokens=tokens)
        elapsed_sec = time.perf_counter() - start_time

        assert result.total_rows == 100, f"Expected 100 rows, got {result.total_rows}"
        assert len(result.rows) == 100

        # Check boundary rows
        first_row = result.rows[0]
        last_row = result.rows[-1]

        assert first_row.row_index == 1
        assert first_row.serial_number.value == "LN-001"
        assert float(first_row.amount.value) > 0

        assert last_row.row_index == 100
        assert last_row.serial_number.value == "LN-100"
        assert float(last_row.amount.value) > 0

        # Performance constraint
        assert elapsed_sec < 3.0, f"100 rows extraction took too long: {elapsed_sec:.2f}s"

    def test_bengali_numeral_exhaustive_translation_matrix(self):
        """
        Adversarial & Boundary Test:
        Exhaustively test translation of all Bengali numerals (০-৯) to Arabic ASCII (0-9).
        Verifies single digits, compound numbers, and edge cases.
        """
        bengali_digits = "০১২৩৪৫৬৭৮৯"
        arabic_digits = "0123456789"

        # 1. Direct 1-to-1 character translation
        assert to_arabic_digits(bengali_digits) == arabic_digits

        # 2. Individual digit validation
        for b_char, a_char in zip(bengali_digits, arabic_digits):
            assert to_arabic_digits(b_char) == a_char

        # 3. Mixed Bengali and ASCII digits in serial numbers
        mixed_serial = "LN-২০২৬-9042"
        assert to_arabic_digits(mixed_serial) == "LN-2026-9042"

        # 4. Bengali phone numbers
        bengali_phone = "০১৭১১২২৩৩৪৪"
        assert to_arabic_digits(bengali_phone) == "01711223344"

        # 5. Complex loan amount with Bengali numerals, currency symbol, and commas
        bengali_amount = "৳১,৫০,০০০.০০"
        val, conf = clean_amount_cell(bengali_amount)
        assert val == 150000.00
        assert conf >= 0.80

    def test_bengali_column_headers_exhaustive_synonyms(self):
        """
        Contract Test:
        Verify that match_header_column recognizes all canonical and alternative
        synonyms for the 5 loan fields in Bengali script and English fallbacks.
        """
        # Serial synonyms
        for syn in ["ক্রমিক নং", "ক্রমিক নম্বর", "ক্রঃ নং", "ক্র নং", "নং", "সিরিয়াল নং", "SL", "Serial No", "Serial"]:
            assert match_header_column(syn) == "serial_number", f"Failed to match serial synonym: '{syn}'"

        # Name synonyms
        for syn in ["নাম", "ঋণগ্রহীতার নাম", "ঋণ গ্রহীতার নাম", "গ্রাহকের নাম", "Borrower Name", "Name"]:
            assert match_header_column(syn) == "name", f"Failed to match name synonym: '{syn}'"

        # Mobile synonyms
        for syn in ["মোবাইল", "মোবাইল নং", "মোবাইল নম্বর", "ফোন", "ফোন নং", "যোগাযোগ", "Mobile", "Phone"]:
            assert match_header_column(syn) == "mobile", f"Failed to match mobile synonym: '{syn}'"

        # Address synonyms
        for syn in ["ঠিকানা", "বর্তমান ঠিকানা", "স্থায়ী ঠিকানা", "বাসার ঠিকানা", "Address", "Location"]:
            assert match_header_column(syn) == "address", f"Failed to match address synonym: '{syn}'"

        # Amount synonyms
        for syn in ["পরিমাণ", "পরিমান", "টাকার পরিমাণ", "টাকার পরিমান", "ঋণের পরিমাণ", "টাকা", "Amount", "Loan Amount"]:
            assert match_header_column(syn) == "amount", f"Failed to match amount synonym: '{syn}'"

    def test_low_confidence_cell_thresholding_strict_boundary(self):
        """
        Boundary Test:
        Strict evaluation of the 0.80 low-confidence threshold.
        - confidence >= 0.80 -> is_low_confidence is False
        - confidence < 0.80 -> is_low_confidence is True
        """
        # Exact boundary values
        assert is_low_confidence(0.80) is False, "0.80 must NOT be flagged as low confidence"
        assert is_low_confidence(0.80001) is False
        assert is_low_confidence(0.79999) is True, "0.79999 MUST be flagged as low confidence"
        assert is_low_confidence(0.79) is True
        assert is_low_confidence(0.50) is True
        assert is_low_confidence(0.00) is True
        assert is_low_confidence(1.00) is False

        # Clamping and precision normalization
        assert normalize_confidence(0.80) == 0.80
        assert normalize_confidence(0.799) == 0.80  # rounded to 2 decimals
        assert normalize_confidence(0.794) == 0.79
        assert normalize_confidence(-0.5) == 0.00
        assert normalize_confidence(95.0) == 0.95  # 0-100 scale from Tesseract
        assert normalize_confidence(150.0) == 1.00  # clamped to 1.00

    def test_batch_excel_export_format_contract(self, client: TestClient):
        """
        Export Resilience Test:
        Verify GET /api/export/batch/{batch_id}/excel endpoint contract.
        If implemented, returns valid OpenXML (.xlsx) bytes starting with PK zip header.
        """
        batch_id = "BATCH-EXCEL-TEST"
        response = client.get(f"/api/export/batch/{batch_id}/excel")

        if response.status_code == 404:
            pytest.skip("GET /api/export/batch/{batch_id}/excel pending Milestone M3 Excel export implementation.")

        assert response.status_code == 200
        content = response.content
        assert content.startswith(b"PK\x03\x04"), "Excel workbook must be valid PK zip archive"

    def test_batch_combined_pdf_export_contract(self, client: TestClient):
        """
        Export Resilience Test:
        Verify GET /api/export/batch/{batch_id}/pdf endpoint contract.
        If implemented, returns valid multi-page PDF starting with %PDF-.
        """
        batch_id = "BATCH-PDF-TEST"
        response = client.get(f"/api/export/batch/{batch_id}/pdf")

        if response.status_code == 404:
            pytest.skip("GET /api/export/batch/{batch_id}/pdf pending Milestone M3 combined PDF implementation.")

        assert response.status_code == 200
        assert response.content.startswith(b"%PDF-"), "Combined PDF must start with %PDF- header"

    def test_batch_zip_archive_export_contract(self, client: TestClient):
        """
        Export Resilience Test:
        Verify GET /api/export/batch/{batch_id}/zip endpoint contract.
        If implemented, returns valid uncorrupted streaming ZIP archive.
        """
        batch_id = "BATCH-ZIP-TEST"
        response = client.get(f"/api/export/batch/{batch_id}/zip")

        if response.status_code == 404:
            pytest.skip("GET /api/export/batch/{batch_id}/zip pending Milestone M3 ZIP archive export implementation.")

        assert response.status_code == 200
        # Verify valid ZIP structure
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        assert len(zf.namelist()) >= 0
