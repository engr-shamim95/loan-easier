"""Text parsing for digital formats (CSV, JSON, Markdown)."""
import csv
import io
import json
import uuid
import re
from typing import Dict, Any, List

from src.ocr.base import BatchOCRResult, TableRow, TableCell

def _create_row(idx: int, sn: str, name: str, mob: str, addr: str, amt: float, raw: str) -> TableRow:
    c = 1.0
    return TableRow(
        row_index=idx,
        serial_number=TableCell(value=sn, raw_text=sn, confidence=c),
        name=TableCell(value=name, raw_text=name, confidence=c),
        mobile=TableCell(value=mob, raw_text=mob, confidence=c),
        address=TableCell(value=addr, raw_text=addr, confidence=c),
        amount=TableCell(value=amt, raw_text=str(amt), confidence=c),
        overall_confidence=c,
        raw_text=raw
    )

def _safe_float(val: Any) -> float:
    try:
        # Strip non-numeric chars except dot
        clean = re.sub(r'[^\d.]', '', str(val))
        return float(clean) if clean else 0.0
    except Exception:
        return 0.0

def parse_csv(file_bytes: bytes) -> BatchOCRResult:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    
    # Try to map common header names
    def get_val(row: dict, keys: list) -> str:
        for k, v in row.items():
            if not k: continue
            for target in keys:
                if target.lower() in k.lower():
                    return str(v).strip()
        return ""
    
    for i, row in enumerate(reader, 1):
        sn = get_val(row, ["serial", "id", "ক্রমিক", "নং"])
        name = get_val(row, ["name", "নাম"])
        mob = get_val(row, ["mobile", "phone", "মোবাইল", "ফোন"])
        addr = get_val(row, ["address", "ঠিকানা"])
        amt_str = get_val(row, ["amount", "পরিমাণ", "টাকা"])
        amt = _safe_float(amt_str)
        
        rows.append(_create_row(i, sn, name, mob, addr, amt, str(row)))
        
    return BatchOCRResult(
        batch_id=f"BATCH-CSV-{uuid.uuid4().hex[:6].upper()}",
        rows=rows,
        engine_name="csv_parser",
        raw_text=text,
        is_tabular=True
    )

def parse_json(file_bytes: bytes) -> BatchOCRResult:
    text = file_bytes.decode("utf-8")
    data = json.loads(text)
    
    if not isinstance(data, list):
        if "records" in data and isinstance(data["records"], list):
            data = data["records"]
        elif "rows" in data and isinstance(data["rows"], list):
            data = data["rows"]
        else:
            data = [data] # Try parsing as single object list
            
    rows = []
    for i, item in enumerate(data, 1):
        if not isinstance(item, dict): continue
        sn = str(item.get("serial_number", item.get("id", item.get("ক্রমিক নং", ""))))
        name = str(item.get("name", item.get("নাম", "")))
        mob = str(item.get("mobile", item.get("মোবাইল", "")))
        addr = str(item.get("address", item.get("ঠিকানা", "")))
        amt = _safe_float(item.get("amount", item.get("পরিমাণ", 0.0)))
        
        rows.append(_create_row(i, sn, name, mob, addr, amt, json.dumps(item)))
        
    return BatchOCRResult(
        batch_id=f"BATCH-JSON-{uuid.uuid4().hex[:6].upper()}",
        rows=rows,
        engine_name="json_parser",
        raw_text=text,
        is_tabular=True
    )

def parse_markdown(file_bytes: bytes) -> BatchOCRResult:
    text = file_bytes.decode("utf-8")
    lines = text.strip().split('\n')
    
    rows = []
    idx = 1
    # Simple markdown table parser
    for line in lines:
        if not line.strip().startswith('|'):
            continue
        cols = [c.strip() for c in line.split('|')[1:-1]]
        if len(cols) < 5 or set(cols[0]) == {'-'} or "serial" in cols[0].lower() or "ক্রমিক" in cols[0]:
            continue # Header or separator
            
        sn = cols[0]
        name = cols[1]
        mob = cols[2]
        addr = cols[3]
        amt = _safe_float(cols[4])
        
        rows.append(_create_row(idx, sn, name, mob, addr, amt, line))
        idx += 1
        
    return BatchOCRResult(
        batch_id=f"BATCH-MD-{uuid.uuid4().hex[:6].upper()}",
        rows=rows,
        engine_name="md_parser",
        raw_text=text,
        is_tabular=True
    )
