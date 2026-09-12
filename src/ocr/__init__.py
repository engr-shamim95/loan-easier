"""OCR module exports for Loan Easier."""

from src.ocr.base import (
    BaseOCREngine,
    OCRResult,
    FieldConfidence,
    TableCell,
    TableRow,
    BatchOCRResult,
    OCREngineError,
    GCPQuotaExceededError,
    GCPConnectionError,
    GCPAuthError,
    TesseractNotFoundError,
    AllOCREnginesFailedError,
)
from src.ocr.parser import (
    parse_loan_fields,
    normalize_confidence,
    is_low_confidence,
    to_arabic_digits,
    TableSpatialExtractor,
    parse_tabular_ocr,
)
from src.ocr.gcp_vision import GCPVisionEngine
from src.ocr.tesseract import TesseractEngine
from src.ocr.dual_engine import DualOCREngine

__all__ = [
    "BaseOCREngine",
    "OCRResult",
    "FieldConfidence",
    "TableCell",
    "TableRow",
    "BatchOCRResult",
    "OCREngineError",
    "GCPQuotaExceededError",
    "GCPConnectionError",
    "GCPAuthError",
    "TesseractNotFoundError",
    "AllOCREnginesFailedError",
    "parse_loan_fields",
    "normalize_confidence",
    "is_low_confidence",
    "to_arabic_digits",
    "TableSpatialExtractor",
    "parse_tabular_ocr",
    "GCPVisionEngine",
    "TesseractEngine",
    "DualOCREngine",
]
