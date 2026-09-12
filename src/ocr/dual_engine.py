"""Dual OCR engine coordinating GCP Vision with automatic Tesseract fallback."""

import logging
import time
from typing import Optional

from src.config import OCR_FORCE_FALLBACK
from src.ocr.base import (
    BaseOCREngine,
    OCRResult,
    AllOCREnginesFailedError,
    GCPQuotaExceededError,
    GCPConnectionError,
    GCPAuthError,
)
from src.ocr.gcp_vision import GCPVisionEngine
from src.ocr.tesseract import TesseractEngine

logger = logging.getLogger("loan_ocr.dual_engine")

class DualOCREngine(BaseOCREngine):
    """
    Coordinates primary GCP Vision OCR with resilient, automatic fallback to Tesseract.
    Captures full audit telemetry on fallback state, engine used, and reason.
    """

    def __init__(
        self,
        primary_engine: Optional[BaseOCREngine] = None,
        fallback_engine: Optional[BaseOCREngine] = None,
        force_fallback: Optional[bool] = None,
    ) -> None:
        self.primary_engine = primary_engine or GCPVisionEngine()
        self.fallback_engine = fallback_engine or TesseractEngine()
        self.force_fallback = (
            force_fallback if force_fallback is not None else OCR_FORCE_FALLBACK
        )

    @property
    def name(self) -> str:
        return "dual_ocr_engine"

    def is_available(self) -> bool:
        return self.primary_engine.is_available() or self.fallback_engine.is_available()

    def extract(self, image_bytes: bytes) -> OCRResult:
        """
        Execute OCR extraction with automatic failover to Tesseract.
        """
        start_time = time.perf_counter()

        # Check if fallback is explicitly forced via config or environment
        if self.force_fallback:
            logger.info("OCR_FORCE_FALLBACK is active; routing directly to fallback engine.")
            try:
                result = self.fallback_engine.extract(image_bytes)
                result.fallback_triggered = True
                result.fallback_reason = "Manual override: OCR_FORCE_FALLBACK is enabled"
                result.engine_name = "tesseract"
                result.execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return result
            except Exception as e:
                logger.error(f"Fallback OCR engine failed under forced fallback: {e}")
                raise AllOCREnginesFailedError(f"Fallback engine failed: {e}") from e

        # Attempt primary engine (GCP Vision)
        logger.info(f"Invoking primary OCR engine: {self.primary_engine.name}")
        try:
            result = self.primary_engine.extract(image_bytes)
            result.fallback_triggered = False
            result.fallback_reason = None
            result.engine_name = self.primary_engine.name
            result.execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info("Primary OCR engine succeeded.")
            return result
        except (GCPQuotaExceededError, GCPConnectionError, GCPAuthError, Exception) as primary_exc:
            logger.warning(
                f"Primary OCR engine ({self.primary_engine.name}) failed: {primary_exc}. "
                f"Triggering automatic fallback to {self.fallback_engine.name}..."
            )
            # Invoke fallback engine (Tesseract)
            try:
                fallback_result = self.fallback_engine.extract(image_bytes)
                fallback_result.fallback_triggered = True
                fallback_result.fallback_reason = str(primary_exc)
                fallback_result.engine_name = "tesseract"
                fallback_result.execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
                logger.info(f"Fallback OCR engine ({self.fallback_engine.name}) succeeded.")
                return fallback_result
            except Exception as fallback_exc:
                logger.critical(f"Both primary and fallback OCR engines failed! Fallback error: {fallback_exc}")
                raise AllOCREnginesFailedError(
                    f"All OCR engines failed. Primary ({self.primary_engine.name}): {primary_exc}; "
                    f"Fallback ({self.fallback_engine.name}): {fallback_exc}"
                ) from fallback_exc
