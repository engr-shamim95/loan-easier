"""Database schema initialization and migrations."""

import sqlite3
from typing import Optional, Union
from pathlib import Path
from src.db.connection import get_connection

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT,
    row_index INTEGER,
    project_type TEXT NOT NULL DEFAULT 'loan',
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
"""

def init_db(db_path: Optional[Union[str, Path]] = None) -> None:
    """Initialize SQLite database tables and indices, and ensure migrations."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.executescript(SCHEMA_SQL)

        # Migration check: Ensure batch_id and row_index exist if loans was already created
        cursor.execute("PRAGMA table_info(loans);")
        columns = [row[1] for row in cursor.fetchall()]
        if "batch_id" not in columns:
            cursor.execute("ALTER TABLE loans ADD COLUMN batch_id TEXT;")
        if "row_index" not in columns:
            cursor.execute("ALTER TABLE loans ADD COLUMN row_index INTEGER;")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_loans_batch ON loans(batch_id);")
        cursor.execute("DROP VIEW IF EXISTS loan_records;")
        cursor.execute("CREATE VIEW loan_records AS SELECT * FROM loans;")
        conn.commit()
        cursor.close()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
