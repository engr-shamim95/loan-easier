"""Pytest configuration and shared fixtures for Loan Easier test suite."""

import os
import sys
from pathlib import Path
from typing import Generator, Dict, Any
import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.mock_images import (
    FIXTURES_DIR,
    SAMPLE_LOAN_DATA,
    generate_all_fixtures,
    get_fixture_bytes,
    get_fixture_path,
)

@pytest.fixture(scope="session", autouse=True)
def setup_test_fixtures():
    """Ensure all mock image fixtures exist before running tests."""
    generate_all_fixtures()

@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provide a temporary, isolated SQLite database path for tests."""
    db_file = tmp_path / "test_loan_records.db"
    return db_file

@pytest.fixture
def loan_repo(temp_db_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide an isolated LoanRepository pointing to a temporary SQLite database."""
    import src.config
    import src.db.repository
    import src.db.connection
    monkeypatch.setattr(src.config, "DB_PATH", temp_db_path)
    monkeypatch.setattr(src.db.repository, "DB_PATH", temp_db_path)
    monkeypatch.setattr(src.db.connection, "DB_PATH", temp_db_path)

    from src.db.repository import LoanRepository
    return LoanRepository(db_path=temp_db_path)

@pytest.fixture
def clean_loan_payload() -> Dict[str, Any]:
    """Provide standard clean loan application dictionary."""
    return {
        "serial_number": "LN-2026-9042",
        "name": "Jane Doe",
        "mobile": "+1-555-234-5678",
        "address": "742 Evergreen Terrace, Springfield, IL 62704",
        "amount": 25000.00,
    }

@pytest.fixture
def sample_loan_record(loan_repo, clean_loan_payload):
    """Create an unverified loan record in the database."""
    from src.db.models import LoanCreate
    payload = LoanCreate(
        serial_number=clean_loan_payload["serial_number"],
        name=clean_loan_payload["name"],
        mobile=clean_loan_payload["mobile"],
        address=clean_loan_payload["address"],
        amount=clean_loan_payload["amount"],
        ocr_engine_used="gcp_vision",
        confidences={
            "serial_number": 0.95,
            "name": 0.94,
            "mobile": 0.92,
            "address": 0.91,
            "amount": 0.96,
        },
        verified=False,
    )
    return loan_repo.create_loan(payload)

@pytest.fixture
def sample_verified_loan_record(loan_repo, clean_loan_payload):
    """Create a verified loan record in the database."""
    from src.db.models import LoanCreate
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    payload = LoanCreate(
        serial_number="LN-2026-VERIFIED-01",
        name=clean_loan_payload["name"],
        mobile=clean_loan_payload["mobile"],
        address=clean_loan_payload["address"],
        amount=clean_loan_payload["amount"],
        ocr_engine_used="gcp_vision",
        confidences={
            "serial_number": 0.95,
            "name": 0.94,
            "mobile": 0.92,
            "address": 0.91,
            "amount": 0.96,
        },
        verified=True,
        verified_at=now,
    )
    return loan_repo.create_loan(payload)

@pytest.fixture
def client(temp_db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient fixture configured with isolated SQLite DB
    and mock environment variables.
    """
    import src.config
    import src.db.repository
    import src.db.connection
    from src.db.schema import init_db
    monkeypatch.setattr(src.config, "DB_PATH", temp_db_path)
    monkeypatch.setattr(src.db.repository, "DB_PATH", temp_db_path)
    monkeypatch.setattr(src.db.connection, "DB_PATH", temp_db_path)

    init_db(temp_db_path)

    from src.api.app import app
    with TestClient(app) as test_client:
        yield test_client
