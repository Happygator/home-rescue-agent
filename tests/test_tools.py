"""Unit tests for appliance_fixer.tools."""
from __future__ import annotations

import gc
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from appliance_fixer.case_store import CaseStore
from appliance_fixer.tools import validate_model, draft_escalation, read_plate


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    db_path = Path("test_temp_tools.db")
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


def test_validate_model_exact():
    """Test exact matches and casing normalization."""
    assert validate_model("RSG257", "Samsung") == "RSG257"
    assert validate_model("rsg257", "samsung") == "RSG257"
    assert validate_model("GSS25", "GE") == "GSS25"


def test_validate_model_cleanup():
    """Test stripping spaces and suffixes."""
    assert validate_model("rsg 257  ", "Samsung") == "RSG257"
    assert validate_model("RF28T5001SR/AA", "Samsung") == "RF28T5001SR"
    assert validate_model("WRFF3336SZ 00", "Whirlpool") == "WRFF3336SZ"


def test_validate_model_ocr_canonicalization():
    """Test handling O/0 and I/1 confusions."""
    # O instead of 0
    assert validate_model("WFW95HEDWO", "Whirlpool") == "WFW95HEDW0"
    # lowercase l instead of I
    assert validate_model("MFl257", "Maytag") == "MFI257"
    # number 1 instead of I
    assert validate_model("MF1257", "Maytag") == "MFI257"


def test_validate_model_invalid():
    """Test that invalid models return None."""
    assert validate_model("INVALID123", "Samsung") is None
    assert validate_model("RSG257", "LG") is None  # mismatching brand


def test_draft_escalation(temp_db):
    """Test drafting escalation email and persisting to SQLite."""
    store = CaseStore(temp_db)
    store.new_case(
        case_id="case-esc-1",
        user_id="user-1",
        appliance="refrigerator",
        brand="Samsung",
        model_number="RSG257",
        status="diagnosing",
        symptom_text="warm fridge",
    )
    
    draft = draft_escalation("case-esc-1", store)
    assert draft is not None
    assert draft["recipient"] == "support@samsung.com"
    assert "Service Request" in draft["subject"]
    assert "warm fridge" in draft["body"]
    
    # Verify in DB
    case = store.load_case("case-esc-1")
    assert case["status"] == "escalated"
    assert case["data"]["escalation"] is not None
    assert case["data"]["escalation"]["recipient"] == "support@samsung.com"
    assert case["data"]["escalation"]["sent"] is False


@patch("google.genai.Client")
def test_read_plate_mock(mock_client_class):
    """Test read_plate by mocking the Google GenAI Client response."""
    # Set up mock response
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.text = '{"brand": "Samsung", "model_number": "RSG257", "error_code": null}'
    mock_client.models.generate_content.return_value = mock_response

    # Create dummy photo file to satisfy Path.exists()
    dummy_file = Path("dummy_plate.jpg")
    dummy_file.write_bytes(b"image content")

    try:
        with patch("appliance_fixer.tools.load_key", return_value="fake-key"):
            res = read_plate(dummy_file)
            
        assert res["brand"] == "Samsung"
        assert res["model_number"] == "RSG257"
        assert res["error_code"] is None
    finally:
        if dummy_file.exists():
            dummy_file.unlink()
