"""Thread-safe SQLite database connection manager."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Union
from src.config import DB_PATH

_thread_local = threading.local()

def configure_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Apply required SQLite pragmas for thread safety, WAL mode, and timeouts."""
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()
    return conn

def get_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """
    Create a newly configured SQLite connection.
    If db_path is omitted, defaults to configured DB_PATH.
    If ':memory:' is requested, uses shared memory URI so multiple connections
    access the same in-memory database.
    """
    path = str(db_path or DB_PATH)
    uri = False

    if path == ":memory:":
        path = "file:loan_memdb?mode=memory&cache=shared"
        uri = True
    elif path.startswith("file:"):
        uri = True
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        path,
        timeout=10.0,
        check_same_thread=False,
        isolation_level=None,  # autocommit mode, transactions handled explicitly
        uri=uri
    )
    return configure_connection(conn)

@contextmanager
def get_db(db_path: Optional[Union[str, Path]] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager yielding a thread-safe connection.
    Wraps operations in an atomic transaction.
    """
    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
