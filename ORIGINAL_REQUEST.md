# Original User Request

## 2026-09-12T04:32:28Z

Build a production-ready web application for OCR-based loan data entry featuring a Human-in-the-Loop (HITL) verification UI, dual OCR engines (GCP Vision with Tesseract fallback), and PDF/CSV export capabilities.

Working directory: C:\Users\Developer Shamim\teamwork_projects\loan_ocr_system
Integrity mode: benchmark

## Requirements

### R1. Document Ingestion & Dual OCR Processing
Accept image uploads containing loan data (serial number, name, mobile, address, amount). Process images primarily using Google Cloud Vision API. Implement an automatic fallback to local Tesseract OCR if GCP Vision API limits are reached or the service is unavailable.

### R2. Human-in-the-Loop Verification Interface
Provide a split-screen interface displaying the uploaded image alongside an editable form containing the extracted data. The interface must visually highlight fields with low OCR confidence scores to direct user attention for manual review.

### R3. Export and Persistence
Store verified loan records locally. Generate individual loan agreements as PDF documents. Export aggregated monthly loan records as CSV or Excel files.

## Acceptance Criteria

### E2E Functional Tests
- [ ] A test script uploads a mock image and simulates OCR extraction; verifies data populates the verification form correctly.
- [ ] A test script modifies a field in the mock verification form and verifies the updated data is saved locally.
- [ ] A test script triggers the fallback mechanism (mocking GCP failure) and verifies Tesseract OCR is invoked.
- [ ] A test script verifies PDF generation contains the expected verified fields.
- [ ] A test script verifies CSV export generates a valid file with all expected columns.

## 2026-09-12T06:42:29Z

Update the existing OCR loan system to support batch multi-row tabular extraction (up to 100 rows), replacing the single-form UI with an editable data grid for HITL verification.

Working directory: I:\Loan Easier
Integrity mode: benchmark

## Requirements

### R1. Tabular OCR Batch Extraction
Refactor the OCR backend (`src/ocr/`) to detect and parse tabular data formats. Extract multiple rows (up to 100) from a single image. The engine must support Bengali handwritten/printed text and Bengali column headers (ক্রমিক নং, নাম, মোবাইল, ঠিকানা, পরিমাণ).

### R2. Data Grid HITL UI
Update the frontend (`src/static/`) to display an interactive, editable data grid (table) alongside the image viewer. Each row corresponds to a loan record. Low-confidence cells must be visually highlighted. Users must be able to add, delete, and edit rows before saving.

### R3. Batch Persistence and Export
Update database logic to save multiple records atomically. Ensure CSV/Excel export works for the batch. Allow generating a combined PDF or a zip of individual PDFs for the batch.

## Acceptance Criteria

### E2E Functional Tests
- [ ] A test script uploads a mock tabular image with 3+ rows, verifies the backend returns an array of records.
- [ ] A test script modifies a specific cell in the mock data grid and verifies all rows are saved correctly to the database.
- [ ] A test script verifies the batch CSV export matches the table data.

