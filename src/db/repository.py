"""Repository layer for atomic CRUD operations on Loan records."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import sqlite3

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.models import LoanCreate, LoanRecord, LoanUpdate, VerificationPayload
from src.db.schema import init_db

class LoanRepository:
    """Repository handling all database operations for loan records."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None, conn: Optional[sqlite3.Connection] = None) -> None:
        self.db_path = db_path or DB_PATH
        self._shared_conn: Optional[sqlite3.Connection] = conn

        # For in-memory databases, keep at least one connection open so tables persist across operations
        if self._shared_conn is None and (str(self.db_path) == ":memory:" or "mode=memory" in str(self.db_path)):
            self._keepalive_conn = get_connection(self.db_path)
        else:
            self._keepalive_conn = None

        # Ensure database tables exist
        init_db(self.db_path)

    def _get_conn(self) -> sqlite3.Connection:
        if self._shared_conn:
            return self._shared_conn
        return get_connection(self.db_path)

    def _close_conn(self, conn: sqlite3.Connection) -> None:
        if conn is not self._shared_conn and conn is not self._keepalive_conn:
            conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite3.Row to a dictionary with parsed JSON fields."""
        data = dict(row)
        if "confidences" in data and isinstance(data["confidences"], str):
            try:
                data["confidences"] = json.loads(data["confidences"])
            except Exception:
                data["confidences"] = {}
        if "raw_ocr_data" in data and isinstance(data["raw_ocr_data"], str):
            try:
                data["raw_ocr_data"] = json.loads(data["raw_ocr_data"])
            except Exception:
                data["raw_ocr_data"] = None
        data["verified"] = bool(data.get("verified", 0))
        return data

    def create_loan(self, loan: LoanCreate) -> LoanRecord:
        """Atomically insert a new loan record and return the created record."""
        now = datetime.now(timezone.utc).isoformat()
        confidences_json = json.dumps(loan.confidences or {})
        raw_ocr_json = json.dumps(loan.raw_ocr_data) if loan.raw_ocr_data is not None else None
        verified_int = 1 if loan.verified else 0

        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO loans (
                    serial_number, name, mobile, address, amount,
                    image_path, raw_ocr_data, confidences, ocr_engine_used,
                    verified, verified_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    loan.serial_number,
                    loan.name,
                    loan.mobile,
                    loan.address or "",
                    float(loan.amount),
                    loan.image_path,
                    raw_ocr_json,
                    confidences_json,
                    loan.ocr_engine_used,
                    verified_int,
                    loan.verified_at,
                    now,
                    now,
                ),
            )
            loan_id = cursor.lastrowid
            conn.execute("COMMIT;")
            cursor.close()
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            raise
        finally:
            self._close_conn(conn)

        created = self.get_loan_by_id(loan_id)
        if not created:
            raise RuntimeError(f"Failed to retrieve loan record immediately after insertion (id: {loan_id})")
        return created

    def get_loan_by_id(self, loan_id: int) -> Optional[LoanRecord]:
        """Fetch a single loan record by primary key id."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM loans WHERE id = ?", (loan_id,))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return None
            return LoanRecord(**self._row_to_dict(row))
        finally:
            self._close_conn(conn)

    def get_loan_by_serial(self, serial_number: str) -> Optional[LoanRecord]:
        """Fetch a loan record by unique serial number."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM loans WHERE serial_number = ? ORDER BY id DESC LIMIT 1", (serial_number,))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return None
            return LoanRecord(**self._row_to_dict(row))
        finally:
            self._close_conn(conn)

    def update_loan(self, loan_id: int, update_data: Union[LoanUpdate, Dict[str, Any]]) -> LoanRecord:
        """Update specific fields of an existing loan record."""
        existing = self.get_loan_by_id(loan_id)
        if not existing:
            raise KeyError(f"Loan with ID {loan_id} not found.")

        if isinstance(update_data, LoanUpdate):
            data_dict = update_data.model_dump(exclude_unset=True)
        elif isinstance(update_data, dict):
            data_dict = {k: v for k, v in update_data.items() if v is not None}
        else:
            raise TypeError("update_data must be LoanUpdate or dict")

        if not data_dict:
            return existing

        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []

        for key, val in data_dict.items():
            if key == "confidences" and isinstance(val, dict):
                fields.append("confidences = ?")
                values.append(json.dumps(val))
            elif key == "raw_ocr_data" and val is not None:
                fields.append("raw_ocr_data = ?")
                values.append(json.dumps(val))
            elif key == "verified":
                fields.append("verified = ?")
                values.append(1 if val else 0)
            elif key in ("serial_number", "name", "mobile", "address", "amount", "image_path", "ocr_engine_used", "verified_at"):
                fields.append(f"{key} = ?")
                values.append(float(val) if key == "amount" else val)

        fields.append("updated_at = ?")
        values.append(now)

        values.append(loan_id)

        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE loans SET {', '.join(fields)} WHERE id = ?",
                tuple(values),
            )
            conn.execute("COMMIT;")
            cursor.close()
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            raise
        finally:
            self._close_conn(conn)

        updated = self.get_loan_by_id(loan_id)
        if not updated:
            raise RuntimeError(f"Loan record {loan_id} disappeared after update")
        return updated

    def update_and_verify_loan(
        self, loan_id: int, update_data: Union[LoanUpdate, VerificationPayload, Dict[str, Any]]
    ) -> LoanRecord:
        """
        Update loan fields and atomically mark record as verified with current timestamp.
        """
        existing = self.get_loan_by_id(loan_id)
        if not existing:
            raise KeyError(f"Loan with ID {loan_id} not found.")

        if isinstance(update_data, (LoanUpdate, VerificationPayload)):
            data_dict = update_data.model_dump(exclude_unset=True)
        elif isinstance(update_data, dict):
            data_dict = {k: v for k, v in update_data.items() if v is not None}
        else:
            raise TypeError("update_data must be LoanUpdate, VerificationPayload, or dict")

        now = datetime.now(timezone.utc).isoformat()
        data_dict["verified"] = True
        data_dict["verified_at"] = now

        return self.update_loan(loan_id, data_dict)

    def list_loans(self, verified_only: bool = False, limit: int = 100, offset: int = 0) -> List[LoanRecord]:
        """List loans with optional verified filter and pagination."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if verified_only:
                cursor.execute(
                    "SELECT * FROM loans WHERE verified = 1 ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            else:
                cursor.execute(
                    "SELECT * FROM loans ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            rows = cursor.fetchall()
            cursor.close()
            return [LoanRecord(**self._row_to_dict(r)) for r in rows]
        finally:
            self._close_conn(conn)

    def list_loans_by_month(self, year_month: str, verified_only: bool = True) -> List[LoanRecord]:
        """
        List loans filtered by year-month string ('YYYY-MM').
        Matches either created_at or verified_at.
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            prefix = f"{year_month}%"
            if verified_only:
                cursor.execute(
                    """
                    SELECT * FROM loans
                    WHERE verified = 1
                      AND (created_at LIKE ? OR verified_at LIKE ?)
                    ORDER BY id ASC
                    """,
                    (prefix, prefix),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM loans
                    WHERE created_at LIKE ? OR verified_at LIKE ?
                    ORDER BY id ASC
                    """,
                    (prefix, prefix),
                )
            rows = cursor.fetchall()
            cursor.close()
            return [LoanRecord(**self._row_to_dict(r)) for r in rows]
        finally:
            self._close_conn(conn)

    def delete_loan(self, loan_id: int) -> bool:
        """Delete a loan record by id. Returns True if deleted."""
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM loans WHERE id = ?", (loan_id,))
            deleted = cursor.rowcount > 0
            conn.execute("COMMIT;")
            cursor.close()
            return deleted
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            raise
        finally:
            self._close_conn(conn)
