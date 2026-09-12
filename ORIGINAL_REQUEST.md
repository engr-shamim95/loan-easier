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
