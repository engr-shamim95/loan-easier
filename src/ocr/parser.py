"""Field extraction and confidence normalization for loan documents."""

import io
import re
import uuid
import unicodedata
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from src.config import CONFIDENCE_THRESHOLD
from src.ocr.base import TableCell, TableRow, BatchOCRResult

# Regex patterns for matching labels and values
SERIAL_LABEL_PATTERN = re.compile(
    r"(?:serial\s*(?:number|no\.?|#)?|loan\s*(?:id|no\.?|#|number|ref(?:erence)?)|app(?:lication)?\s*(?:id|no\.?|#)|ref(?:erence)?\s*(?:no\.?|#)?|ক্রমিক\s*নং)\s*[:=\-]?\s*([A-Za-z0-9\-_]{1,30}|[০-৯]+)",
    re.IGNORECASE,
)
SERIAL_FALLBACK_PATTERN = re.compile(
    r"\b([A-Z]{2,4}[-_][0-9]{4,10}|[A-Z]{2,4}[0-9]{6,10}|[০-৯]+)\b"
)

NAME_LABEL_PATTERN = re.compile(
    r"(?:borrower\s*(?:name)?|applicant\s*(?:name)?|customer\s*(?:name)?|client\s*(?:name)?|full\s*name|name|ঋণ\s*গ্রহীতার\s*নাম)\s*[:=\-]?\s*([A-Za-z]+(?:[ '\-][A-Za-z]+)+|[\u0980-\u09FF]+(?:\s+[\u0980-\u09FF]+)*)",
    re.IGNORECASE,
)

PHONE_LABEL_PATTERN = re.compile(
    r"(?:mobile\s*(?:number|no\.?|#)?|phone\s*(?:number|no\.?|#)?|contact\s*(?:no\.?|#)?|cell(?:ular)?|tel(?:ephone)?|মোবাইল\s*নং)\s*[:=\-]?\s*(\+?[0-9\s\(\)\-\.]{10,25}|[০-৯\s\-\.]{10,25})",
    re.IGNORECASE,
)
PHONE_DIGITS_PATTERN = re.compile(r"\+?[1-9]\d{1,14}|\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}|[০-৯]{11}")

ADDRESS_LABEL_PATTERN = re.compile(
    r"(?:residential\s*address|mailing\s*address|borrower\s*address|street\s*address|address|ঠিকানা)\s*[:=\-]?\s*([^\n\r]{5,250})",
    re.IGNORECASE,
)

AMOUNT_LABEL_PATTERN = re.compile(
    r"(?:loan\s*amount|principal\s*(?:amount)?|amount\s*(?:approved|sanctioned)?|principal|amount|টাকার\s*পরিমান|টাকার\s*পরিমাণ)\s*[:=\-]?\s*\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?|[০-৯,]+)",
    re.IGNORECASE,
)
AMOUNT_CURRENCY_PATTERN = re.compile(
    r"(?:\$|ট|৳)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?|[০-৯,]+)"
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

# =====================================================================
# Bengali Numeral & Column Synonyms Mapping
# =====================================================================

BENGALI_DIGITS = "০১২৩৪৫৬৭৮৯"
ARABIC_DIGITS = "0123456789"
BENGALI_TO_ARABIC_TABLE = str.maketrans(BENGALI_DIGITS, ARABIC_DIGITS)

def to_arabic_digits(text: str) -> str:
    """Convert all Bengali digits (০-৯) to standard ASCII Arabic numerals (0-9)."""
    if not text:
        return ""
    return str(text).translate(BENGALI_TO_ARABIC_TABLE)

BENGALI_HEADER_SYNONYMS: Dict[str, List[str]] = {
    "serial_number": [
        "ক্রমিক নং", "ক্রমিক নম্বর", "ক্রঃ নং", "ক্র নং", "ক্রমিক", "নং",
        "সিরিয়াল নং", "সিরিয়াল নং", "সিরিয়াল", "সিরিয়াল",
        "sl", "sl no", "sl. no.", "sl.", "serial", "serial no", "serial number", "s/n", "no"
    ],
    "name": [
        "নাম", "ঋণগ্রহীতার নাম", "ঋণ গ্রহীতার নাম", "গ্রাহকের নাম", "সদস্যের নাম", "বোরোয়ারের নাম",
        "name", "borrower name", "applicant name", "customer name", "client name", "full name"
    ],
    "mobile": [
        "মোবাইল", "মোবাইল নং", "মোবাইল নম্বর", "মোবাইল নাম্বার", "ফোন", "ফোন নং", "যোগাযোগ",
        "mobile", "mobile no", "mobile number", "phone", "phone no", "contact", "cell", "tel"
    ],
    "address": [
        "ঠিকানা", "বর্তমান ঠিকানা", "স্থায়ী ঠিকানা", "স্থায়ী ঠিকানা", "বাসার ঠিকানা", "গ্রাম", "গ্রাম/মহল্লা", "ঠিকানা/গ্রাম",
        "address", "present address", "permanent address", "location", "residence"
    ],
    "amount": [
        "পরিমাণ", "পরিমান", "টাকার পরিমাণ", "টাকার পরিমান", "ঋণের পরিমাণ", "ঋণের পরিমান",
        "টাকা", "ঋণ", "আদায়", "আদায়ের পরিমাণ", "বিতরণ", "বিতরণের পরিমাণ", "কিস্তি",
        "amount", "loan amount", "principal", "sanctioned amount", "disbursed amount"
    ],
}

@dataclass
class OCRToken:
    """2D word token with bounding box coordinates and confidence."""
    text: str
    x: int
    y: int
    w: int
    h: int
    confidence: float = 1.0

    @property
    def x_center(self) -> float:
        return self.x + self.w / 2.0

    @property
    def y_center(self) -> float:
        return self.y + self.h / 2.0

    @property
    def x_max(self) -> int:
        return self.x + self.w

    @property
    def y_max(self) -> int:
        return self.y + self.h

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "confidence": self.confidence,
        }

def match_header_column(text: str) -> Optional[str]:
    """Match a text token or phrase to one of the 5 canonical column keys."""
    if not text:
        return None
    cleaned = text.strip().lower()
    # Remove punctuation
    cleaned = re.sub(r"[:\.\-#\(\)\|\*\,\\\/]", " ", cleaned).strip()
    # Bengali spelling normalization
    cleaned = cleaned.replace("সিরিয়াল", "সিরিয়াল").replace("স্থায়ী", "স্থায়ী").replace("পরিমান", "পরিমাণ")
    words = cleaned.split()
    cleaned_norm = " ".join(words)
    cleaned_no_spaces = "".join(words)

    # 1. Exact match (with normalized spaces or no spaces)
    for col, synonyms in BENGALI_HEADER_SYNONYMS.items():
        for syn in synonyms:
            syn_clean = syn.lower().replace("সিরিয়াল", "সিরিয়াল").replace("স্থায়ী", "স্থায়ী").replace("পরিমান", "পরিমাণ")
            syn_words = syn_clean.split()
            syn_norm = " ".join(syn_words)
            syn_no_spaces = "".join(syn_words)
            if cleaned_norm == syn_norm or cleaned_no_spaces == syn_no_spaces:
                return col

    # 2. Check if text is a single multi-word header matching exactly
    for col, synonyms in BENGALI_HEADER_SYNONYMS.items():
        for syn in synonyms:
            syn_clean = syn.lower().replace("সিরিয়াল", "সিরিয়াল").replace("স্থায়ী", "স্থায়ী").replace("পরিমান", "পরিমাণ")
            syn_words = syn_clean.split()
            if len(syn_words) > 1 and len(words) == len(syn_words):
                if words == syn_words:
                    return col

    # 3. Single-word synonym match if phrase has only 1 word
    if len(words) == 1:
        for col, synonyms in BENGALI_HEADER_SYNONYMS.items():
            for syn in synonyms:
                syn_clean = syn.lower().replace("সিরিয়াল", "সিরিয়াল").replace("স্থায়ী", "স্থায়ী").replace("পরিমান", "পরিমাণ")
                if syn_clean == words[0]:
                    return col

    return None

def clean_serial_cell(raw_text: str, row_index: int = 1) -> Tuple[str, float]:
    """Clean serial number cell and calculate confidence."""
    if not raw_text:
        return f"LN-{row_index:03d}", 0.70
    arabic = to_arabic_digits(raw_text)
    cleaned = re.sub(r"[^\w\-_]", "", arabic).strip()
    if not cleaned:
        return f"LN-{row_index:03d}", 0.70
    if re.match(r"^[A-Za-z0-9\-_]{1,30}$", cleaned):
        return cleaned, 0.95
    return cleaned, 0.75

def clean_name_cell(raw_text: str) -> Tuple[str, float]:
    """Clean borrower name cell and calculate confidence."""
    if not raw_text:
        return "", 0.00
    cleaned = re.sub(r"[\r\n\t]+", " ", raw_text)
    cleaned = re.sub(r"[:|#$@*_=]+", "", cleaned).strip()
    cleaned = re.sub(r"^[0-9০-৯]+[\.\-\)]\s*", "", cleaned).strip()
    cleaned = unicodedata.normalize("NFC", cleaned)
    words = cleaned.split()
    if len(words) >= 2:
        return cleaned, 0.94
    elif len(words) == 1 and len(words[0]) >= 2:
        return cleaned, 0.75
    return cleaned, 0.50

def clean_mobile_cell(raw_text: str) -> Tuple[str, float]:
    """Clean mobile phone number cell and calculate confidence."""
    if not raw_text:
        return "", 0.00
    arabic = to_arabic_digits(raw_text)
    cleaned = re.sub(r"[^\d+]", "", arabic)
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) == 11 and digits.startswith("01"):
        return digits, 0.95
    elif len(digits) == 13 and cleaned.startswith("+8801"):
        return cleaned, 0.95
    elif 10 <= len(digits) <= 15:
        return cleaned, 0.88
    elif len(digits) >= 7:
        return cleaned, 0.60
    return cleaned, 0.40

def clean_address_cell(raw_text: str) -> Tuple[str, float]:
    """Clean address cell and calculate confidence."""
    if not raw_text:
        return "", 0.00
    cleaned = re.sub(r"[\r\n\t]+", " ", raw_text)
    cleaned = re.sub(r"[:|#$@*_=]+", "", cleaned).strip()
    cleaned = unicodedata.normalize("NFC", cleaned)
    if len(cleaned) >= 10:
        return cleaned, 0.92
    elif len(cleaned) >= 5:
        return cleaned, 0.75
    return cleaned, 0.50

def clean_amount_cell(raw_text: str) -> Tuple[float, float]:
    """Clean loan amount cell and calculate confidence."""
    if not raw_text:
        return 0.0, 0.00
    arabic = to_arabic_digits(raw_text)
    stripped = re.sub(r"(?:টাকা|ট|৳|TK|Tk|USD|\$|/|\-)+", "", arabic, flags=re.IGNORECASE)
    stripped = stripped.replace(",", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", stripped)
    if match:
        try:
            val = float(match.group(0))
            if val > 0:
                return round(val, 2), 0.96
            return 0.0, 0.00
        except ValueError:
            pass
    return 0.0, 0.00

class TableSpatialExtractor:
    """
    Extracts structured tabular loan records from 2D OCR word tokens or text lines.
    Clusters rows by Y-coordinates, partitions columns by horizontal boundaries,
    and normalizes confidences. Supports up to 100 rows.
    """

    def __init__(self, batch_id: Optional[str] = None, engine_name: str = "") -> None:
        self.batch_id = batch_id or f"BATCH-{uuid.uuid4().hex[:8].upper()}"
        self.engine_name = engine_name

    def _normalize_token(self, item: Any) -> Optional[OCRToken]:
        """Convert heterogeneous token representations into OCRToken."""
        if isinstance(item, OCRToken):
            return item
        if isinstance(item, dict):
            return OCRToken(
                text=str(item.get("text", "")).strip(),
                x=int(item.get("x", 0)),
                y=int(item.get("y", 0)),
                w=int(item.get("w", 0)),
                h=int(item.get("h", 0)),
                confidence=float(item.get("confidence", 1.0)),
            )
        if isinstance(item, (list, tuple)):
            if len(item) >= 6:
                return OCRToken(
                    text=str(item[0]).strip(),
                    x=int(item[1]),
                    y=int(item[2]),
                    w=int(item[3]),
                    h=int(item[4]),
                    confidence=float(item[5]),
                )
            elif len(item) >= 5:
                return OCRToken(
                    text=str(item[0]).strip(),
                    x=int(item[1]),
                    y=int(item[2]),
                    w=int(item[3]),
                    h=int(item[4]),
                    confidence=1.0,
                )
        return None

    def extract(
        self,
        tokens: Optional[List[Any]] = None,
        raw_text: str = "",
    ) -> BatchOCRResult:
        """
        Extract tabular loan records. Attempts 2D spatial extraction first
        if tokens are present, falling back to text-line parser.
        """
        if tokens and len(tokens) > 0:
            result = self.extract_from_tokens(tokens, raw_text=raw_text)
            if result.total_rows > 0:
                return result
        return self.extract_from_text(raw_text)

    def extract_from_tokens(
        self,
        raw_tokens: List[Any],
        raw_text: str = "",
    ) -> BatchOCRResult:
        """
        Extract table using 2D spatial layout analysis:
        1. Identify table header tokens across Y bands.
        2. Establish horizontal column intervals.
        3. Cluster data tokens into rows via adaptive Y coordinates.
        4. Partition row tokens into columns and normalize cell confidences.
        5. Support up to 100 rows.
        """
        norm_tokens: List[OCRToken] = []
        for raw in raw_tokens:
            tok = self._normalize_token(raw)
            if tok and tok.text:
                norm_tokens.append(tok)

        if not norm_tokens:
            return self.extract_from_text(raw_text)

        # Estimate median token height
        heights = [t.h for t in norm_tokens if t.h > 0]
        median_h = statistics.median(heights) if heights else 20.0

        # Sort tokens by Y coordinate
        norm_tokens.sort(key=lambda t: (t.y, t.x))

        # Group tokens into candidate lines by vertical overlap
        line_clusters: List[List[OCRToken]] = []
        for t in norm_tokens:
            if not line_clusters:
                line_clusters.append([t])
                continue
            last_line = line_clusters[-1]
            avg_y = sum(x.y_center for x in last_line) / len(last_line)
            if abs(t.y_center - avg_y) <= 0.65 * median_h:
                last_line.append(t)
            else:
                line_clusters.append([t])

        for line in line_clusters:
            line.sort(key=lambda t: t.x)

        # Step 1: Detect Table Header Row
        header_row_idx = -1
        detected_headers: Dict[str, OCRToken] = {}  # col_key -> token/span
        best_header_count = 0

        for idx, line in enumerate(line_clusters):
            matched_in_line: Dict[str, OCRToken] = {}
            # Check 1-token, 2-token, 3-token combinations in line
            n = len(line)
            i = 0
            while i < n:
                matched_col = None
                span_len = 1
                for k in range(min(3, n - i), 0, -1):
                    phrase = " ".join(t.text for t in line[i : i + k])
                    col = match_header_column(phrase)
                    if col and col not in matched_in_line:
                        matched_col = col
                        span_len = k
                        # Create combined token representation for bounding box
                        combined_tok = OCRToken(
                            text=phrase,
                            x=line[i].x,
                            y=min(t.y for t in line[i : i + k]),
                            w=line[i + k - 1].x_max - line[i].x,
                            h=max(t.y_max for t in line[i : i + k]) - min(t.y for t in line[i : i + k]),
                            confidence=sum(t.confidence for t in line[i : i + k]) / span_len,
                        )
                        break
                if matched_col:
                    matched_in_line[matched_col] = combined_tok
                    i += span_len
                else:
                    i += 1

            if len(matched_in_line) > best_header_count and len(matched_in_line) >= 2:
                best_header_count = len(matched_in_line)
                header_row_idx = idx
                detected_headers = matched_in_line

        # Step 2: Establish Column Horizontal Intervals
        canonical_cols = ["serial_number", "name", "mobile", "address", "amount"]
        col_intervals: List[Tuple[str, float, float]] = []

        max_x = max(t.x_max for t in norm_tokens) if norm_tokens else 1000

        if header_row_idx >= 0 and detected_headers:
            # Sort detected headers by x position
            sorted_headers = sorted(detected_headers.items(), key=lambda item: item[1].x)

            # Calculate boundary midpoints between adjacent headers
            splits: List[float] = []
            for i in range(len(sorted_headers) - 1):
                left_h = sorted_headers[i][1]
                right_h = sorted_headers[i + 1][1]
                split_x = (left_h.x_max + right_h.x) / 2.0
                splits.append(split_x)

            # Build intervals
            col_intervals.append((sorted_headers[0][0], 0.0, splits[0] if splits else float(max_x)))
            for i in range(1, len(sorted_headers) - 1):
                col_intervals.append((sorted_headers[i][0], splits[i - 1], splits[i]))
            if len(sorted_headers) > 1:
                col_intervals.append((sorted_headers[-1][0], splits[-1], float(max_x + 1000)))

            data_lines = line_clusters[header_row_idx + 1 :]
        else:
            # Default positional partition
            col_intervals = [
                ("serial_number", 0.0, max_x * 0.15),
                ("name", max_x * 0.15, max_x * 0.40),
                ("mobile", max_x * 0.40, max_x * 0.60),
                ("address", max_x * 0.60, max_x * 0.80),
                ("amount", max_x * 0.80, float(max_x + 1000)),
            ]
            data_lines = line_clusters

        # Step 3: Extract Data Rows (up to 100 rows)
        rows: List[TableRow] = []
        row_index = 1

        for line in data_lines:
            if row_index > 100:
                break
            # Skip noise lines with very few or zero tokens
            if not line:
                continue

            # Check if this line is a summary/total or footer line
            line_str = " ".join(t.text for t in line)
            if any(k in line_str for k in ("Total", "সর্বমোট", "মোট", "Signatures", "স্বাক্ষর")):
                continue

            # Bucket tokens into columns by x_center
            col_buckets: Dict[str, List[OCRToken]] = {col: [] for col in canonical_cols}
            for tok in line:
                xc = tok.x_center
                assigned = False
                for col_name, x_start, x_end in col_intervals:
                    if x_start <= xc < x_end:
                        col_buckets[col_name].append(tok)
                        assigned = True
                        break
                if not assigned:
                    # Assign to nearest column boundary
                    if xc < col_intervals[0][1]:
                        col_buckets[col_intervals[0][0]].append(tok)
                    else:
                        col_buckets[col_intervals[-1][0]].append(tok)

            # Extract cell values and confidences
            def process_cell(col_name: str) -> TableCell:
                toks = col_buckets[col_name]
                raw_c = " ".join(t.text for t in toks).strip()
                tok_conf = (sum(t.confidence for t in toks) / len(toks)) if toks else 0.0

                b_box = None
                if toks:
                    b_box = {
                        "x": min(t.x for t in toks),
                        "y": min(t.y for t in toks),
                        "w": max(t.x_max for t in toks) - min(t.x for t in toks),
                        "h": max(t.y_max for t in toks) - min(t.y for t in toks),
                    }

                if col_name == "serial_number":
                    val, heur = clean_serial_cell(raw_c, row_index)
                elif col_name == "name":
                    val, heur = clean_name_cell(raw_c)
                elif col_name == "mobile":
                    val, heur = clean_mobile_cell(raw_c)
                elif col_name == "address":
                    val, heur = clean_address_cell(raw_c)
                elif col_name == "amount":
                    val, heur = clean_amount_cell(raw_c)
                else:
                    val, heur = raw_c, 0.50

                if toks:
                    score = normalize_confidence(0.6 * tok_conf + 0.4 * heur) if heur > 0 else normalize_confidence(tok_conf * 0.5)
                else:
                    score = 0.00
                is_low = is_low_confidence(score)
                return TableCell(
                    value=val,
                    raw_text=raw_c,
                    confidence=score,
                    is_low_confidence=is_low,
                    bounding_box=b_box,
                )

            cell_sl = process_cell("serial_number")
            cell_name = process_cell("name")
            cell_mobile = process_cell("mobile")
            cell_addr = process_cell("address")
            cell_amt = process_cell("amount")

            # Check if row has meaningful data (at least 2 non-empty fields or 1 if mobile/amount)
            has_data = any(
                [
                    cell_name.value,
                    cell_mobile.value,
                    cell_amt.value > 0 if isinstance(cell_amt.value, (int, float)) else False,
                ]
            )

            # Handle wrapped address line: if row has no serial, no name, no amount, but address exists, merge to previous
            if not has_data and cell_addr.value and rows:
                prev_row = rows[-1]
                merged_addr = f"{prev_row.address.value} {cell_addr.value}".strip()
                prev_row.address.value = merged_addr
                prev_row.address.raw_text = f"{prev_row.address.raw_text} {cell_addr.raw_text}".strip()
                continue

            if not has_data:
                continue

            all_confs = [
                cell_sl.confidence,
                cell_name.confidence,
                cell_mobile.confidence,
                cell_addr.confidence,
                cell_amt.confidence,
            ]
            overall_conf = round(sum(all_confs) / 5.0, 2)
            row_is_low = any(
                c.is_low_confidence
                for c in [cell_sl, cell_name, cell_mobile, cell_addr, cell_amt]
            )

            row_box = {
                "x": min(t.x for t in line),
                "y": min(t.y for t in line),
                "w": max(t.x_max for t in line) - min(t.x for t in line),
                "h": max(t.y_max for t in line) - min(t.y for t in line),
            }

            rows.append(
                TableRow(
                    row_index=row_index,
                    serial_number=cell_sl,
                    name=cell_name,
                    mobile=cell_mobile,
                    address=cell_addr,
                    amount=cell_amt,
                    overall_confidence=overall_conf,
                    is_low_confidence=row_is_low,
                    raw_text=line_str,
                    bounding_box=row_box,
                )
            )
            row_index += 1

        if not rows:
            return self.extract_from_text(raw_text)

        detected_col_names = [col for col, _, _ in col_intervals]
        return BatchOCRResult(
            batch_id=self.batch_id,
            rows=rows,
            total_rows=len(rows),
            engine_name=self.engine_name,
            raw_text=raw_text or "\n".join(r.raw_text for r in rows),
            detected_columns=detected_col_names,
            is_tabular=True,
        )

    def extract_from_text(self, raw_text: str) -> BatchOCRResult:
        """
        Fallback parser for delimiter-separated or structured tabular text lines.
        Supports pipe '|', tab '\t', or multi-space delimiters, as well as single-record agreements.
        """
        if not raw_text or not raw_text.strip():
            return BatchOCRResult(
                batch_id=self.batch_id,
                rows=[],
                total_rows=0,
                engine_name=self.engine_name,
                raw_text="",
            )

        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        # Check for header row
        header_idx = -1
        col_order: List[str] = ["serial_number", "name", "mobile", "address", "amount"]

        for i, line in enumerate(lines[:10]):
            parts = [p.strip() for p in re.split(r"[\|\t]|\s{2,}", line) if p.strip()]
            matched = []
            for p in parts:
                col = match_header_column(p)
                if col and col not in matched:
                    matched.append(col)
            if len(matched) >= 2:
                header_idx = i
                col_order = matched
                break

        data_lines = lines[header_idx + 1 :] if header_idx >= 0 else lines
        rows: List[TableRow] = []
        row_index = 1

        for line in data_lines:
            if row_index > 100:
                break
            if any(k in line for k in ("Total", "সর্বমোট", "মোট", "Signatures", "স্বাক্ষর")):
                continue

            parts = [p.strip() for p in re.split(r"[\|\t]|\s{2,}", line) if p.strip()]
            if len(parts) >= 3:
                # Delimited row
                row_dict: Dict[str, str] = {}
                for idx, part in enumerate(parts):
                    if idx < len(col_order):
                        row_dict[col_order[idx]] = part
                    else:
                        # Extra parts append to address
                        if "address" in row_dict:
                            row_dict["address"] += f" {part}"
                        else:
                            row_dict["address"] = part

                sl_val, sl_heur = clean_serial_cell(row_dict.get("serial_number", ""), row_index)
                name_val, name_heur = clean_name_cell(row_dict.get("name", ""))
                mobile_val, mobile_heur = clean_mobile_cell(row_dict.get("mobile", ""))
                addr_val, addr_heur = clean_address_cell(row_dict.get("address", ""))
                amt_val, amt_heur = clean_amount_cell(row_dict.get("amount", ""))

                c_sl = TableCell(value=sl_val, raw_text=row_dict.get("serial_number", ""), confidence=sl_heur, is_low_confidence=is_low_confidence(sl_heur))
                c_name = TableCell(value=name_val, raw_text=row_dict.get("name", ""), confidence=name_heur, is_low_confidence=is_low_confidence(name_heur))
                c_mobile = TableCell(value=mobile_val, raw_text=row_dict.get("mobile", ""), confidence=mobile_heur, is_low_confidence=is_low_confidence(mobile_heur))
                c_addr = TableCell(value=addr_val, raw_text=row_dict.get("address", ""), confidence=addr_heur, is_low_confidence=is_low_confidence(addr_heur))
                c_amt = TableCell(value=amt_val, raw_text=row_dict.get("amount", ""), confidence=amt_heur, is_low_confidence=is_low_confidence(amt_heur))

                overall = round((sl_heur + name_heur + mobile_heur + addr_heur + amt_heur) / 5.0, 2)
                row_low = any(c.is_low_confidence for c in [c_sl, c_name, c_mobile, c_addr, c_amt])

                rows.append(
                    TableRow(
                        row_index=row_index,
                        serial_number=c_sl,
                        name=c_name,
                        mobile=c_mobile,
                        address=c_addr,
                        amount=c_amt,
                        overall_confidence=overall,
                        is_low_confidence=row_low,
                        raw_text=line,
                    )
                )
                row_index += 1

        # If no multi-line table rows were parsed, attempt single-loan extraction
        if not rows:
            single_vals, single_confs = parse_loan_fields(raw_text)
            if any(single_vals.values()):
                sl = single_vals.get("serial_number") or f"LN-{row_index:03d}"
                c_sl = TableCell(value=sl, raw_text=sl, confidence=single_confs.get("serial_number", 0.90), is_low_confidence=is_low_confidence(single_confs.get("serial_number", 0.90)))
                c_name = TableCell(value=single_vals.get("name") or "", raw_text=single_vals.get("name") or "", confidence=single_confs.get("name", 0.90), is_low_confidence=is_low_confidence(single_confs.get("name", 0.90)))
                c_mobile = TableCell(value=single_vals.get("mobile") or "", raw_text=single_vals.get("mobile") or "", confidence=single_confs.get("mobile", 0.90), is_low_confidence=is_low_confidence(single_confs.get("mobile", 0.90)))
                c_addr = TableCell(value=single_vals.get("address") or "", raw_text=single_vals.get("address") or "", confidence=single_confs.get("address", 0.90), is_low_confidence=is_low_confidence(single_confs.get("address", 0.90)))
                amt = single_vals.get("amount") if single_vals.get("amount") is not None else 0.0
                c_amt = TableCell(value=amt, raw_text=str(amt), confidence=single_confs.get("amount", 0.90), is_low_confidence=is_low_confidence(single_confs.get("amount", 0.90)))

                overall = round(sum(single_confs.values()) / max(len(single_confs), 1), 2)
                row_low = any(c.is_low_confidence for c in [c_sl, c_name, c_mobile, c_addr, c_amt])

                rows.append(
                    TableRow(
                        row_index=1,
                        serial_number=c_sl,
                        name=c_name,
                        mobile=c_mobile,
                        address=c_addr,
                        amount=c_amt,
                        overall_confidence=overall,
                        is_low_confidence=row_low,
                        raw_text=raw_text,
                    )
                )

        return BatchOCRResult(
            batch_id=self.batch_id,
            rows=rows,
            total_rows=len(rows),
            engine_name=self.engine_name,
            raw_text=raw_text,
            detected_columns=col_order,
            is_tabular=True,
        )

def parse_tabular_ocr(
    tokens: Optional[List[Any]] = None,
    raw_text: str = "",
    batch_id: Optional[str] = None,
    engine_name: str = "",
) -> BatchOCRResult:
    """Convenience functional interface for tabular extraction."""
    extractor = TableSpatialExtractor(batch_id=batch_id, engine_name=engine_name)
    return extractor.extract(tokens=tokens, raw_text=raw_text)

def generate_mock_tabular_tokens(
    num_rows: int = 3,
    low_conf_row: Optional[int] = None,
    base_conf: float = 0.95,
) -> List[OCRToken]:
    """
    Generate realistic 2D OCR word tokens for a Bengali loan table.
    Supports 1 to 100 rows with authentic Bengali headers and values.
    """
    tokens: List[OCRToken] = []

    # Table Header at y=50
    headers = [
        ("ক্রমিক নং", 30, 50, 80, 25),
        ("নাম", 130, 50, 200, 25),
        ("মোবাইল", 350, 50, 140, 25),
        ("ঠিকানা", 510, 50, 240, 25),
        ("পরিমাণ", 770, 50, 120, 25),
    ]
    for text, x, y, w, h in headers:
        tokens.append(OCRToken(text=text, x=x, y=y, w=w, h=h, confidence=base_conf))

    first_names = ["রফিকুল", "মোসাঃ ফাতেমা", "আব্দুল", "নাজমুল", "সালমা", "তারেক", "নাসরিন", "মাহমুদ", "শাহীন", "রেহানা"]
    last_names = ["ইসলাম", "বেগম", "করিম", "হোসেন", "আক্তার", "রহমান", "চৌধুরী", "খাঁন", "আহমেদ", "মিয়া"]
    districts = ["ঈশ্বরদী, পাবনা", "ধানমন্ডি, ঢাকা", "চকবাজার, চট্টগ্রাম", "সোনাতলা, বগুড়া", "সদর, রাজশাহী", "শিবগঞ্জ, সিলেট", "খালিশপুর, খুলনা", "কোতোয়ালী, বরিশাল", "পলাশপোল, সাতক্ষীরা", "টঙ্গী, গাজীপুর"]

    for i in range(1, num_rows + 1):
        y = 95 + (i - 1) * 35
        sl_str = f"LN-{i:03d}"
        name_str = f"{first_names[(i - 1) % len(first_names)]} {last_names[(i - 1) % len(last_names)]}"
        mob_num = (i * 11111111) % 90000000 + 10000000
        mob_str = f"017{mob_num:08d}"
        addr_str = f"{i * 12} নং রোড, {districts[(i - 1) % len(districts)]}"
        amt_val = 15000 + (i * 2500)
        amt_str = f"{amt_val:,}"

        # Check if this row is flagged for low confidence
        is_low_row = (low_conf_row is not None and i == low_conf_row)
        mob_conf = 0.55 if is_low_row else base_conf

        tokens.append(OCRToken(text=sl_str, x=30, y=y, w=60, h=20, confidence=base_conf))
        # Split name words
        name_parts = name_str.split()
        curr_x = 130
        for part in name_parts:
            pw = len(part) * 14
            tokens.append(OCRToken(text=part, x=curr_x, y=y, w=pw, h=20, confidence=base_conf))
            curr_x += pw + 8

        tokens.append(OCRToken(text=mob_str, x=350, y=y, w=100, h=20, confidence=mob_conf))

        addr_parts = addr_str.split()
        curr_x = 510
        for part in addr_parts:
            pw = len(part) * 12
            tokens.append(OCRToken(text=part, x=curr_x, y=y, w=pw, h=20, confidence=base_conf))
            curr_x += pw + 6

        tokens.append(OCRToken(text=amt_str, x=770, y=y, w=80, h=20, confidence=base_conf))

    return tokens
