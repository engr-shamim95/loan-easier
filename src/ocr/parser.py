"""Field extraction and confidence normalization for loan documents."""

import re
from typing import Any, Dict, Optional, Tuple
from src.config import CONFIDENCE_THRESHOLD

# Regex patterns for matching labels and values
SERIAL_LABEL_PATTERN = re.compile(
    r"(?:serial\s*(?:number|no\.?|#)?|loan\s*(?:id|no\.?|#|number|ref(?:erence)?)|app(?:lication)?\s*(?:id|no\.?|#)|ref(?:erence)?\s*(?:no\.?|#)?)\s*[:=\-]\s*([A-Za-z0-9\-_]{4,30})",
    re.IGNORECASE,
)
SERIAL_FALLBACK_PATTERN = re.compile(
    r"\b([A-Z]{2,4}[-_][0-9]{4,10}|[A-Z]{2,4}[0-9]{6,10})\b"
)

NAME_LABEL_PATTERN = re.compile(
    r"(?:borrower\s*(?:name)?|applicant\s*(?:name)?|customer\s*(?:name)?|client\s*(?:name)?|full\s*name|name)\s*[:=\-]\s*([A-Za-z]+(?:[ '\-][A-Za-z]+)+)",
    re.IGNORECASE,
)

PHONE_LABEL_PATTERN = re.compile(
    r"(?:mobile\s*(?:number|no\.?|#)?|phone\s*(?:number|no\.?|#)?|contact\s*(?:no\.?|#)?|cell(?:ular)?|tel(?:ephone)?)\s*[:=\-]\s*(\+?[0-9\s\(\)\-\.]{10,25})",
    re.IGNORECASE,
)
PHONE_DIGITS_PATTERN = re.compile(r"\+?[1-9]\d{1,14}|\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}")

ADDRESS_LABEL_PATTERN = re.compile(
    r"(?:residential\s*address|mailing\s*address|borrower\s*address|street\s*address|address)\s*[:=\-]\s*([^\n\r]{5,250})",
    re.IGNORECASE,
)

AMOUNT_LABEL_PATTERN = re.compile(
    r"(?:loan\s*amount|principal\s*(?:amount)?|amount\s*(?:approved|sanctioned)?|principal|amount)\s*[:=\-]\s*\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
AMOUNT_CURRENCY_PATTERN = re.compile(
    r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)"
)

def normalize_confidence(score: float) -> float:
    """Normalize confidence score strictly to float [0.00, 1.00] with 2 decimal precision."""
    if score is None:
        return 0.00
    # If passed as 0-100 scale (e.g. from Tesseract)
    if score > 1.0:
        score = score / 100.0
    # Clamp to [0.00, 1.00]
    score = max(0.00, min(1.00, float(score)))
    return round(score, 2)

def is_low_confidence(confidence: float) -> bool:
    """Strictly evaluate if confidence score is below threshold (< 0.80)."""
    return float(confidence) < CONFIDENCE_THRESHOLD

def extract_serial_number(text: str) -> Tuple[Optional[str], float]:
    """Extract serial / loan identifier and calculate confidence."""
    match = SERIAL_LABEL_PATTERN.search(text)
    if match:
        val = match.group(1).strip()
        if re.match(r"^[A-Za-z0-9\-_]{4,30}$", val):
            return val, 0.95
        return val, 0.70

    fallback = SERIAL_FALLBACK_PATTERN.search(text)
    if fallback:
        val = fallback.group(1).strip()
        return val, 0.75

    return None, 0.00

def extract_name(text: str) -> Tuple[Optional[str], float]:
    """Extract borrower name and calculate confidence."""
    match = NAME_LABEL_PATTERN.search(text)
    if match:
        raw_name = match.group(1).strip()
        # Clean unwanted trailing punctuation or words
        cleaned = re.sub(r"[\r\n\t]+", " ", raw_name).strip()
        parts = cleaned.split()
        if len(parts) >= 2 and all(p.isalpha() or "'" in p or "-" in p for p in parts):
            return cleaned, 0.94
        elif len(parts) >= 1:
            return cleaned, 0.65
        return cleaned, 0.50

    return None, 0.00

def extract_mobile(text: str) -> Tuple[Optional[str], float]:
    """Extract mobile number, normalize to standard phone digits, and calculate confidence."""
    match = PHONE_LABEL_PATTERN.search(text)
    candidate = match.group(1).strip() if match else None

    if not candidate:
        fallback = PHONE_DIGITS_PATTERN.search(text)
        if fallback:
            candidate = fallback.group(0).strip()

    if candidate:
        # Extract only digits and leading plus
        cleaned = re.sub(r"[^\d+]", "", candidate)
        digits = re.sub(r"\D", "", cleaned)
        if 10 <= len(digits) <= 15:
            # Format nicely or preserve standard international/national format
            if len(digits) == 10 and not cleaned.startswith("+"):
                formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            else:
                formatted = cleaned
            return formatted, 0.92
        elif len(digits) >= 7:
            return cleaned, 0.60
        return cleaned, 0.40

    return None, 0.00

def extract_address(text: str) -> Tuple[Optional[str], float]:
    """Extract residential or mailing address and calculate confidence."""
    match = ADDRESS_LABEL_PATTERN.search(text)
    if match:
        addr = match.group(1).strip()
        # Remove trailing label words if line continued
        addr = re.sub(r"\s+(?:amount|loan|mobile|phone|serial|id)[:=\-].*", "", addr, flags=re.IGNORECASE).strip()
        if len(addr) >= 10:
            return addr, 0.91
        elif len(addr) >= 5:
            return addr, 0.70
        return addr, 0.50

    # Heuristic: search for street address patterns like "123 Main St, Springfield"
    street_pattern = re.compile(
        r"\b(\d+\s+[A-Za-z0-9\s,\.'\-#]+(?:street|st|avenue|ave|road|rd|blvd|boulevard|lane|ln|drive|dr|court|ct|circle|cir|suite|ste|apt|way)\b[^\n\r]*)",
        re.IGNORECASE,
    )
    street_match = street_pattern.search(text)
    if street_match:
        addr = street_match.group(1).strip()
        return addr, 0.75

    return None, 0.00

def extract_amount(text: str) -> Tuple[Optional[float], float]:
    """Extract loan principal amount and calculate confidence."""
    match = AMOUNT_LABEL_PATTERN.search(text)
    if match:
        raw_amt = match.group(1).strip().replace(",", "")
        try:
            val = float(raw_amt)
            if val > 0:
                return round(val, 2), 0.96
            return None, 0.00
        except ValueError:
            pass

    # Currency symbol fallback
    curr_match = AMOUNT_CURRENCY_PATTERN.search(text)
    if curr_match:
        raw_amt = curr_match.group(1).strip().replace(",", "")
        try:
            val = float(raw_amt)
            if val > 0:
                return round(val, 2), 0.85
        except ValueError:
            pass

    return None, 0.00

def parse_loan_fields(
    raw_text: str,
    token_confidences: Optional[Dict[str, float]] = None,
    base_engine_confidence: float = 0.90,
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """
    Parse raw OCR text into the 5 structured loan fields.
    Computes normalized confidence scores in [0.00, 1.00] for each field.
    """
    if not raw_text:
        empty_conf = {
            "serial_number": 0.00,
            "name": 0.00,
            "mobile": 0.00,
            "address": 0.00,
            "amount": 0.00,
        }
        empty_vals = {
            "serial_number": None,
            "name": None,
            "mobile": None,
            "address": None,
            "amount": None,
        }
        return empty_vals, empty_conf

    serial, serial_conf = extract_serial_number(raw_text)
    name, name_conf = extract_name(raw_text)
    mobile, mobile_conf = extract_mobile(raw_text)
    address, address_conf = extract_address(raw_text)
    amount, amount_conf = extract_amount(raw_text)

    # Blend with engine token confidences if provided
    def blend(field_name: str, heuristic_score: float) -> float:
        if token_confidences and field_name in token_confidences:
            engine_score = normalize_confidence(token_confidences[field_name])
            if heuristic_score > 0.0:
                # Weighted average: 60% engine token confidence, 40% heuristic validation
                return normalize_confidence(0.6 * engine_score + 0.4 * heuristic_score)
            return normalize_confidence(engine_score * 0.5)
        # Apply base engine scale
        return normalize_confidence(heuristic_score * base_engine_confidence)

    confidences = {
        "serial_number": blend("serial_number", serial_conf),
        "name": blend("name", name_conf),
        "mobile": blend("mobile", mobile_conf),
        "address": blend("address", address_conf),
        "amount": blend("amount", amount_conf),
    }

    values = {
        "serial_number": serial,
        "name": name,
        "mobile": mobile,
        "address": address or "",
        "amount": amount,
    }

    return values, confidences
