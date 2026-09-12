# Test Infrastructure & E2E Validation Framework

**Project**: Loan Easier (OCR-Based Loan Data Entry System)  
**Author**: `test_writer_1` (E2E Test Engineer)  
**Status**: ACTIVE & COMPLETE  
**Integrity Mode**: Benchmark / Production  

---

## 1. Overview & Dual-Track Methodology

The test suite employs an **opaque-box, contract-driven dual-track testing methodology**. Tests are engineered strictly against the authoritative specifications defined in `ORIGINAL_REQUEST.md` and the architecture contracts in `PROJECT.md`.

Key architectural principles:
- **Opaque-Box Verification**: Tests validate the system primarily through HTTP endpoints via `fastapi.testclient.TestClient` and documented module interfaces (`DualOCREngine`, `LoanRepository`, `PDFGenerator`, `CSVExporter`).
- **Complete Test Isolation**: Each test operates in an ephemeral sandbox. SQLite databases are instantiated in pytest `tmp_path` fixtures, preventing data collision or side effects across runs.
- **Zero External Network Dependencies**: Deterministic synthetic mock images are generated locally using Pillow (`PIL`), simulating high-contrast loan documents, low-confidence documents, and corrupted streams without live cloud dependencies.
- **Strict Error and Fallback Verification**: Fault injection simulates Google Cloud Vision API quota limits (HTTP 429), timeouts, auth errors, and configuration switches (`OCR_FORCE_FALLBACK=true`), verifying that the Tesseract fallback engine activates and logs telemetry.

---

## 2. Acceptance Criteria & Test Matrix

| Acceptance Criteria | Test Module | Test Functions | Scope & Assertions |
|---|---|---|---|
| **AC1: Document Ingestion & Form Population** | `tests/test_ac1_ingestion_form.py` | `test_upload_mock_image_e2e_success`<br>`test_form_retrieval_matches_uploaded_data`<br>`test_jpeg_format_ingestion_success`<br>`test_ocr_field_parser_contract` | Verifies multipart image upload (`POST /api/documents/upload`), field extraction (`serial_number`, `name`, `mobile`, `address`, `amount`), and normalized confidence scores in `[0.00, 1.00]`. |
| **AC2: Form Modification & Persistence** | `tests/test_ac2_verification_save.py` | `test_modify_fields_and_verify_e2e_persistence`<br>`test_subsequent_get_reflects_updated_data`<br>`test_repository_atomic_update_and_verify` | Verifies HITL edits (`POST /api/loans/{id}/verify`), atomic persistence to SQLite, `verified=True` status, and ISO timestamp audit trail. |
| **AC3: Dual OCR Fallback Mechanism** | `tests/test_ac3_ocr_fallback.py` | `test_gcp_quota_exceeded_triggers_tesseract_fallback`<br>`test_gcp_connection_error_triggers_tesseract_fallback`<br>`test_gcp_auth_error_triggers_tesseract_fallback`<br>`test_force_fallback_configuration_flag`<br>`test_e2e_upload_with_ocr_force_fallback_env`<br>`test_both_engines_failing_raises_error` | Simulates GCP failures (quota 429, timeouts, credentials), confirms automatic failover to Tesseract, and verifies telemetry (`fallback_triggered=True`, `engine_name='tesseract'`). |
| **AC4: Loan Agreement PDF Generation** | `tests/test_ac4_pdf_generation.py` | `test_generate_pdf_endpoint_e2e`<br>`test_pdf_generator_unit_contract`<br>`test_pdf_generation_escapes_special_characters`<br>`test_nonexistent_loan_pdf_returns_404` | Validates `GET /api/loans/{id}/pdf`, verifies `%PDF-` header, extracts plain text via `pypdfium2`, and ensures all verified fields are present with XML escaping. |
| **AC5: Monthly Aggregated CSV Export** | `tests/test_ac5_csv_export.py` | `test_export_monthly_csv_e2e_valid_columns_and_format`<br>`test_rfc4180_escaping_quotes_and_commas`<br>`test_empty_monthly_csv_returns_headers_only`<br>`test_unverified_loans_excluded_from_export` | Validates `GET /api/export/csv?month=YYYY-MM`, verifies RFC 4180 compliance, header columns, data rows, quotes/commas escaping, and exclusion of draft records. |
| **Edge Cases & Boundaries** | `tests/test_edge_cases.py` | `test_zero_byte_upload_rejection`<br>`test_invalid_mime_type_rejection`<br>`test_corrupted_image_rejection`<br>`test_low_confidence_threshold_detection_boundary`<br>`test_low_confidence_fixture_detection_e2e`<br>`test_duplicate_serial_number_handling`<br>`test_negative_loan_amount_rejected` | Tests 0-byte upload rejection (HTTP 400/422), invalid MIME types (HTTP 415/422), corrupted files, strict `< 0.80` boundary evaluation, empty month exports, duplicate serials, and negative amounts. |
| **Dual OCR Engine Core** | `tests/test_dual_engine.py` | `test_dual_engine_primary_success`<br>`test_dual_engine_quota_failover`<br>`test_dual_engine_forced_fallback`<br>`test_dual_engine_all_fail` | Unit tests for DualOCREngine state transitions, failover triggers, and exception cascades. |
| **SQLite Persistence Core** | `tests/test_persistence.py` | `test_create_and_get_loan`<br>`test_update_and_verify`<br>`test_list_loans_by_month` | Unit tests for SQLite WAL transactions, serial lookups, and monthly queries. |

---

## 3. Test Fixture Architecture (`tests/fixtures/`)

Synthetic mock documents are generated dynamically and stored in `tests/fixtures/`:
1. **`clean_loan_document.png`**: High-contrast, clean 800x1000 PNG image containing full promissory agreement text, standard serial number (`LN-2026-9042`), name (`Jane Doe`), phone (`+1-555-234-5678`), address (`742 Evergreen Terrace`), and principal amount (`$25,000.00`).
2. **`clean_loan_document.jpg`**: JPEG version for format compatibility validation.
3. **`low_confidence_document.png`**: Rendered with `#F0F0F0` background to trigger low-confidence OCR simulation (`confidence < 0.80` on mobile/address) for HITL highlighting tests.
4. **`empty_file.png`**: 0-byte binary file for upload boundary testing.
5. **`invalid_file.txt`**: Plain text file pretending to be an image to verify MIME and magic bytes validation.
6. **`corrupted_image.png`**: PNG magic header followed by corrupt binary stream.

---

## 4. Pytest Configuration & Test Runner (`tests/conftest.py`)

- **Session Setup**: Automatically initializes fixtures in `tests/fixtures/` before running any test.
- **Isolated DB (`temp_db_path`)**: Creates a fresh SQLite database in pytest's temporary directory for every test invoking `loan_repo` or `client`.
- **Monkeypatching**: Seamlessly redirects `src.config.DB_PATH` and `src.db.repository.DB_PATH` to the isolated temporary database.
- **Test Client (`client`)**: Instantiates `fastapi.testclient.TestClient(app)` wrapped in a context manager for fast synchronous HTTP testing.

---

## 5. How to Run the Tests

### Run Full Test Suite
```powershell
python -m pytest tests/ -v
```

### Run Specific Acceptance Criteria
```powershell
# Run AC1 (Ingestion & Form Population)
python -m pytest tests/test_ac1_ingestion_form.py -v

# Run AC2 (Form Modification & SQLite Persistence)
python -m pytest tests/test_ac2_verification_save.py -v

# Run AC3 (Dual OCR Fallback & Telemetry)
python -m pytest tests/test_ac3_ocr_fallback.py -v

# Run AC4 (PDF Generation & Field Verification)
python -m pytest tests/test_ac4_pdf_generation.py -v

# Run AC5 (Monthly CSV Export & RFC 4180)
python -m pytest tests/test_ac5_csv_export.py -v

# Run Edge Cases & Boundary Scenarios
python -m pytest tests/test_edge_cases.py -v
```

### Run with Short Tracebacks and Detailed Summaries
```powershell
python -m pytest -q --tb=short
```
