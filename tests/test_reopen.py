"""Unit tests for the reopen module."""
from __future__ import annotations

import gc
import sqlite3
import subprocess
import sys
from pathlib import Path
import pytest

from appliance_fixer.case_store import CaseStore
from appliance_fixer.reopen import reopen_case


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    db_path = Path("test_temp_reopen.db")
    if db_path.exists():
        db_path.unlink()
    
    yield db_path

    # Cleanup
    gc.collect()
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            import time
            time.sleep(0.1)
            gc.collect()
            if db_path.exists():
                db_path.unlink()


def test_reopen_success(temp_db):
    """Test successful case reopening and state rehydration."""
    store = CaseStore(temp_db)
    store.new_case(
        case_id="case-abc",
        user_id="user-123",
        appliance="refrigerator",
        brand="LG",
        model_number="LFX123",
        status="awaiting_user",
        symptom_text="fridge warm",
    )
    
    case, recap = reopen_case("case-abc", store)
    assert case["case_id"] == "case-abc"
    assert "LG LFX123" in recap
    assert "fridge warm" in recap


def test_reopen_missing(temp_db):
    """Test that reopening a missing case raises ValueError."""
    store = CaseStore(temp_db)
    with pytest.raises(ValueError, match="Case 'missing-id' not found"):
        reopen_case("missing-id", store)


def test_reopen_corrupt(temp_db):
    """Test that a case with corrupt JSON raises ValueError."""
    store = CaseStore(temp_db)
    # Insert corrupt case manually bypass save_case json encoding
    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            """
            INSERT INTO cases (case_id, user_id, status, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("corrupt-id", "user-1", "intake", "invalid-json-content", "now", "now"),
        )
        conn.commit()

    with pytest.raises(ValueError, match="corrupt or missing data"):
        reopen_case("corrupt-id", store)


def test_reopen_cli_success(temp_db):
    """Test running the reopen script as a CLI command (success)."""
    store = CaseStore(temp_db)
    store.new_case("case-cli", "user-1", "refrigerator", "Samsung", "RF999", "intake", "not cooling")
    
    # Run python reopen.py case-cli --db temp_db
    # We must set PYTHONPATH so import works
    cmd = [sys.executable, "-m", "appliance_fixer.reopen", "case-cli", "--db", str(temp_db)]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": ".", **subprocess.os.environ},
    )
    
    assert res.returncode == 0
    assert "Samsung RF999" in res.stdout
    assert "not cooling" in res.stdout


def test_reopen_cli_missing(temp_db):
    """Test running the reopen script as a CLI command for a missing case."""
    # Ensure database exists
    store = CaseStore(temp_db)
    
    cmd = [sys.executable, "-m", "appliance_fixer.reopen", "missing-case", "--db", str(temp_db)]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": ".", **subprocess.os.environ},
    )
    
    assert res.returncode != 0
    assert "Error: Case 'missing-case' not found" in res.stderr
