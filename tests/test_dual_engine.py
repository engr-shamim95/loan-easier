"""Unit tests for DualOCREngine failover logic, state transitions, and telemetry."""

import pytest
from unittest.mock import MagicMock
from src.ocr.base import (
    BaseOCREngine,
    OCRResult,
    GCPQuotaExceededError,
    GCPConnectionError,
    GCPAuthError,
    AllOCREnginesFailedError,
)
from src.ocr.dual_engine import DualOCREngine

def test_dual_engine_primary_success():
    """Verify that when primary GCP engine succeeds, fallback is not triggered."""
    primary = MagicMock(spec=BaseOCREngine)
    primary.name = "gcp_vision"
    primary.extract.return_value = OCRResult(
        serial_number="LN-PRIMARY-OK",
        name="John Doe",
        amount=10000.0,
        engine_name="gcp_vision",
    )

    fallback = MagicMock(spec=BaseOCREngine)
    fallback.name = "tesseract"

    engine = DualOCREngine(primary_engine=primary, fallback_engine=fallback)
    result = engine.extract(b"dummy_bytes")

    assert result.engine_name == "gcp_vision"
    assert result.fallback_triggered is False
    assert result.fallback_reason is None
    assert primary.extract.called
    assert not fallback.extract.called

def test_dual_engine_quota_failover():
    """Verify HTTP 429 quota exhaustion triggers fallback."""
    primary = MagicMock(spec=BaseOCREngine)
    primary.name = "gcp_vision"
    primary.extract.side_effect = GCPQuotaExceededError("HTTP 429 Resource Exhausted")

    fallback = MagicMock(spec=BaseOCREngine)
    fallback.name = "tesseract"
    fallback.extract.return_value = OCRResult(
        serial_number="LN-FALLBACK-OK",
        name="John Doe",
        amount=10000.0,
        engine_name="tesseract",
    )

    engine = DualOCREngine(primary_engine=primary, fallback_engine=fallback)
    result = engine.extract(b"dummy_bytes")

    assert result.engine_name == "tesseract"
    assert result.fallback_triggered is True
    assert "429" in result.fallback_reason
    assert primary.extract.called
    assert fallback.extract.called

def test_dual_engine_forced_fallback():
    """Verify force_fallback=True routes directly to fallback without touching primary."""
    primary = MagicMock(spec=BaseOCREngine)
    primary.name = "gcp_vision"

    fallback = MagicMock(spec=BaseOCREngine)
    fallback.name = "tesseract"
    fallback.extract.return_value = OCRResult(
        serial_number="LN-FORCED-OK",
        engine_name="tesseract",
    )

    engine = DualOCREngine(primary_engine=primary, fallback_engine=fallback, force_fallback=True)
    result = engine.extract(b"dummy_bytes")

    assert result.engine_name == "tesseract"
    assert result.fallback_triggered is True
    assert not primary.extract.called
    assert fallback.extract.called

def test_dual_engine_all_fail():
    """Verify AllOCREnginesFailedError when both engines raise exceptions."""
    primary = MagicMock(spec=BaseOCREngine)
    primary.name = "gcp_vision"
    primary.extract.side_effect = GCPConnectionError("Timeout")

    fallback = MagicMock(spec=BaseOCREngine)
    fallback.name = "tesseract"
    fallback.extract.side_effect = RuntimeError("Binary missing")

    engine = DualOCREngine(primary_engine=primary, fallback_engine=fallback)
    with pytest.raises(AllOCREnginesFailedError):
        engine.extract(b"dummy_bytes")
