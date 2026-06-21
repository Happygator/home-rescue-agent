"""Unit tests for CaseStore."""
from __future__ import annotations

import gc
from pathlib import Path
import pytest

from appliance_fixer.case_store import CaseStore


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    db_path = Path("test_temp_appliance_fixer.db")
    if db_path.exists():
        db_path.unlink()
    
    yield db_path
    
    # Force garbage collection to close any lingering SQLite file handles
    gc.collect()
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            # Fallback if Windows still holds a lock momentarily
            import time
            time.sleep(0.1)
            gc.collect()
            if db_path.exists():
                db_path.unlink()


def test_init_db(temp_db):
    """Test that CaseStore initializes correctly and creates the table."""
    store = CaseStore(temp_db)
    assert temp_db.exists()
    # Check if load_case on missing ID handles it gracefully
    assert store.load_case("missing-id") is None


def test_new_case(temp_db):
    """Test creating a new case and verifying default values."""
    store = CaseStore(temp_db)
    case = store.new_case(
        case_id="case-123",
        user_id="user-456",
        appliance="refrigerator",
        brand="Whirlpool",
        model_number="WRF123",
        status="intake",
        symptom_text="freezer warm",
    )
    
    assert case is not None
    assert case["case_id"] == "case-123"
    assert case["user_id"] == "user-456"
    assert case["appliance"] == "refrigerator"
    assert case["brand"] == "Whirlpool"
    assert case["model_number"] == "WRF123"
    assert case["status"] == "intake"
    
    # Check CaseFile JSON content
    data = case["data"]
    assert data["symptom_text"] == "freezer warm"
    assert data["error_code"] is None
    assert data["photos"] == []
    assert data["steps"] == []
    assert data["cache"] == {}
    assert data["diagnosis"] is None
    assert data["escalation"] is None


def test_save_case(temp_db):
    """Test saving updates to case metadata and JSON payload."""
    store = CaseStore(temp_db)
    store.new_case("case-1", "user-1", "washer", "LG", "WM100", "intake", "wont drain")
    
    # Update some metadata and JSON fields
    success = store.save_case(
        case_id="case-1",
        status="diagnosing",
        error_code="OE",
        photos=[{"kind": "symptom", "ref": "photo.jpg", "taken_at": "2026-06-21"}],
    )
    
    assert success is True
    
    # Reload and check values
    case = store.load_case("case-1")
    assert case["status"] == "diagnosing"
    assert case["brand"] == "LG"  # preserved
    assert case["data"]["error_code"] == "OE"
    assert len(case["data"]["photos"]) == 1
    assert case["data"]["photos"][0]["ref"] == "photo.jpg"
    
    # Check that unsaved keys (like cache) are preserved
    assert case["data"]["cache"] == {}


def test_save_case_nonexistent(temp_db):
    """Test saving a nonexistent case ID returns False."""
    store = CaseStore(temp_db)
    assert store.save_case("fake-id", status="some-status") is False


def test_recap(temp_db):
    """Test generating a user-readable case summary."""
    store = CaseStore(temp_db)
    store.new_case("case-999", "user-1", "dishwasher", "Bosch", "SHX863", "diagnosing", "gritty dishes")
    
    # Perform some steps
    steps = [
        {"step_id": 1, "instruction": "Clean filter", "user_result": "done", "outcome": "not_resolved"},
        {"step_id": 2, "instruction": "Check spray arm", "user_result": "cleared clogs", "outcome": "resolved"}
    ]
    store.save_case("case-999", steps=steps, diagnosis={"hypothesis": "clogged spray arm", "confidence": "high"})
    
    summary = store.recap("case-999")
    
    assert "=== Case Recap: case-999 ===" in summary
    assert "Status: DIAGNOSING" in summary
    assert "Appliance: Bosch SHX863 (dishwasher)" in summary
    assert "Symptom: gritty dishes" in summary
    assert "1. [Outcome: NOT_RESOLVED] Clean filter -> Result: done" in summary
    assert "2. [Outcome: RESOLVED] Check spray arm -> Result: cleared clogs" in summary
    assert "Diagnosis: clogged spray arm (Confidence: high)" in summary


def test_recap_missing(temp_db):
    """Test recap on missing case."""
    store = CaseStore(temp_db)
    assert store.recap("missing") == "Case not found."
