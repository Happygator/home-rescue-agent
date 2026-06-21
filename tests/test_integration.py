"""Integration tests for CaseStore and Reopen flows."""
from __future__ import annotations

import gc
from pathlib import Path
import pytest

from appliance_fixer.case_store import CaseStore
from appliance_fixer.reopen import reopen_case


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    db_path = Path("test_temp_integration.db")
    if db_path.exists():
        db_path.unlink()
    
    yield db_path

    # Force cleanup to release Windows file locks
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


def test_end_to_end_reopen_flow(temp_db):
    """Test the complete lifecyle of a case: create -> modify -> reopen -> recap."""
    store = CaseStore(temp_db)
    case_id = "case-integration-1"
    user_id = "user-999"

    # 1. Create a new case
    case = store.new_case(
        case_id=case_id,
        user_id=user_id,
        appliance="refrigerator",
        brand="Whirlpool",
        model_number="WRF560SEHZ",
        status="intake",
        symptom_text="ice maker not working",
    )
    assert case["case_id"] == case_id
    assert case["status"] == "intake"
    assert case["data"]["symptom_text"] == "ice maker not working"

    # 2. Add troubleshooting steps (simulate a diagnostic loop)
    steps = [
        {"step_id": 1, "instruction": "Check water filter status", "user_result": "recently replaced", "outcome": "not_resolved"},
        {"step_id": 2, "instruction": "Check fill tube for ice blockage", "user_result": "clear of ice", "outcome": "not_resolved"},
    ]
    diagnosis = {"hypothesis": "failed water inlet valve", "confidence": "medium"}
    
    success = store.save_case(
        case_id=case_id,
        status="diagnosing",
        error_code="E2",
        steps=steps,
        diagnosis=diagnosis,
    )
    assert success is True

    # 3. Simulate a fresh session reopening this case by ID
    fresh_store = CaseStore(temp_db)
    reopened_case, recap_text = reopen_case(case_id, fresh_store)

    # Verify state was correctly rehydrated
    assert reopened_case["case_id"] == case_id
    assert reopened_case["status"] == "diagnosing"
    assert reopened_case["brand"] == "Whirlpool"
    assert reopened_case["model_number"] == "WRF560SEHZ"
    assert reopened_case["data"]["error_code"] == "E2"
    assert len(reopened_case["data"]["steps"]) == 2
    assert reopened_case["data"]["diagnosis"]["hypothesis"] == "failed water inlet valve"

    # Verify the recap contains all history
    assert "=== Case Recap: case-integration-1 ===" in recap_text
    assert "Status: DIAGNOSING" in recap_text
    assert "Appliance: Whirlpool WRF560SEHZ (refrigerator)" in recap_text
    assert "Symptom: ice maker not working" in recap_text
    assert "1. [Outcome: NOT_RESOLVED] Check water filter status -> Result: recently replaced" in recap_text
    assert "2. [Outcome: NOT_RESOLVED] Check fill tube for ice blockage -> Result: clear of ice" in recap_text
    assert "Diagnosis: failed water inlet valve (Confidence: medium)" in recap_text
