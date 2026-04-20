"""E2E test fixtures for dashboard API testing."""

import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

# Mock email_validator module before any imports
sys.modules["email_validator"] = MagicMock()

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path so dashboard can be imported as a package
root_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_path))

from dashboard.app import app


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    # Run migrations
    conn = sqlite3.connect(db_path)
    try:
        migrations_dir = Path(__file__).parent.parent.parent.parent / "dashboard" / "migrations"

        # Read and execute all migration files in order
        for migration_file in sorted(migrations_dir.glob("*.sql")):
            with open(migration_file, "r", encoding="utf-8") as f:
                sql = f.read()
                conn.executescript(sql)

        conn.commit()
    finally:
        conn.close()

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def client(monkeypatch, temp_db) -> TestClient:
    """Create a test client with a temporary database."""
    # Monkey-patch the THEBRANCH_DB path in the app module
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "THEBRANCH_DB", Path(temp_db))

    return TestClient(app)
