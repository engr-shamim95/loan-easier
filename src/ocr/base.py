"""Base classes, dataclasses, and exceptions for OCR engines."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

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
