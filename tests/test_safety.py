"""Unit tests for safety.py."""
from __future__ import annotations

import gc
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from appliance_fixer.case_store import CaseStore
from appliance_fixer.safety import before_model_callback


@pytest.fixture
def temp_db():
    """Create a temporary database for testing safety escalation."""
    db_path = Path("test_temp_safety.db")
    if db_path.exists():
        db_path.unlink()
    
    yield db_path

    # Cleanup SQLite lock
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


@pytest.mark.asyncio
async def test_before_model_callback_safe():
    """Test that safe queries pass through (return None)."""
    # Setup safe prompt
    content = types.Content(role="user", parts=[types.Part.from_text(text="My fridge is warm")])
    request = LlmRequest(contents=[content])
    
    context = MagicMock()
    context.state = {}
    
    res = await before_model_callback(context, request)
    assert res is None


@pytest.mark.asyncio
async def test_before_model_callback_dangerous_gas(temp_db):
    """Test that dangerous gas query is blocked and escalated."""
    store = CaseStore(temp_db)
    store.new_case("case-safe-1", "user-1", "refrigerator", "Samsung", "RSG257", "intake", "gas smell near kitchen")
    
    content = types.Content(role="user", parts=[types.Part.from_text(text="I think I have a gas leak near the stove burner")])
    request = LlmRequest(contents=[content])
    
    context = MagicMock()
    context.state = {"case_id": "case-safe-1", "db_path": str(temp_db)}
    
    res = await before_model_callback(context, request)
    
    assert res is not None
    assert "Safety Alert" in res.content.parts[0].text
    assert "gas system handling" in res.content.parts[0].text
    
    # Check that case was escalated in DB
    case = store.load_case("case-safe-1")
    assert case["status"] == "escalated"
    assert case["data"]["escalation"] is not None


@pytest.mark.asyncio
async def test_before_model_callback_dangerous_electrical():
    """Test that dangerous live wires query is blocked."""
    content = types.Content(role="user", parts=[types.Part.from_text(text="How do I test the capacitor or live wires?")])
    request = LlmRequest(contents=[content])
    
    context = MagicMock()
    context.state = {}
    
    res = await before_model_callback(context, request)
    
    assert res is not None
    assert "high-voltage electrical work" in res.content.parts[0].text
