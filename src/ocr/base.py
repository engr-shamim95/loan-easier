"""Base classes, dataclasses, and exceptions for OCR engines."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

class OCREngineError(Exception):
    """Base exception for all OCR engine errors."""
    pass

class GCPQuotaExceededError(OCREngineError):
    """Raised when Google Cloud Vision API quota limit (e.g. HTTP 429) is reached."""
    pass

class GCPConnectionError(OCREngineError):
    """Raised when Google Cloud Vision API network or connection timeout occurs."""
    pass

class GCPAuthError(OCREngineError):
    """Raised when Google Cloud Vision API credentials are missing or invalid."""
    pass

class TesseractNotFoundError(OCREngineError):
    """Raised when local Tesseract binary is not installed or not found on PATH."""
    pass

class AllOCREnginesFailedError(OCREngineError):
    """Raised when both primary and fallback OCR engines fail."""
    pass

@dataclass
class FieldConfidence:
    """Confidence metric and metadata for a single extracted field."""
    value: Any
    confidence: float  # Normalized strictly between 0.00 and 1.00
    is_low_confidence: bool = False  # True if confidence < 0.80
    engine: str = ""

@dataclass
class TableCell:
    """A single cell in a tabular OCR extraction."""
    value: Any = None
    raw_text: str = ""
    confidence: float = 1.0
    is_low_confidence: bool = False
    bounding_box: Optional[Dict[str, int]] = None
    manually_edited: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "raw_text": self.raw_text,
            "confidence": round(float(self.confidence), 2),
            "is_low_confidence": self.is_low_confidence,
            "bounding_box": self.bounding_box,
            "manually_edited": self.manually_edited,
        }

@dataclass
class TableRow:
    """A single row representing one loan applicant record in a table."""
    row_index: int
    serial_number: TableCell
    name: TableCell
    mobile: TableCell
    address: TableCell
    amount: TableCell
    overall_confidence: float = 1.0
    is_low_confidence: bool = False
    raw_text: str = ""
    bounding_box: Optional[Dict[str, int]] = None
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_index": self.row_index,
            "serial_number": self.serial_number.value,
            "name": self.name.value,
            "mobile": self.mobile.value,
            "address": self.address.value,
            "amount": self.amount.value,
            "confidences": {
                "serial_number": round(float(self.serial_number.confidence), 2),
                "name": round(float(self.name.confidence), 2),
                "mobile": round(float(self.mobile.confidence), 2),
                "address": round(float(self.address.confidence), 2),
                "amount": round(float(self.amount.confidence), 2),
            },
            "overall_confidence": round(float(self.overall_confidence), 2),
            "is_low_confidence": self.is_low_confidence,
            "verified": self.verified,
            "raw_text": self.raw_text,
            "bounding_box": self.bounding_box,
            "cells": {
                "serial_number": self.serial_number.to_dict(),
                "name": self.name.to_dict(),
                "mobile": self.mobile.to_dict(),
                "address": self.address.to_dict(),
                "amount": self.amount.to_dict(),
            },
        }

    def to_flat_dict(self) -> Dict[str, Any]:
        return self.to_dict()

@dataclass
class BatchOCRResult:
    """Standardized batch OCR extraction result for tabular loan documents."""
    batch_id: str = ""
    rows: List[TableRow] = field(default_factory=list)
    total_rows: int = 0
    engine_name: str = ""
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None
    execution_time_ms: float = 0.0
    raw_text: str = ""
    raw_ocr_data: Dict[str, Any] = field(default_factory=dict)
    detected_columns: List[str] = field(default_factory=list)
    is_tabular: bool = True

    def __post_init__(self):
        self._serial_number: Optional[str] = None
        self._name: Optional[str] = None
        self._mobile: Optional[str] = None
        self._address: Optional[str] = None
        self._amount: Optional[float] = None
        self._confidences: Optional[Dict[str, float]] = None
        if not self.total_rows and self.rows:
            self.total_rows = len(self.rows)

    @property
    def records(self) -> List[TableRow]:
        return self.rows

    @records.setter
    def records(self, val: List[TableRow]):
        self.rows = val
        self.total_rows = len(val)

    @property
    def serial_number(self) -> Optional[str]:
        if self._serial_number is not None:
            return self._serial_number
        return self.rows[0].serial_number.value if self.rows else None

    @serial_number.setter
    def serial_number(self, val: Optional[str]):
        self._serial_number = val

    @property
    def name(self) -> Optional[str]:
        if self._name is not None:
            return self._name
        return self.rows[0].name.value if self.rows else None

    @name.setter
    def name(self, val: Optional[str]):
        self._name = val

    @property
    def mobile(self) -> Optional[str]:
        if self._mobile is not None:
            return self._mobile
        return self.rows[0].mobile.value if self.rows else None

    @mobile.setter
    def mobile(self, val: Optional[str]):
        self._mobile = val

    @property
    def address(self) -> Optional[str]:
        if self._address is not None:
            return self._address
        return self.rows[0].address.value if self.rows else None

    @address.setter
    def address(self, val: Optional[str]):
        self._address = val

    @property
    def amount(self) -> Optional[float]:
        if self._amount is not None:
            return self._amount
        return self.rows[0].amount.value if self.rows else None

    @amount.setter
    def amount(self, val: Optional[float]):
        self._amount = val

    @property
    def confidences(self) -> Dict[str, float]:
        if self._confidences is not None:
            return self._confidences
        if not self.rows:
            return {}
        r0 = self.rows[0]
        return {
            "serial_number": round(float(r0.serial_number.confidence), 2),
            "name": round(float(r0.name.confidence), 2),
            "mobile": round(float(r0.mobile.confidence), 2),
            "address": round(float(r0.address.confidence), 2),
            "amount": round(float(r0.amount.confidence), 2),
        }

    @confidences.setter
    def confidences(self, val: Dict[str, float]):
        self._confidences = val

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_rows": self.total_rows,
            "engine_name": self.engine_name,
            "fallback_triggered": self.fallback_triggered,
            "fallback_reason": self.fallback_reason,
            "execution_time_ms": self.execution_time_ms,
            "raw_text": self.raw_text,
            "rows": [r.to_dict() for r in self.rows],
            "records": [r.to_dict() for r in self.rows],
            "detected_columns": self.detected_columns,
            "is_tabular": self.is_tabular,
        }

@dataclass
class OCRResult:
    """Standardized OCR extraction result for loan documents."""
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
    """Abstract base class for OCR engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine name identifier."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is configured and available in the current environment."""
        pass

    @abstractmethod
    def extract(self, image_bytes: bytes) -> OCRResult:
        """Extract text and loan fields from raw image bytes."""
        pass

    def extract_tabular(self, image_bytes: bytes) -> BatchOCRResult:
        """Extract tabular batch of loan records from image bytes."""
        return self.extract_batch(image_bytes)

    def extract_batch(self, image_bytes: bytes) -> BatchOCRResult:
        """Extract tabular batch of loan records from image bytes."""
        raise NotImplementedError("extract_batch is not implemented by this engine")
