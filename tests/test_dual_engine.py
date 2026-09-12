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

def test_dual_engine_tabular_primary_success():
    """Verify that extract_tabular invokes primary GCP engine and records telemetry when successful."""
    from src.ocr.base import BatchOCRResult, TableRow, TableCell

    primary = MagicMock(spec=BaseOCREngine)
    primary.name = "gcp_vision"
    cell = TableCell(value="LN-001", confidence=0.95)
    row = TableRow(
        row_index=1,
        serial_number=cell,
        name=TableCell(value="রফিকুল ইসলাম", confidence=0.92),
        mobile=TableCell(value="01711223344", confidence=0.95),
        address=TableCell(value="মিরপুর, ঢাকা", confidence=0.90),
        amount=TableCell(value=50000.0, confidence=0.96),
    )
    primary.extract_tabular.return_value = BatchOCRResult(
        batch_id="BATCH-001",
        rows=[row],
        total_rows=1,
        engine_name="gcp_vision",
    )

    fallback = MagicMock(spec=BaseOCREngine)
    fallback.name = "tesseract"

    engine = DualOCREngine(primary_engine=primary, fallback_engine=fallback)
    result = engine.extract_tabular(b"mock_tabular_bytes")

    assert isinstance(result, BatchOCRResult)
    assert result.engine_name == "gcp_vision"
    assert result.fallback_triggered is False
    assert result.fallback_reason is None
    assert result.total_rows == 1
    assert result.rows[0].serial_number.value == "LN-001"
    assert primary.extract_tabular.called
    assert not fallback.extract_tabular.called

def test_dual_engine_tabular_quota_failover():
    """Verify that extract_tabular catches GCP quota errors and automatically falls over to Tesseract."""
    from src.ocr.base import BatchOCRResult, TableRow, TableCell

    primary = MagicMock(spec=BaseOCREngine)
    primary.name = "gcp_vision"
    primary.extract_tabular.side_effect = GCPQuotaExceededError("GCP Vision quota exceeded (HTTP 429)")

    fallback = MagicMock(spec=BaseOCREngine)
    fallback.name = "tesseract"
    cell = TableCell(value="LN-001", confidence=0.88)
    row = TableRow(
        row_index=1,
        serial_number=cell,
        name=TableCell(value="মোসাঃ ফাতেমা", confidence=0.85),
        mobile=TableCell(value="01822334455", confidence=0.89),
        address=TableCell(value="উত্তরা, ঢাকা", confidence=0.84),
        amount=TableCell(value=75000.0, confidence=0.91),
    )
    fallback.extract_tabular.return_value = BatchOCRResult(
        batch_id="BATCH-FAILOVER",
        rows=[row],
        total_rows=1,
        engine_name="tesseract",
    )

    engine = DualOCREngine(primary_engine=primary, fallback_engine=fallback)
    result = engine.extract_tabular(b"mock_tabular_bytes")

    assert isinstance(result, BatchOCRResult)
    assert result.engine_name == "tesseract"
    assert result.fallback_triggered is True
    assert "429" in result.fallback_reason
    assert result.total_rows == 1
    assert primary.extract_tabular.called
    assert fallback.extract_tabular.called

def test_dual_engine_tabular_forced_fallback():
    """Verify that force_fallback=True routes extract_tabular directly to Tesseract."""
    from src.ocr.base import BatchOCRResult

    primary = MagicMock(spec=BaseOCREngine)
    primary.name = "gcp_vision"

    fallback = MagicMock(spec=BaseOCREngine)
    fallback.name = "tesseract"
    fallback.extract_tabular.return_value = BatchOCRResult(
        batch_id="BATCH-FORCED",
        rows=[],
        total_rows=0,
        engine_name="tesseract",
    )

    engine = DualOCREngine(primary_engine=primary, fallback_engine=fallback, force_fallback=True)
    result = engine.extract_tabular(b"mock_tabular_bytes")

    assert result.engine_name == "tesseract"
    assert result.fallback_triggered is True
    assert "OCR_FORCE_FALLBACK" in result.fallback_reason
    assert not primary.extract_tabular.called
    assert fallback.extract_tabular.called

def test_dual_engine_tabular_all_fail():
    """Verify AllOCREnginesFailedError when both engines fail during tabular extraction."""
    primary = MagicMock(spec=BaseOCREngine)
    primary.name = "gcp_vision"
    primary.extract_tabular.side_effect = GCPConnectionError("Timeout")

    fallback = MagicMock(spec=BaseOCREngine)
    fallback.name = "tesseract"
    fallback.extract_tabular.side_effect = RuntimeError("OCR crash")

    engine = DualOCREngine(primary_engine=primary, fallback_engine=fallback)
    with pytest.raises(AllOCREnginesFailedError) as exc_info:
        engine.extract_tabular(b"mock_tabular_bytes")

    assert "All OCR engines failed tabular extraction" in str(exc_info.value)

def test_tabular_mock_simulation_3_and_100_rows():
    """Verify deterministic mock simulation works for 3 rows and scales to 100 rows."""
    from src.ocr import GCPVisionEngine, TesseractEngine, DualOCREngine
    from tests.mock_tabular_fixtures import get_tabular_image_bytes

    # 1. Test standard 3-row image
    img_3 = get_tabular_image_bytes(num_rows=3)
    dual = DualOCREngine()
    res_3 = dual.extract_tabular(img_3)

    assert res_3.total_rows == 3
    assert len(res_3.rows) == 3
    for idx, row in enumerate(res_3.rows):
        assert row.row_index == idx + 1
        assert row.serial_number.value.startswith("LN-")
        assert len(row.name.value) > 0
        assert row.mobile.value.startswith("01")
        assert isinstance(row.amount.value, (int, float))
        assert row.amount.value > 0

    # 2. Test 100-row batch scale
    img_100 = get_tabular_image_bytes(num_rows=100)
    res_100 = dual.extract_tabular(img_100)

    assert res_100.total_rows == 100
    assert len(res_100.rows) == 100
    assert res_100.rows[99].serial_number.value == "LN-100"

def test_tabular_low_confidence_flagging():
    """Verify that cell confidence below 0.80 flags is_low_confidence=True on cell and row."""
    from src.ocr import DualOCREngine
    from tests.mock_tabular_fixtures import get_tabular_image_bytes

    img_low = get_tabular_image_bytes(num_rows=3, is_low_conf=True)
    dual = DualOCREngine()
    res = dual.extract_tabular(img_low)

    assert res.total_rows == 3
    # Row 2 was deliberately flagged with low confidence on mobile
    row_2 = res.rows[1]
    assert row_2.is_low_confidence is True
    assert row_2.mobile.is_low_confidence is True
    assert row_2.mobile.confidence < 0.80

    # Row 1 and Row 3 should have normal confidence
    assert res.rows[0].is_low_confidence is False
    assert res.rows[2].is_low_confidence is False

def test_bengali_numeral_translation_and_headers():
    """Verify Bengali numeral translation and Bengali column header matching."""
    from src.ocr.parser import to_arabic_digits, match_header_column, clean_mobile_cell, clean_amount_cell

    # Numeral translation
    assert to_arabic_digits("০১২৩৪৫৬৭৮৯") == "0123456789"
    assert to_arabic_digits("০১৭২২-৩৪৫৬৭৮") == "01722-345678"

    # Header synonyms
    assert match_header_column("ক্রমিক নং") == "serial_number"
    assert match_header_column("ক্রঃ নং") == "serial_number"
    assert match_header_column("নাম") == "name"
    assert match_header_column("ঋণ গ্রহীতার নাম") == "name"
    assert match_header_column("মোবাইল") == "mobile"
    assert match_header_column("মোবাইল নম্বর") == "mobile"
    assert match_header_column("ঠিকানা") == "address"
    assert match_header_column("বর্তমান ঠিকানা") == "address"
    assert match_header_column("পরিমাণ") == "amount"
    assert match_header_column("টাকার পরিমান") == "amount"

    # Cell cleaning with Bengali digits
    mob, conf = clean_mobile_cell("০১৭১২৩৪৫৬৭৮")
    assert mob == "01712345678"
    assert conf >= 0.90

    amt, conf = clean_amount_cell("৳৫০,০০০.০০/-")
    assert amt == 50000.0
    assert conf >= 0.95
