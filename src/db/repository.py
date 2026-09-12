"""Repository layer for atomic CRUD operations on Loan records."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import sqlite3

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.models import (
    LoanCreate,
    LoanRecord,
    LoanUpdate,
    VerificationPayload,
    BatchVerificationRow,
)
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
                    batch_id, row_index, project_type,
                    serial_number, name, mobile, address, amount,
                    image_path, raw_ocr_data, confidences, ocr_engine_used,
                    verified, verified_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    loan.batch_id,
                    loan.row_index,
                    loan.project_type,
                    loan.serial_number,
                    loan.name,
                    loan.mobile,
                    loan.address,
                    loan.amount,
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
            elif key in (
                "serial_number",
                "name",
                "mobile",
                "address",
                "amount",
                "image_path",
                "ocr_engine_used",
                "verified_at",
                "batch_id",
                "row_index",
            ):
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

    def list_loans_by_month(self, year_month: str, verified_only: bool = True, project_type: Optional[str] = None) -> List[LoanRecord]:
        """
        List loans filtered by year-month string ('YYYY-MM') and optionally project_type.
        Matches either created_at or verified_at.
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            prefix = f"{year_month}%"
            
            query = "SELECT * FROM loans WHERE (created_at LIKE ? OR verified_at LIKE ?)"
            params = [prefix, prefix]
            
            if verified_only:
                query += " AND verified = 1"
            
            if project_type:
                query += " AND project_type = ?"
                params.append(project_type)
                
            query += " ORDER BY id ASC"
            
            cursor.execute(query, tuple(params))
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

    def get_batch_loans(self, batch_id: str) -> List[LoanRecord]:
        """Fetch all loan records belonging to a specific batch, ordered by row_index."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM loans WHERE batch_id = ? ORDER BY row_index ASC, id ASC",
                (batch_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [LoanRecord(**self._row_to_dict(r)) for r in rows]
        finally:
            self._close_conn(conn)

    def create_batch_loans(self, batch_id: str, rows: List[LoanCreate]) -> List[LoanRecord]:
        """Atomically insert an initial batch of draft loan records."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.cursor()
            for idx, loan in enumerate(rows, start=1):
                confidences_json = json.dumps(loan.confidences or {})
                raw_ocr_json = json.dumps(loan.raw_ocr_data) if loan.raw_ocr_data is not None else None
                verified_int = 1 if loan.verified else 0
                row_idx = loan.row_index if loan.row_index is not None else idx
                cursor.execute(
                    """
                    INSERT INTO loans (
                        batch_id, row_index, serial_number, name, mobile, address, amount,
                        image_path, raw_ocr_data, confidences, ocr_engine_used,
                        verified, verified_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        row_idx,
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

        return self.get_batch_loans(batch_id)

    def save_and_verify_batch(
        self,
        batch_id: str,
        rows: List[Union[Dict[str, Any], Any]],
        deleted_ids: Optional[List[int]] = None,
    ) -> List[LoanRecord]:
        """
        Atomically save and verify all rows in a batch inside a single SQLite transaction.
        Uses BEGIN IMMEDIATE ... COMMIT; with rollback on constraint violations or errors.
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.cursor()

            # Handle deletions if requested
            if deleted_ids:
                for del_id in deleted_ids:
                    cursor.execute(
                        "DELETE FROM loans WHERE id = ? AND (batch_id = ? OR batch_id IS NULL)",
                        (del_id, batch_id),
                    )

            # Process rows
            for idx, r in enumerate(rows, start=1):
                if hasattr(r, "model_dump"):
                    row_data = r.model_dump()
                elif isinstance(r, dict):
                    row_data = r
                else:
                    row_data = dict(r)

                row_idx = row_data.get("row_index") or idx
                serial = str(row_data.get("serial_number") or f"LN-{batch_id[-4:]}-{row_idx:03d}")
                name = str(row_data.get("name") or row_data.get("borrower_name") or "")
                mobile = str(row_data.get("mobile") or row_data.get("mobile_number") or "")
                address = str(row_data.get("address") or "")
                raw_amount = row_data.get("amount") if "amount" in row_data else row_data.get("loan_amount")
                if raw_amount is None:
                    raise sqlite3.IntegrityError(f"Missing loan amount for row {row_idx}")

                try:
                    amount = float(raw_amount)
                except (ValueError, TypeError) as exc:
                    raise sqlite3.IntegrityError(f"Invalid amount for row {row_idx}: {raw_amount}") from exc

                # Constraint check: amount must be > 0
                if amount <= 0:
                    raise sqlite3.IntegrityError(
                        f"Constraint check failed: amount must be positive for row {row_idx}, got {amount}"
                    )

                record_id = row_data.get("id") or row_data.get("loan_id")
                confidences = row_data.get("confidences") or {}
                conf_json = json.dumps(confidences) if isinstance(confidences, dict) else str(confidences)
                ocr_engine = str(row_data.get("ocr_engine_used") or "batch_grid")
                image_path = row_data.get("image_path")

                project_type = str(row_data.get("project_type") or "loan")
                
                # Check if record already exists in DB
                existing_id = None
                if record_id:
                    cursor.execute("SELECT id FROM loans WHERE id = ?", (record_id,))
                    row_match = cursor.fetchone()
                    if row_match:
                        existing_id = row_match[0]

                if not existing_id:
                    # Check by batch_id and row_index or serial_number
                    cursor.execute(
                        "SELECT id FROM loans WHERE batch_id = ? AND (row_index = ? OR serial_number = ?)",
                        (batch_id, row_idx, serial),
                    )
                    row_match = cursor.fetchone()
                    if row_match:
                        existing_id = row_match[0]

                if existing_id:
                    cursor.execute(
                        """
                        UPDATE loans SET
                            batch_id = ?,
                            row_index = ?,
                            project_type = ?,
                            serial_number = ?,
                            name = ?,
                            mobile = ?,
                            address = ?,
                            amount = ?,
                            confidences = ?,
                            verified = 1,
                            verified_at = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            batch_id,
                            row_idx,
                            project_type,
                            serial,
                            name,
                            mobile,
                            address,
                            amount,
                            conf_json,
                            now,
                            now,
                            existing_id,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO loans (
                            batch_id, row_index, project_type, serial_number, name, mobile, address, amount,
                            image_path, confidences, ocr_engine_used,
                            verified, verified_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                        """,
                        (
                            batch_id,
                            row_idx,
                            project_type,
                            serial,
                            name,
                            mobile,
                            address,
                            amount,
                            image_path,
                            conf_json,
                            ocr_engine,
                            now,
                            now,
                            now,
                        ),
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

        return self.get_batch_loans(batch_id)

