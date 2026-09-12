"""Deterministic mock tabular loan image and data fixtures for Batch E2E tests."""

from io import BytesIO
from typing import Any, Dict, List, Optional
from PIL import Image, ImageDraw, ImageFont

CANONICAL_BENGALI_HEADERS = ["ক্রমিক নং", "নাম", "মোবাইল", "ঠিকানা", "পরিমাণ"]

SAMPLE_TABULAR_ROWS = [
    {
        "serial_number": "LN-2026-001",
        "name": "আব্দুর রহিম",
        "mobile": "01711223344",
        "address": "মিরপুর-১০, ঢাকা",
        "amount": 50000.00,
    },
    {
        "serial_number": "LN-2026-002",
        "name": "করিম উদ্দিন",
        "mobile": "01822334455",
        "address": "উত্তরা, ঢাকা",
        "amount": 75000.00,
    },
    {
        "serial_number": "LN-2026-003",
        "name": "ফারহানা আক্তার",
        "mobile": "01933445566",
        "address": "ধানমন্ডি, ঢাকা",
        "amount": 100000.00,
    },
    {
        "serial_number": "LN-2026-004",
        "name": "মোহাম্মদ রফিক",
        "mobile": "01544556677",
        "address": "গুলশান-২, ঢাকা",
        "amount": 120000.00,
    },
    {
        "serial_number": "LN-2026-005",
        "name": "সুলতানা পারভীন",
        "mobile": "01655667788",
        "address": "মতিঝিল, ঢাকা",
        "amount": 65000.00,
    },
]

def generate_tabular_loan_data(num_rows: int = 3, low_conf_index: int = -1) -> List[Dict[str, Any]]:
    """Generate a deterministic list of tabular loan dictionaries up to num_rows (e.g. 100)."""
    rows = []
    base_count = len(SAMPLE_TABULAR_ROWS)
    for i in range(num_rows):
        base_template = SAMPLE_TABULAR_ROWS[i % base_count]
        row_id = i + 1
        row = {
            "row_index": row_id,
            "serial_number": f"LN-2026-{row_id:03d}",
            "name": f"{base_template['name']} {row_id}",
            "mobile": f"017{row_id:08d}"[:11],
            "address": f"{base_template['address']}, সেক্টর {row_id % 15 + 1}",
            "amount": float(25000 + (row_id * 2500)),
        }
        if i == low_conf_index:
            row["is_low_conf"] = True
            row["mobile"] = "???-blur"
        rows.append(row)
    return rows

def _get_font(size: int = 14) -> ImageFont.ImageFont:
    """Attempt loading Kalpurush Bengali font; fall back to default font if unavailable."""
    font_paths = [
        r"C:\Windows\Fonts\kalpurush.ttf",
        r"C:\Windows\Fonts\vrinda.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for fp in font_paths:
        try:
            return ImageFont.truetype(fp, size=size)
        except Exception:
            continue
    return ImageFont.load_default()

def create_mock_tabular_image(
    rows_data: Optional[List[Dict[str, Any]]] = None,
    headers: Optional[List[str]] = None,
    width: int = 1200,
    row_height: int = 38,
    bg_color: str = "#FFFFFF",
    line_color: str = "#333333",
    header_bg: str = "#F0F4F8",
    text_color: str = "#111827",
    is_low_conf_doc: bool = False,
) -> Image.Image:
    """
    Render a clean, high-resolution tabular loan document image with grid lines,
    Bengali column headers, and structured rows.
    """
    if rows_data is None:
        rows_data = generate_tabular_loan_data(num_rows=3)
    if headers is None:
        headers = CANONICAL_BENGALI_HEADERS

    total_rows = len(rows_data)
    # Total image height includes margins, title, header row, and data rows
    top_margin = 100
    bottom_margin = 50
    table_top = top_margin
    total_table_height = (total_rows + 1) * row_height
    height = table_top + total_table_height + bottom_margin

    if is_low_conf_doc:
        bg_color = "#F0F0F0"  # Specific marker color for low confidence fixture

    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    font = _get_font(14)
    title_font = _get_font(18)

    # 1. Document Title
    draw.text((40, 30), "সরকারি ঋণ বিতরণ ও আদায় খতিয়ান (Loan Distribution Ledger)", fill=text_color, font=title_font)
    draw.text((40, 65), f"ব্যাচ পরিচিতি: BATCH-MOCK-2026 | মোট ঋণ গ্রহীতা: {total_rows} জন", fill="#4B5563", font=font)

    # 2. Table Column Dimensions (5 columns)
    left_margin = 40
    right_margin = width - 40
    table_width = right_margin - left_margin

    # Proportions: SL (10%), Name (25%), Mobile (20%), Address (25%), Amount (20%)
    col_widths = [
        int(table_width * 0.10),
        int(table_width * 0.25),
        int(table_width * 0.20),
        int(table_width * 0.25),
        int(table_width * 0.20),
    ]
    col_x = [left_margin]
    for w in col_widths[:-1]:
        col_x.append(col_x[-1] + w)
    col_x.append(right_margin)

    # 3. Header Row Background and Grid
    draw.rectangle([(left_margin, table_top), (right_margin, table_top + row_height)], fill=header_bg, outline=line_color, width=2)
    for col_idx, header_title in enumerate(headers):
        x = col_x[col_idx] + 10
        y = table_top + 10
        draw.text((x, y), header_title, fill=text_color, font=font)

    # 4. Data Rows
    current_y = table_top + row_height
    for row_idx, row in enumerate(rows_data):
        # Draw row boundary
        draw.rectangle([(left_margin, current_y), (right_margin, current_y + row_height)], outline=line_color, width=1)

        # Values mapping
        sl_val = str(row.get("serial_number", f"LN-{row_idx+1:03d}"))
        name_val = str(row.get("name", ""))
        mobile_val = str(row.get("mobile", ""))
        address_val = str(row.get("address", ""))
        amt_val = f"৳{float(row.get('amount', 0.0)):,.2f}"

        cell_values = [sl_val, name_val, mobile_val, address_val, amt_val]

        for col_idx, val in enumerate(cell_values):
            x = col_x[col_idx] + 10
            y = current_y + 10
            draw.text((x, y), val, fill=text_color, font=font)

        current_y += row_height

    # 5. Draw Vertical Column Grid Lines
    for x_line in col_x:
        draw.line([(x_line, table_top), (x_line, current_y)], fill=line_color, width=1)

    return img

def get_tabular_image_bytes(
    num_rows: int = 3,
    image_format: str = "PNG",
    headers: Optional[List[str]] = None,
    is_low_conf: bool = False,
) -> bytes:
    """Generate mock tabular image and return binary bytes."""
    data = generate_tabular_loan_data(num_rows=num_rows, low_conf_index=1 if is_low_conf else -1)
    img = create_mock_tabular_image(rows_data=data, headers=headers, is_low_conf_doc=is_low_conf)
    bio = BytesIO()
    img.save(bio, format=image_format)
    return bio.getvalue()
