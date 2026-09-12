"""Configuration module for Loan Easier system."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "loan_records.db"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Confidence scoring
CONFIDENCE_THRESHOLD = 0.80  # Strict: score < 0.80 is marked as low confidence

# File upload constraints
MAX_UPLOAD_SIZE = 15 * 1024 * 1024  # 15 MB
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp", ".csv", ".json", ".md"}
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/webp",
    "text/csv",
    "application/json",
    "text/markdown",
    "text/plain",  # Often browsers send md/csv as text/plain
}

# OCR Engine configuration
def get_bool_env(var_name: str, default: bool = False) -> bool:
    val = os.getenv(var_name, "").strip().lower()
    if val in ("true", "1", "yes", "on"):
        return True
    if val in ("false", "0", "no", "off"):
        return False
    return default

OCR_FORCE_FALLBACK = get_bool_env("OCR_FORCE_FALLBACK", False)
OCR_MOCK_MODE = get_bool_env("OCR_MOCK_MODE", False)

# Tesseract executable lookup
DEFAULT_TESSERACT_PATHS = [
    os.getenv("TESSERACT_CMD", ""),
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\Developer Shamim\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
]

def find_tesseract_binary() -> str | None:
    for path in DEFAULT_TESSERACT_PATHS:
        if path and Path(path).is_file():
            return path
    return None

TESSERACT_CMD = find_tesseract_binary()

# Server defaults
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
