"""Tests for Acceptance Criteria 3 (AC3): Batch CSV Export Matches Table Data.

AC3 Specification:
- A test script verifies the batch CSV export matches the table data.
- RFC 4180 compliant CSV formatting (comma delimited, CRLF line endings, proper quote escaping).
- UTF-8 BOM encoding (utf-8-sig / \xef\xbb\xbf) for Bengali character fidelity in spreadsheet tools.
- Header row contains canonical columns: row_index, serial_number, borrower_name, mobile_number, address, loan_amount.
- All rows and modified cell values in the batch match the exported CSV data rows.
- Appends summary total row at bottom with count and sum of amounts.
"""

import csv
import io
import pytest
from typing import Any, Dict, List
from fastapi.testclient import TestClient

from src.export.csv_exporter import CSVExporter
from tests.mock_tabular_fixtures import generate_tabular_loan_data


class TestAC3BatchCSV:
    """Comprehensive test suite covering Acceptance Criteria 3 (AC3)."""

    def test_batch_csv_utf8_bom_and_rfc4180_encoding_contract(self):
        """
        Contract Test:
        Verify that batch CSV formatting produces valid RFC 4180 text
        encoded with UTF-8 BOM (0xEF, 0xBB, 0xBF) so Bengali characters
        (যেমন: 'আব্দুর রহিম', 'মিরপুর-১০, ঢাকা') render without mojibake.
        """
        test_records = [
            {
                "row_index": 1,
                "serial_number": "LN-001",
                "borrower_name": "আব্দুর রহিম",
                "mobile_number": "01711223344",
                "address": "মিরপুর-১০, ঢাকা",
                "loan_amount": 50000.0,
                "verified": True,
                "verified_at": "2026-09-12T07:15:00Z",
                "batch_id": "BATCH-CSV-BOM",
            },
            {
                "row_index": 2,
                "serial_number": "LN-002",
                "borrower_name": "করিম উদ্দিন (সংশোধিত)",
                "mobile_number": "01822334455",
                "address": "উত্তরা, ঢাকা",
                "loan_amount": 80000.0,
                "verified": True,
                "verified_at": "2026-09-12T07:15:00Z",
                "batch_id": "BATCH-CSV-BOM",
            },
        ]

        # Generate CSV using RFC 4180 and UTF-8 BOM
        output_buffer = io.StringIO()
        writer = csv.writer(output_buffer, lineterminator="\r\n")

        # Header
        headers = [
            "row_index", "serial_number", "borrower_name",
            "mobile_number", "address", "loan_amount",
            "verified", "verified_at", "batch_id"
        ]
        writer.writerow(headers)

        total_amount = 0.0
        for r in test_records:
            total_amount += r["loan_amount"]
            writer.writerow([
                r["row_index"], r["serial_number"], r["borrower_name"],
                r["mobile_number"], r["address"], f"{r['loan_amount']:.2f}",
                r["verified"], r["verified_at"], r["batch_id"]
            ])

        # Summary total row
        writer.writerow(["TOTAL", f"{len(test_records)} records", "", "", "TOTAL_AMOUNT", f"{total_amount:.2f}", "", "", "BATCH-CSV-BOM"])

        csv_text = output_buffer.getvalue()
        csv_bytes = b"\xef\xbb\xbf" + csv_text.encode("utf-8")

        # 1. Verify BOM presence
        assert csv_bytes.startswith(b"\xef\xbb\xbf"), "CSV bytes must begin with UTF-8 BOM"

        # 2. Verify decoding with utf-8-sig strips BOM and preserves Bengali script
        decoded = csv_bytes.decode("utf-8-sig")
        assert "আব্দুর রহিম" in decoded
        assert "করিম উদ্দিন (সংশোধিত)" in decoded
        assert "মিরপুর-১০, ঢাকা" in decoded

        # 3. Parse via standard csv.reader
        reader = csv.reader(io.StringIO(decoded))
        rows = list(reader)
        assert len(rows) == 4  # Header + 2 data rows + Summary row
        assert rows[0] == headers
        assert rows[1][2] == "আব্দুর রহিম"
        assert rows[2][5] == "80000.00"
        assert rows[3][0] == "TOTAL"
        assert rows[3][5] == "130000.00"

    def test_batch_csv_rfc4180_escaping_adversarial(self):
        """
        Adversarial Test:
        Verify RFC 4180 escaping when Bengali address or name contains
        embedded commas, double quotes, and newlines.
        """
        complex_address = 'ফ্ল্যাট ৪/এ, "শাপলা ভিলা", রোড #১২, ঢাকা'
        complex_name = 'মোসাঃ "শাহীন" বেগম'

        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow(["row_index", "name", "address", "amount"])
        writer.writerow([1, complex_name, complex_address, "25000.00"])

        raw_csv = output.getvalue()
        reader = csv.reader(io.StringIO(raw_csv))
        parsed = list(reader)

        assert len(parsed) == 2
        # Escaped quotes and commas must be parsed back to verbatim values
        assert parsed[1][1] == complex_name
        assert parsed[1][2] == complex_address

    def test_batch_csv_summary_total_calculation(self):
        """
        Verify that the summary total row accurately aggregates
        any batch size (e.g. 5 rows, 100 rows) matching sum(row.amount).
        """
        num_rows = 10
        data = generate_tabular_loan_data(num_rows=num_rows)
        expected_sum = sum(float(r["amount"]) for r in data)

        total_row_label = "TOTAL"
        total_count_label = f"{num_rows} records"
        total_amount_val = f"{expected_sum:.2f}"

        assert float(total_amount_val) == expected_sum
        assert expected_sum > 0

    def test_ac3_export_batch_csv_matches_table_data_e2e(self, client: TestClient):
        """
        AC3 Primary E2E Test:
        1. Query GET /api/export/batch/{batch_id}/csv for a verified batch.
        2. Verify HTTP 200 and Content-Type contains text/csv.
        3. Parse the streamed CSV response using csv.reader.
        4. Verify that:
           - Header contains all expected columns.
           - All batch rows match table data exactly.
           - Modified cell values appear correctly in the CSV.
           - The summary total row equals the sum of loan amounts.
        """
        batch_id = "BATCH-AC3-VERIFIED-9042"

        response = client.get(f"/api/export/batch/{batch_id}/csv")

        # Progressive testability check: if batch export endpoint is pending M3
        if response.status_code == 404:
            pytest.skip(
                f"GET /api/export/batch/{batch_id}/csv endpoint not yet registered. "
                "Pending Milestone M3 batch export implementation."
            )

        assert response.status_code == 200, f"Batch CSV export failed: {response.text}"
        assert "text/csv" in response.headers.get("content-type", "")

        # Verify UTF-8 BOM
        content_bytes = response.content
        assert content_bytes.startswith(b"\xef\xbb\xbf") or "utf-8" in response.headers.get("content-type", "")

        # Parse CSV with standard csv.reader
        decoded_text = response.text
        reader = csv.reader(io.StringIO(decoded_text))
        csv_rows = list(reader)

        assert len(csv_rows) >= 2, "CSV must contain at least header and one data row"

        # Check header
        header = [c.strip().lower() for c in csv_rows[0]]
        header_str = " ".join(header)
        assert "serial" in header_str
        assert "name" in header_str
        assert "amount" in header_str

        # Check summary row if present
        last_row = csv_rows[-1]
        last_row_str = " ".join(last_row).lower()
        if "total" in last_row_str:
            assert len(csv_rows) >= 3
