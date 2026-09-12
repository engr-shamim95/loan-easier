# Test Infrastructure & E2E Validation Framework: Batch Multi-Row Tabular OCR

**Project**: Loan Easier (OCR-Based Loan Data Entry System)  
**Author**: `test_writer_e2e_2` (E2E Test Writer)  
**Version**: 2.0.0  
**Status**: ACTIVE & COMPLETE (Tiers 1-4 Ready)  
**Integrity Mode**: Benchmark / Production  

---

## 1. Overview & Multi-Tier Testing Architecture

The test infrastructure validates the **Batch Multi-Row Tabular OCR and Human-in-the-Loop (HITL) Data Grid** system across 4 distinct testing tiers. Tests are engineered strictly against the authoritative requirements in `ORIGINAL_REQUEST.md` (Update 2026-09-12T06:42:29Z) and the architectural specifications in `PROJECT.md`.

### The 4 Testing Tiers:
- **Tier 1: Unit & Spatial Parser Contracts**: Validates 2D token normalization, table boundary detection, row clustering, horizontal column partitioning, cell confidence normalization in `[0.00, 1.00]`, and Bengali numeral translation (`০-৯` to `0-9`).
- **Tier 2: Component & Dual OCR Integration**: Validates tabular batch extraction failover between primary GCP Vision and Tesseract, preserving full execution telemetry (`fallback_triggered`, `fallback_reason`, `engine_name`).
- **Tier 3: E2E Acceptance Criteria (AC1, AC2, AC3)**:
  - **AC1** (`tests/test_ac1_tabular_extraction.py`): Tabular document image upload (3+ rows) verifying backend returns an array of structured records.
  - **AC2** (`tests/test_ac2_grid_save.py`): In-grid cell modification and atomic SQLite batch save/verification (`BEGIN IMMEDIATE ... COMMIT;` with rollback).
  - **AC3** (`tests/test_ac3_batch_csv.py`): Streamed batch CSV export matching table data with RFC 4180 compliance, UTF-8 BOM encoding for Bengali, and summary total row.
- **Tier 4: Boundary, Capacity & Adversarial Stress**: Validates 100 rows maximum batch capacity, exhaustive Bengali numeral conversion matrices, Bengali column header synonyms, strict `< 0.80` cell threshold boundaries, and multi-format exports (Excel `.xlsx`, Combined PDF, ZIP archive).

---

## 2. Acceptance Criteria & Test Matrix

| Criteria / Tier | Test Module | Test Functions | Scope & Assertions |
|---|---|---|---|
| **AC1: Tabular Extraction (3+ rows)** | `tests/test_ac1_tabular_extraction.py` | `test_mock_tabular_image_generation_3_plus_rows`<br>`test_spatial_table_extractor_contract_3_rows`<br>`test_tabular_parser_with_bengali_text_lines`<br>`test_low_confidence_cell_flagging_in_batch`<br>`test_ac1_upload_tabular_image_e2e` | Uploads mock tabular image with 3+ rows (`POST /api/documents/upload`), verifies backend returns an array of records with `serial_number`, `name`, `mobile`, `address`, `amount`, normalized cell confidences in `[0.00, 1.00]`, and draft status. |
| **AC2: Data Grid Save & Atomic DB** | `tests/test_ac2_grid_save.py` | `test_grid_cell_edit_state_transition_contract`<br>`test_sqlite_atomic_transaction_rollback_guarantee`<br>`test_dynamic_row_add_and_delete_in_grid_payload`<br>`test_ac2_modify_cell_and_verify_atomic_persistence_e2e` | Simulates inline cell edit in mock data grid, verifies all rows are committed atomically to SQLite with `verified = True` and ISO timestamp. Injects constraint violations to guarantee zero partial commits on failure (`ROLLBACK;`). |
| **AC3: Batch CSV Export Match** | `tests/test_ac3_batch_csv.py` | `test_batch_csv_utf8_bom_and_rfc4180_encoding_contract`<br>`test_batch_csv_rfc4180_escaping_adversarial`<br>`test_batch_csv_summary_total_calculation`<br>`test_ac3_export_batch_csv_matches_table_data_e2e` | Requests `GET /api/export/batch/{batch_id}/csv`, parses via `csv.reader`, verifies UTF-8 BOM (`\xef\xbb\xbf`), matches all columns and cell edits with table data, and verifies summary total row. |
| **Tier 4: Stress & Boundaries** | `tests/test_tabular_stress_boundaries.py` | `test_tabular_100_rows_maximum_capacity_stress`<br>`test_bengali_numeral_exhaustive_translation_matrix`<br>`test_bengali_column_headers_exhaustive_synonyms`<br>`test_low_confidence_cell_thresholding_strict_boundary`<br>`test_batch_excel_export_format_contract`<br>`test_batch_combined_pdf_export_contract`<br>`test_batch_zip_archive_export_contract` | Validates 100 rows batch capacity under 3.0s, exhaustive Bengali numeral conversion (`০-৯` -> `0-9`), Bengali header synonyms (`ক্রমিক নং`, `নাম`, `মোবাইল`, `ঠিকানা`, `পরিমাণ`), strict `< 0.80` boundary evaluation, and export format resilience. |
| **Single-Form Ingestion (Legacy AC1)** | `tests/test_ac1_ingestion_form.py` | Full suite (4 tests) | Preserves backwards compatibility for single-record image uploads and field parsers. |
| **Single-Form Verification (Legacy AC2)** | `tests/test_ac2_verification_save.py` | Full suite (3 tests) | Preserves single-record verification persistence via `POST /api/loans/{id}/verify`. |
| **OCR Failover (Legacy AC3)** | `tests/test_ac3_ocr_fallback.py` | Full suite (6 tests) | Simulates GCP failures (quota 429, timeouts, credentials) triggering Tesseract fallback. |
| **Single-Loan PDF (Legacy AC4)** | `tests/test_ac4_pdf_generation.py` | Full suite (4 tests) | Validates single-loan agreement PDF generation and entity escaping. |
| **Monthly CSV Export (Legacy AC5)** | `tests/test_ac5_csv_export.py` | Full suite (4 tests) | Validates monthly aggregated CSV export `GET /api/export/csv?month=YYYY-MM`. |
| **Adversarial & Edge Cases** | `tests/test_edge_cases.py` | Full suite (7 tests) | Validates 0-byte uploads, corrupted streams, invalid MIME types, negative amounts. |
| **Dual Engine Tabular** | `tests/test_dual_engine.py` | Full suite (11 tests) | Validates primary, failover, forced fallback, and tabular mock extraction. |
| **Concurrency & Stress** | `tests/test_stress_scenarios.py` | Full suite (20 tests) | High concurrency stress, truncated byte payloads, and WAL race condition checks. |
| **Export Integrity** | `tests/test_challenger_export_integrity.py` | Full suite (18 tests) | Validates RFC 4180 escaping, financial totals, and leap-year boundaries. |

---

## 3. Test Fixture Architecture (`tests/mock_tabular_fixtures.py` & `tests/fixtures/`)

1. **`create_mock_tabular_image(rows_data, headers, ...)`**: Generates high-resolution tabular document images with grid lines, Bengali headers (`ক্রমিক নং`, `নাম`, `মোবাইল`, `ঠিকানা`, `পরিমাণ`), and structured rows (scaling from 3 up to 100 rows).
2. **`get_tabular_image_bytes(num_rows, is_low_conf)`**: Returns binary bytes of synthetic tabular images for upload simulation.
3. **`generate_mock_tabular_tokens(num_rows, low_conf_row, base_conf)`**: Generates realistic 2D OCR word tokens with bounding boxes `(text, x, y, w, h, confidence)` for spatial extractor validation.
4. **`tabular_loan_document_3rows.png`**: Standard 3-row tabular document fixture persisted on disk.
5. **`tabular_loan_document_low_conf.png`**: Tabular fixture with background `#F0F0F0` and blurred cell triggering low confidence (`< 0.80`) on Row 2 mobile.

---

## 4. Pytest Configuration & Fixtures (`tests/conftest.py`)

- **`mock_tabular_3rows_bytes`**: Fixture providing raw binary bytes of a 3-row tabular image.
- **`mock_tabular_low_conf_bytes`**: Fixture providing bytes of a tabular image with low-confidence cells.
- **`sample_tabular_data`**: Fixture returning standardized 3-row tabular loan dictionaries.
- **`temp_db_path`**: Ephemeral SQLite database sandbox per test in `tmp_path`.
- **`loan_repo`**: Isolated `LoanRepository` pointing to the ephemeral SQLite database.
- **`client`**: Synchronous FastAPI `TestClient` wrapped in context manager.

---

## 5. How to Run the Tests

### Run Full Test Suite
```powershell
python -m pytest -v
```

### Run Batch Tabular E2E Acceptance Criteria
```powershell
# AC1: Tabular OCR Batch Extraction (3+ rows)
python -m pytest tests/test_ac1_tabular_extraction.py -v

# AC2: Data Grid Cell Modification & Atomic Save
python -m pytest tests/test_ac2_grid_save.py -v

# AC3: Batch CSV Export Matches Table Data
python -m pytest tests/test_ac3_batch_csv.py -v

# Tier 4: 100 Rows Stress, Bengali Numerals, Low Confidence
python -m pytest tests/test_tabular_stress_boundaries.py -v
```

### Run All Tabular Tests Together
```powershell
python -m pytest tests/test_ac1_tabular_extraction.py tests/test_ac2_grid_save.py tests/test_ac3_batch_csv.py tests/test_tabular_stress_boundaries.py -v
```
