"""Deterministic mock image generator and loader for Loan Easier tests."""

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FIXTURES_DIR = Path(__file__).resolve().parent

SAMPLE_LOAN_DATA = {
    "serial_number": "LN-2026-9042",
    "name": "Jane Doe",
    "mobile": "+1-555-234-5678",
    "address": "742 Evergreen Terrace, Springfield, IL 62704",
    "amount": "$25,000.00",
}

def create_loan_document_image(
    data: dict = None,
    width: int = 800,
    height: int = 1000,
    bg_color: str = "#FFFFFF",
    text_color: str = "#000000",
) -> Image.Image:
    """Generate a clean synthetic loan document image with text rendered clearly."""
    if data is None:
        data = SAMPLE_LOAN_DATA

    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Use default PIL bitmap font
    font = ImageFont.load_default()

    # Draw border
    draw.rectangle([(20, 20), (width - 20, height - 20)], outline="#333333", width=2)

    # Draw Header
    title = "OFFICIAL PROMISSORY LOAN AGREEMENT"
    draw.text((width // 4, 50), title, fill=text_color, font=font)
    draw.line([(40, 80), (width - 40, 80)], fill="#666666", width=2)

    # Draw Metadata
    lines = [
        f"Serial Number: {data.get('serial_number', 'LN-2026-9042')}",
        "",
        f"Borrower Name: {data.get('name', 'Jane Doe')}",
        "",
        f"Mobile Number: {data.get('mobile', '+1-555-234-5678')}",
        "",
        f"Address: {data.get('address', '742 Evergreen Terrace, Springfield, IL 62704')}",
        "",
        f"Loan Amount: {data.get('amount', '$25,000.00')}",
        "",
        "Terms and Conditions: The borrower agrees to repay the principal amount",
        "according to the agreed amortization schedule with applicable monthly interest.",
        "",
        "Signatures:",
        "Borrower: _________________________    Date: 2026-09-12",
        "Authorized Officer: ________________   Date: 2026-09-12",
    ]

    y = 120
    for line in lines:
        draw.text((60, y), line, fill=text_color, font=font)
        y += 28

    return img

def generate_all_fixtures() -> None:
    """Generate and persist all deterministic fixture files on disk."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Clean standard PNG
    clean_img = create_loan_document_image()
    clean_png_path = FIXTURES_DIR / "clean_loan_document.png"
    clean_img.save(clean_png_path, format="PNG")

    # 2. Clean standard JPEG
    clean_jpg_path = FIXTURES_DIR / "clean_loan_document.jpg"
    clean_img.save(clean_jpg_path, format="JPEG", quality=95)

    # 3. Low confidence / custom loan document
    low_conf_data = {
        "serial_number": "LN-2026-LOW7",
        "name": "Robert Query",
        "mobile": "+1-555-987-6543",
        "address": "120 Low Street, Apt 3B, Metropolis, NY 10001",
        "amount": "$12,345.67",
    }
    low_img = create_loan_document_image(low_conf_data, bg_color="#F0F0F0")
    low_img_path = FIXTURES_DIR / "low_confidence_document.png"
    low_img.save(low_img_path, format="PNG")

    # 4. Empty file (0 bytes)
    empty_path = FIXTURES_DIR / "empty_file.png"
    empty_path.write_bytes(b"")

    # 5. Invalid MIME text file
    txt_path = FIXTURES_DIR / "invalid_file.txt"
    txt_path.write_text("This is an invalid plain text file pretending to be an image.", encoding="utf-8")

    # 6. Corrupted image file (invalid byte stream with PNG magic bytes)
    corrupted_path = FIXTURES_DIR / "corrupted_image.png"
    corrupted_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRcorruptedcontentgarbagebytes")

def get_fixture_path(filename: str) -> Path:
    """Return absolute path to fixture file, generating it if it doesn't exist."""
    path = FIXTURES_DIR / filename
    if not path.exists():
        generate_all_fixtures()
    return path

def get_fixture_bytes(filename: str) -> bytes:
    """Return raw bytes of a fixture file."""
    return get_fixture_path(filename).read_bytes()

if __name__ == "__main__":
    generate_all_fixtures()
    print("All fixtures generated successfully in:", FIXTURES_DIR)
