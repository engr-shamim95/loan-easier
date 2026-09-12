"""Database schema initialization and migrations."""

import sqlite3
from typing import Optional, Union
from pathlib import Path
from src.db.connection import get_connection

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial_number TEXT NOT NULL,
    name TEXT NOT NULL,
    mobile TEXT NOT NULL,
    address TEXT,
    amount REAL NOT NULL,
    image_path TEXT,
    raw_ocr_data TEXT,
    confidences TEXT,
    ocr_engine_used TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0,
    verified_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_loans_serial ON loans(serial_number);
CREATE INDEX IF NOT EXISTS idx_loans_verified ON loans(verified);
CREATE INDEX IF NOT EXISTS idx_loans_created ON loans(created_at);
CREATE INDEX IF NOT EXISTS idx_loans_verified_at ON loans(verified_at);

-- Alias view to ensure full compatibility with queries referencing loan_records
CREATE VIEW IF NOT EXISTS loan_records AS SELECT * FROM loans;
"""

def init_db(db_path: Optional[Union[str, Path]] = None) -> None:
    """Initialize SQLite database tables and indices."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.executescript(SCHEMA_SQL)
        cursor.close()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
