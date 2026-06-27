import asyncio

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from home_rescue.case_store import CaseStore
from home_rescue.escalation import escalate_case
from home_rescue.safety import (
    after_model_callback,
    before_tool_callback,
    scan_for_danger,
)


class FakeCtx:
    def __init__(self, state):
        self.state = state


class FakeTool:
    name = "record_step_result"


class FakeResponse:
    def __init__(self, text):
        self.content = types.Content(role="model", parts=[types.Part(text=text)])


def _case_store(tmp_path, case_id="case-safety"):
    store = CaseStore(tmp_path / f"{case_id}.db")
    store.new_case(
        case_id,
        "user-1",
        appliance="refrigerator",
        brand="Samsung",
        model_number="RF28R7201",
        status="diagnosing",
        symptom_text="Fresh food section is warm while freezer is still cold.",
        error_code="OF OF",
    )
    return store


def _state(tmp_path, case_id="case-safety"):
    return {"case_id": case_id, "db_path": tmp_path / f"{case_id}.db"}


def _response_text(llm_response):
    return " ".join(
        part.text
        for part in llm_response.content.parts
        if getattr(part, "text", None)
    )


def test_scan_trips_on_dangerous_instruction():
    dangerous, reason = scan_for_danger(
        "Disconnect the gas line and clean the burner assembly."
    )
    assert dangerous is True
    assert "gas" in reason

    dangerous, reason = scan_for_danger(
        "Test the live wires with the power on."
    )
    assert dangerous is True
    assert "electrical" in reason

    dangerous, reason = scan_for_danger(
        "Recharge the refrigerant in the sealed system."
    )
    assert dangerous is True
    assert "refrigerant" in reason


def test_scan_does_not_trip_on_refusal():
    assert scan_for_danger(
        "I won't advise gas-line or mains-voltage work - that needs a pro."
    ) == (False, None)
    assert scan_for_danger(
        "Never open the sealed refrigerant system; call a professional."
    ) == (False, None)


def test_scan_ignores_safe_steps():
    assert scan_for_danger(
        "Vacuum the condenser coils and check the door seal."
    ) == (False, None)


def test_after_model_forces_refusal(tmp_path):
    case_id = "case-after-danger"
    store = _case_store(tmp_path, case_id=case_id)
    ctx = FakeCtx(_state(tmp_path, case_id=case_id))
    resp = FakeResponse("Disconnect the gas line and clean the burner assembly.")

    result = asyncio.run(after_model_callback(ctx, resp))

    case = store.load_case(case_id)
    escalation = case["data"]["escalation"]
    assert isinstance(result, LlmResponse)
    assert "Safety stop" in _response_text(result)
    assert case["status"] == "escalated"
    assert escalation["safety_forced"] is True
    assert escalation["packet"]


def test_after_model_passes_safe_response():
    ctx = FakeCtx({})
    resp = FakeResponse("Vacuum the condenser coils and check the door seal.")

    assert asyncio.run(after_model_callback(ctx, resp)) is None


def test_before_tool_blocks_dangerous_args(tmp_path):
    case_id = "case-tool-danger"
    _case_store(tmp_path, case_id=case_id)
    ctx = FakeCtx(_state(tmp_path, case_id=case_id))

    result = before_tool_callback(
        FakeTool(),
        {"instruction": "open the sealed system and braze the compressor line"},
        ctx,
    )

    assert result["blocked"] is True
    assert result["reason"]
    assert before_tool_callback(
        FakeTool(),
        {"instruction": "Vacuum the condenser coils."},
        ctx,
    ) is None


def test_safety_forced_escalation_has_packet(tmp_path):
    case_id = "case-forced-packet"
    store = _case_store(tmp_path, case_id=case_id)

    escalate_case(case_id, store, safety_forced=True)
    case = store.load_case(case_id)
    escalation = case["data"]["escalation"]
    packet = escalation["packet"]

    assert escalation["safety_forced"] is True
    assert packet["shots_total"] > 0
    assert packet["summary"]
