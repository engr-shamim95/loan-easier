# Project: OCR-Based Loan Data Entry Production System

## Architecture
The application is a production-ready, full-stack web application for automated loan document ingestion, optical character recognition (OCR) with automatic multi-engine failover, Human-in-the-Loop (HITL) split-screen verification, and automated export (PDF loan agreements & monthly aggregated CSV/Excel reports).

### Data Flow
1. **Document Ingestion**: Client uploads a loan document image (PNG, JPEG, TIFF, BMP, WebP) via `POST /api/documents/upload`.
2. **Dual OCR Extraction**:
   - `DualOCREngine` dispatches to `GCPVisionEngine` (primary).
   - If GCP Vision encounters errors (HTTP 429 quota, connection timeout, missing credentials, HTTP 500/503), it triggers automatic fallback to `TesseractEngine`.
   - Raw text is parsed by `FieldParser` into 5 structured fields: `serial_number`, `name`, `mobile`, `address`, `amount`.
   - Confidences are normalized strictly to `[0.00, 1.00]`. Fields with confidence `< 0.80` are flagged with `is_low_confidence = True`.
3. **Draft Record Creation**: Record stored in local SQLite database with `verified = False` and full OCR telemetry.
4. **HITL Split-Screen UI**:
   - Left Pane: Interactive document viewer with pan and zoom.
   - Right Pane: Verification form pre-filled with extracted data, highlighting low-confidence fields in warning colors.
5. **Human Verification & Persistence**: User reviews and modifies fields as needed; clicking "Verify & Save" updates SQLite (`verified = True`, `verified_at = timestamp`, `manually_edited = True`).
6. **Export**:
   - `GET /api/loans/{id}/pdf`: Generates formal legal loan agreement PDF via ReportLab.
   - `GET /api/export/csv?month=YYYY-MM`: Generates RFC 4180 compliant CSV of all verified loans for the month with summary totals.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Document Upload Endpoint | Accepts loan document image files via HTTP POST multipart form | M1 | survey (spec_miner_req_1) |
| 2 | File Type & Integrity Validation | Verifies image MIME type, magic bytes (PNG, JPEG, TIFF, BMP, WebP), 15MB size limit | M1 | survey (spec_miner_req_1) |
| 3 | Serial Number Extraction & Validation | Regex extraction and normalization (`^[A-Za-z0-9\-_]{4,30}$`) | M1 | survey (spec_miner_req_1) |
| 4 | Borrower Name Extraction & Validation | Cleans and validates full borrower legal name (`^[A-Za-z]+([ '-][A-Za-z]+)+$`) | M1 | survey (spec_miner_req_1) |
| 5 | Mobile Number Extraction & Validation | Standardizes phone number to 10-15 digits | M1 | survey (spec_miner_req_1) |
| 6 | Address Extraction & Validation | Extracts and normalizes residential/mailing address (5-250 chars) | M1 | survey (spec_miner_req_1) |
| 7 | Loan Amount Extraction & Normalization | Normalizes currency to positive float with 2 decimals | M1 | survey (spec_miner_req_1) |
| 8 | Primary GCP Vision Engine | Calls Google Cloud Vision API with confidence extraction and error categorization | M1 | survey (spec_miner_req_1) |
| 9 | Automatic Tesseract Fallback Engine | Local Tesseract OCR invocation with normalized confidences | M1 | survey (spec_miner_req_1) |
| 10 | Fallback Trigger & State Machine | Triggers Tesseract on 429 quota, server errors, missing credentials, timeouts | M1 | survey (spec_miner_req_1) |
| 11 | Field Confidence Calculation | Computes normalized 0.00-1.00 float confidence per field | M1 | survey (spec_miner_req_1) |
| 12 | Low-Confidence Threshold Detection | Strict threshold `confidence < 0.80` marking `is_low_confidence = True` | M1 | survey (spec_miner_req_1) |
| 13 | HITL Split-Screen Layout | Responsive 50/50 side-by-side split screen on desktop | M2 | survey (spec_miner_req_1) |
| 14 | HITL Interactive Document Viewer | Pan, zoom in/out, fit to view, and rotate controls | M2 | survey (spec_miner_req_1) |
| 15 | HITL Low-Confidence Highlighting | Warning badges and high-contrast amber/red border styling for `< 0.80` | M2 | survey (spec_miner_req_1) |
| 16 | HITL Manual Edit & Override | In-place editing of fields marking `manually_edited: true` and persisting changes | M1, M2 | survey (spec_miner_req_1) |
| 17 | Local SQLite Storage & Persistence | Schema with WAL mode, transactions, JSON confidences, audit timestamps | M1 | survey (spec_miner_req_1) |
| 18 | Document Image Archiving | Stores uploaded document scans in `data/uploads/` with safe naming | M1 | survey (spec_miner_req_1) |
| 19 | Single Loan Agreement PDF Export | ReportLab PDF generation with agreement terms, borrower info, signatures | M1 | survey (spec_miner_req_1) |
| 20 | Monthly Aggregated CSV Export | RFC 4180 CSV export filterable by `YYYY-MM` with column totals | M1 | survey (spec_miner_req_1) |
| 21 | Monthly Aggregated Excel Export | Excel workbook generation (`.xlsx`) with openpyxl/csv fallback | M1 | survey (spec_miner_req_1) |
| 22 | OCR Simulation & Mock Ingestion | Deterministic mock engine for offline testing of AC1 & AC2 | M1, E2E | survey (spec_miner_req_1) |
| 23 | GCP Failure Mocking Switch | Environment variable / flag to force GCP failure to test fallback (AC3) | M1, E2E | survey (spec_miner_req_1) |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Suite | Test harness, mock fixtures, Tiers 1-4 covering all 5 Acceptance Criteria, TEST_READY.md | none | DONE |
| M1 | Backend Core, Dual OCR Fallback Engine, Persistence & Export API | Dependencies, SQLite WAL DB, models, LoanRepository, DualOCREngine (GCP + Tesseract fallback), FieldParser, PDFGenerator, CSVExporter, FastAPI REST API | none | DONE |
| M2 | Split-Screen HITL Verification Web UI | Responsive split-screen UI (HTML5/CSS3/ES6), image viewer with pan/zoom, visual confidence badges (< 0.80 highlight), edit form & save integration | M1 | DONE |
| M3 | Final Milestone: 100% E2E Pass, Adversarial Hardening & Audit | Full verification of all 5 acceptance criteria, 73/73 tests passing, forensic audit CLEAN | E2E, M2 | DONE |

---

## Interface Contracts

### OCR Engine Contract (`src/ocr/base.py`)
```python
@dataclass
class OCRResult:
    serial_number: Optional[str] = None
    name: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    amount: Optional[float] = None
    confidences: Dict[str, float] = field(default_factory=dict)
    raw_text: str = ""
    raw_ocr_data: Dict[str, Any] = field(default_factory=dict)
    engine_name: str = ""
    execution_time_ms: float = 0.0
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None

class BaseOCREngine(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass
    @abstractmethod
    def is_available(self) -> bool: pass
    @abstractmethod
    def extract(self, image_bytes: bytes) -> OCRResult: pass
```

### Persistence Contract (`src/db/repository.py`)
```python
class LoanRepository:
    def create_loan(self, loan: LoanCreate) -> LoanRecord: ...
    def get_loan_by_id(self, loan_id: int) -> Optional[LoanRecord]: ...
    def get_loan_by_serial(self, serial_number: str) -> Optional[LoanRecord]: ...
    def update_and_verify_loan(self, loan_id: int, update_data: LoanUpdate) -> LoanRecord: ...
    def list_loans_by_month(self, year_month: str, verified_only: bool = True) -> List[LoanRecord]: ...
```

### Export Contracts (`src/export/`)
```python
class PDFGenerator:
    def generate_loan_agreement(self, loan: LoanRecord) -> bytes: ...

class CSVExporter:
    def export_monthly_csv(self, loans: List[LoanRecord]) -> str: ...
    def export_monthly_excel(self, loans: List[LoanRecord]) -> bytes: ...
```

### REST API Endpoints (`src/api/`)
- `POST /api/documents/upload`: Multipart upload -> returns extracted `OCRResult` and draft `loan_id`.
- `GET /api/loans/{id}`: Fetches loan record with confidences and image URL.
- `POST /api/loans/{id}/verify`: Submits verified/edited fields -> saves to DB (`verified = True`).
- `GET /api/loans/{id}/pdf`: Returns `application/pdf` binary download of the agreement.
- `GET /api/export/csv?month=YYYY-MM`: Returns RFC 4180 CSV attachment.
- `GET /`: Serves the split-screen HITL UI.

---

## Code Layout
```
i:\Loan Easier\
├── data/
│   ├── loan_records.db             # Local SQLite database
│   └── uploads/                    # Uploaded document scans
├── src/
│   ├── __init__.py
│   ├── config.py                   # Configuration, low-confidence threshold (< 0.80)
│   ├── ocr/
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseOCREngine, OCRResult dataclasses
│   │   ├── parser.py               # Field regex extraction and normalization
│   │   ├── gcp_vision.py           # GCPVisionEngine (API client + mock simulation)
│   │   ├── tesseract.py            # TesseractEngine (pytesseract + local binary)
│   │   └── dual_engine.py          # DualOCREngine with failover & metadata
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py           # SQLite connection with WAL mode
│   │   ├── schema.py               # DDL schema initialization
│   │   ├── models.py               # Pydantic schemas and dataclasses
│   │   └── repository.py           # LoanRepository CRUD operations
│   ├── export/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py        # ReportLab PDF Agreement generator
│   │   └── csv_exporter.py         # Monthly CSV/Excel aggregator
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py                  # FastAPI application factory
│   │   ├── routes_ocr.py           # Document upload & OCR trigger routes
│   │   ├── routes_loans.py         # Loan verification, update, and retrieval
│   │   └── routes_export.py        # PDF and CSV download routes
│   └── static/
│       ├── index.html              # Split-screen HITL interface
│       ├── css/styles.css          # Split-screen styling & confidence badges
│       └── js/app.js               # Pan/zoom viewer, form bindings, verification
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Test fixtures, mock engines, TestClient
│   ├── test_ac1_ingestion_form.py  # AC1: Mock image upload & form population
│   ├── test_ac2_verification_save.py # AC2: Modify field & verify DB persistence
│   ├── test_ac3_ocr_fallback.py    # AC3: GCP failure triggers Tesseract fallback
│   ├── test_ac4_pdf_generation.py  # AC4: PDF agreement contains verified fields
│   ├── test_ac5_csv_export.py      # AC5: Valid monthly CSV with expected columns
│   ├── test_dual_engine.py         # Unit tests for DualOCREngine
│   ├── test_persistence.py        # Unit tests for SQLite repository
│   ├── test_stress_scenarios.py    # Stress & concurrency test suite (Challenger 1)
│   └── test_challenger_export_integrity.py # Export integrity test suite (Challenger 2)
├── requirements.txt                # Production & test dependencies
├── run_server.py                   # Startup script for local running
├── PROJECT.md                      # Authoritative project index
├── TEST_INFRA.md                   # E2E test suite index
└── TEST_READY.md                   # Published when E2E suite is ready
```
