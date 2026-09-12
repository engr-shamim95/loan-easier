# MASTER_INDEX: Loan OCR Data Entry System

## 1. Project Overview
This software is a Human-in-the-Loop (HITL) OCR-based data entry system for loan processing. It automates the extraction of handwritten or printed loan details (Serial Number, Borrower Name, Mobile Number, Address, Loan Amount) from uploaded images and allows human verification before saving.

## 2. Core Architecture
- **Backend Framework:** FastAPI (Python)
- **Database:** SQLite (WAL mode enabled for concurrent safety)
- **Frontend UI:** Single Page Application (SPA) served via FastAPI static mounts (HTML/CSS/JS). Features a split-screen design.
- **OCR Engine:** Dual OCR Pipeline (Google Cloud Vision API as primary, Tesseract OCR as local fallback).
- **Export Engine:** ReportLab Platypus (PDF generation) and RFC 4180 standard CSV exporter.

## 3. Key Features
- **Document Ingestion:** Accepts PNG, JPG, TIFF, BMP, WebP (up to 15MB) with magic-byte validation.
- **Dual OCR Pipeline:** Automatically falls back to Tesseract if GCP Vision fails (e.g., quota limits, network issues).
- **HITL Split-Screen UI:** 
  - Left Panel: Document viewer with pan, zoom, fit-to-view, and rotate capabilities.
  - Right Panel: Editable verification form.
- **Confidence Highlighting:** Fields with OCR confidence scores < 0.80 are visually highlighted (red/amber borders) to demand human review.
- **Data Persistence & Export:** Saves verified records atomically. Can export individual records as PDFs (loan agreements) and aggregated records as CSV/Excel files (monthly reports).

## 4. Directory Structure
```
i:\Loan Easier\
├── src/
│   ├── api/             # FastAPI routes (ingestion, verification, export)
│   ├── db/              # SQLite database schema, models, and repository layer
│   ├── ocr/             # Dual OCR engines and rule-based parser with confidence scoring
│   ├── export/          # PDF generator (ReportLab) and CSV exporter
│   └── static/          # Frontend assets (HTML, CSS, JS for split-screen UI)
├── tests/               # E2E Test Suite (73/73 tests passing)
│   ├── fixtures/        # Mock images and test payloads
│   └── ...              # AC1 to AC5 specific test files
├── data/                # Local SQLite database file (loan_records.db)
├── .agents/             # Agentic logs and victory audit reports (Sentinel)
├── user_manual_bn.md    # Bengali User Guide
└── MASTER_INDEX.md      # This file
```

## 5. System Workflows
### A. Ingestion Flow
`Upload Image -> Magic-Byte Check -> DualOCREngine -> Parser -> Return JSON with Confidence Scores`

### B. Verification Flow (HITL)
`UI receives JSON -> Renders Form & Image -> User reviews highlights (< 0.80) -> Edits fields -> Submits -> Repository saves to SQLite`

### C. Export Flow
`Repository queries SQLite -> Export Module formats data -> Returns PDF or CSV FileResponse`

## 6. Future Context for AI Agents
If you are an AI reading this in the future to debug or upgrade the system:
- **OCR Logic:** Start at `src/ocr/`. Modifying the parsing logic requires updating the confidence threshold calculations in `src/ocr/parser.py`.
- **UI Logic:** The split-screen UI is vanilla JS/HTML in `src/static/`. If React/Vue is needed in the future, rip out the static mount and build a separate frontend.
- **Database:** Ensure `WAL` mode remains enabled if concurrent users are introduced. Check `src/db/repository.py`.
- **Testing:** The system has an exhaustive E2E suite covering failure modes (e.g., Tesseract fallback mock). Always run `pytest tests/` after modifying core logic.
