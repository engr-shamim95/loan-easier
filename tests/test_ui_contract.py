"""Tests for Milestone M2: Data Grid HITL UI Contracts and Static Assets Integrity."""

import re
from pathlib import Path
import pytest


STATIC_DIR = Path(__file__).resolve().parent.parent / "src" / "static"


class TestM2UIContract:
    """Validates HTML structure, CSS rules, and JavaScript logic for Data Grid HITL UI."""

    @pytest.fixture
    def html_content(self) -> str:
        index_html = STATIC_DIR / "index.html"
        assert index_html.exists(), "src/static/index.html must exist"
        return index_html.read_text(encoding="utf-8")

    @pytest.fixture
    def css_content(self) -> str:
        styles_css = STATIC_DIR / "css" / "styles.css"
        assert styles_css.exists(), "src/static/css/styles.css must exist"
        return styles_css.read_text(encoding="utf-8")

    @pytest.fixture
    def js_content(self) -> str:
        app_js = STATIC_DIR / "js" / "app.js"
        assert app_js.exists(), "src/static/js/app.js must exist"
        return app_js.read_text(encoding="utf-8")

    def test_all_js_dom_element_ids_exist_in_html(self, html_content: str, js_content: str):
        """
        Verify that every document.getElementById('...') reference in app.js
        corresponds to an actual id attribute in index.html.
        """
        id_pattern = re.compile(r"document\.getElementById\(['\"]([^'\"]+)['\"]\)")
        js_ids = set(id_pattern.findall(js_content))
        assert len(js_ids) >= 30, f"Expected 30+ getElementById references, found {len(js_ids)}"

        missing_ids = []
        for elem_id in js_ids:
            if f'id="{elem_id}"' not in html_content and f"id='{elem_id}'" not in html_content:
                missing_ids.append(elem_id)

        assert not missing_ids, f"DOM element IDs referenced in app.js missing from index.html: {missing_ids}"

    def test_data_grid_table_columns_and_headers(self, html_content: str):
        """
        Verify table structure in index.html contains all 5 canonical fields
        plus SL and Actions in both English and Bengali script.
        """
        assert 'id="batch-grid-table"' in html_content
        assert 'id="batch-grid-tbody"' in html_content
        assert 'id="batch-grid-tfoot"' in html_content

        # SL / ক্রমিক
        assert "SL" in html_content and "ক্রমিক" in html_content
        # Name / নাম
        assert "Name" in html_content and "নাম" in html_content
        # Mobile / মোবাইল
        assert "Mobile" in html_content and "মোবাইল" in html_content
        # Address / ঠিকানা
        assert "Address" in html_content and "ঠিকানা" in html_content
        # Amount / পরিমাণ
        assert "Amount" in html_content and "পরিমাণ" in html_content
        # Actions / অ্যাকশন
        assert "Actions" in html_content or "অ্যাকশন" in html_content

    def test_live_summary_bar_and_metrics_elements(self, html_content: str):
        """
        Verify that index.html contains all summary bar elements:
        Total Records, Total Amount, Pending Review count, OCR engine badge.
        """
        assert 'id="batch-stat-records"' in html_content
        assert 'id="batch-stat-amount"' in html_content
        assert 'id="batch-stat-low-conf"' in html_content
        assert 'id="batch-engine-badge"' in html_content
        assert 'id="grid-footer-total-amount"' in html_content

    def test_dynamic_row_operation_buttons(self, html_content: str):
        """
        Verify presence of Add Row, Reset Batch, and Save & Verify Batch buttons.
        """
        assert 'id="btn-add-grid-row"' in html_content
        assert 'id="btn-save-batch"' in html_content
        assert 'id="btn-reset-batch"' in html_content

    def test_batch_export_buttons_present(self, html_content: str):
        """
        Verify export buttons for CSV, Excel, Combined PDF, and ZIP.
        """
        assert 'id="btn-export-batch-csv"' in html_content
        assert 'id="btn-export-batch-excel"' in html_content
        assert 'id="btn-export-batch-pdf"' in html_content
        assert 'id="btn-export-batch-zip"' in html_content

    def test_dual_mode_tabs_and_views_present(self, html_content: str):
        """
        Verify both views (single-record-view and batch-grid-view) and mode switch tabs exist.
        """
        assert 'id="single-record-view"' in html_content
        assert 'id="batch-grid-view"' in html_content
        assert 'id="tab-batch-grid"' in html_content
        assert 'id="tab-single-form"' in html_content
        assert 'id="btn-quick-sample-tabular"' in html_content

    def test_css_low_confidence_and_edited_rules(self, css_content: str):
        """
        Verify css rules for cell-low-confidence (<0.80), cell-edited,
        warning badges, and scrollable data grid table.
        """
        assert ".cell-low-confidence" in css_content
        assert ".cell-edited" in css_content
        assert ".cell-badge-low" in css_content
        assert ".cell-badge-edited" in css_content
        assert ".grid-scroll-wrapper" in css_content
        assert ".data-grid-table" in css_content
        assert ".btn-delete-row" in css_content
        assert ".batch-summary-cards" in css_content

    def test_js_functions_and_contract_methods(self, js_content: str):
        """
        Verify app.js defines the key batch functions.
        """
        required_functions = [
            "populateBatchGrid",
            "renderBatchGrid",
            "handleGridCellInput",
            "handleAddGridRow",
            "handleDeleteGridRow",
            "updateBatchSummary",
            "handleSaveBatch",
            "handleResetBatchGrid",
            "handleBatchExportCsv",
            "handleBatchExportExcel",
            "handleBatchExportPdf",
            "handleBatchExportZip",
            "handleQuickSampleTabular",
            "switchMode",
        ]
        for fn in required_functions:
            assert fn in js_content, f"Function '{fn}' must be defined in app.js"

    def test_js_confidence_threshold_and_reset_on_edit(self, js_content: str):
        """
        Verify confidence threshold is 0.80 and that editing a cell sets confidence to 1.00.
        """
        assert "confidenceThreshold: 0.80" in js_content or "confidenceThreshold = 0.80" in js_content
        assert "row.confidences[field] = 1.00" in js_content
        assert "cell-low-confidence" in js_content
        assert "cell-edited" in js_content
