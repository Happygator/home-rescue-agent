"""Unit tests for agent tool functions in appliance_fixer/agent.py."""
from __future__ import annotations

import gc
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from appliance_fixer.case_store import CaseStore
from appliance_fixer.agent import (
    verify_model_number,
    reopen_existing_case,
    initialize_new_case,
    lookup_fixes,
    record_step_result,
    generate_escalation_draft,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing agent tools."""
    db_path = Path("test_temp_agent_tools.db")
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


def test_verify_model_number():
    """Test verify_model_number with supported and unsupported models."""
    res = verify_model_number("RSG257", "Samsung")
    assert res["valid"] is True
    assert res["matched_model"] == "RSG257"

    res_invalid = verify_model_number("UNKNOWN123", "Samsung")
    assert res_invalid["valid"] is False


def test_initialize_new_case(temp_db):
    """Test initializing a new case in the database."""
    context = MagicMock()
    context.state = {"db_path": str(temp_db)}
    
    res = initialize_new_case(
        appliance="refrigerator",
        brand="Samsung",
        model_number="RSG257",
        symptom_text="warm freezer",
        error_code="",
        tool_context=context,
    )
    
    assert res["success"] is True
    case_id = res["case_id"]
    assert case_id.startswith("case-")
    
    # Verify in state
    assert context.state["case_id"] == case_id
    assert context.state["brand"] == "Samsung"
    assert context.state["model_number"] == "RSG257"
    
    # Verify database record
    store = CaseStore(temp_db)
    case = store.load_case(case_id)
    assert case is not None
    assert case["brand"] == "Samsung"
    assert case["data"]["symptom_text"] == "warm freezer"


def test_reopen_existing_case(temp_db):
    """Test reopening an existing case and reloading state."""
    store = CaseStore(temp_db)
    store.new_case(
        case_id="case-101",
        user_id="user-1",
        appliance="refrigerator",
        brand="LG",
        model_number="LFXS26",
        status="diagnosing",
        symptom_text="ice maker not working",
    )
    
    context = MagicMock()
    context.state = {"db_path": str(temp_db)}
    
    res = reopen_existing_case("case-101", context)
    assert res["success"] is True
    assert res["brand"] == "LG"
    assert res["model_number"] == "LFXS26"
    assert "LG LFXS26" in res["recap"]
    
    assert context.state["case_id"] == "case-101"
    assert context.state["brand"] == "LG"
    assert context.state["model_number"] == "LFXS26"
    assert context.state["symptom_text"] == "ice maker not working"


def test_lookup_fixes():
    """Test looking up fixes for a symptom."""
    res = lookup_fixes("refrigerator", "Samsung", "RSG257", "warm fridge", "")
    assert "fixes" in res
    assert len(res["fixes"]) > 0


def test_record_step_result(temp_db):
    """Test recording a troubleshooting step result."""
    store = CaseStore(temp_db)
    store.new_case("case-202", "user-1", "refrigerator", "GE", "GSS25", "diagnosing", "warm fridge")
    
    context = MagicMock()
    context.state = {"db_path": str(temp_db), "history_summary": ""}
    
    res = record_step_result(
        case_id="case-202",
        step_id=1,
        instruction="Clean coils",
        user_result="vacuumed them",
        outcome="not_resolved",
        tool_context=context,
    )
    
    assert res["success"] is True
    
    # Verify in DB
    case = store.load_case("case-202")
    steps = case["data"]["steps"]
    assert len(steps) == 1
    assert steps[0]["instruction"] == "Clean coils"
    assert steps[0]["outcome"] == "not_resolved"


def test_generate_escalation_draft(temp_db):
    """Test generating an escalation email draft."""
    store = CaseStore(temp_db)
    store.new_case("case-303", "user-1", "refrigerator", "Samsung", "RSG257", "diagnosing", "warm fridge")
    
    context = MagicMock()
    context.state = {"db_path": str(temp_db), "history_summary": ""}
    
    res = generate_escalation_draft("case-303", context)
    assert res["success"] is True
    assert "recipient" in res["draft"]
    assert res["draft"]["recipient"] == "support@samsung.com"
