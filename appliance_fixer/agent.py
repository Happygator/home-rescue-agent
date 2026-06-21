"""Agent configuration and tools for Appliance Fixer."""
from __future__ import annotations

import uuid
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext

from appliance_fixer.case_store import CaseStore
from appliance_fixer.reopen import reopen_case
from appliance_fixer.grounding import get_fixes
from appliance_fixer.tools import validate_model, read_plate, draft_escalation
from appliance_fixer.safety import before_model_callback


async def initialize_state(callback_context: CallbackContext) -> None:
    """Initialize session state variables to avoid KeyError in prompt formatting."""
    state = callback_context.state
    defaults = {
        "case_id": "Unknown",
        "brand": "Unknown",
        "model_number": "Unknown",
        "appliance": "refrigerator",
        "symptom_text": "None",
        "error_code": "None",
        "history_summary": "No prior history.",
        "db_path": "appliance_fixer.db",
    }
    for k, v in defaults.items():
        if k not in state:
            state[k] = v


def read_spec_plate(photo_path: str) -> dict:
    """Read the spec/model plate of an appliance from a photo to extract details.

    Args:
        photo_path: The absolute path to the photo of the spec plate.

    Returns:
        A dictionary with keys 'brand', 'model_number', and 'error_code'.
    """
    try:
        return read_plate(photo_path)
    except Exception as e:
        return {"brand": None, "model_number": None, "error_code": None, "error": str(e)}


def verify_model_number(model_number: str, brand: str) -> dict:
    """Verify if the model number is supported in the system.

    Args:
        model_number: The model number extracted from the plate or entered by the user.
        brand: The brand of the appliance.

    Returns:
        A dictionary with 'valid' (bool) and 'matched_model' (str or null).
    """
    matched = validate_model(model_number, brand)
    return {"valid": matched is not None, "matched_model": matched}


def reopen_existing_case(case_id: str, tool_context: ToolContext) -> dict:
    """Reopen an existing case using its unique case ID and load its history.

    Args:
        case_id: The unique ID of the case to reopen.

    Returns:
        A dictionary with 'success' (bool), 'recap' (str), 'brand', and 'model_number'.
    """
    db_path = tool_context.state.get("db_path", "appliance_fixer.db")
    store = CaseStore(db_path)
    try:
        case, recap_text = reopen_case(case_id, store)
        tool_context.state["case_id"] = case_id
        tool_context.state["brand"] = case.get("brand") or "Unknown"
        tool_context.state["model_number"] = case.get("model_number") or "Unknown"
        tool_context.state["appliance"] = case.get("appliance") or "refrigerator"
        tool_context.state["symptom_text"] = case["data"].get("symptom_text") or "None"
        tool_context.state["error_code"] = case["data"].get("error_code") or "None"
        tool_context.state["history_summary"] = recap_text
        return {
            "success": True,
            "recap": recap_text,
            "brand": tool_context.state["brand"],
            "model_number": tool_context.state["model_number"],
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}


def initialize_new_case(
    appliance: str, brand: str, model_number: str, symptom_text: str, error_code: str, tool_context: ToolContext
) -> dict:
    """Initialize a new troubleshooting case in the database.

    Args:
        appliance: The type of appliance (e.g., 'refrigerator').
        brand: The manufacturer brand name (e.g., 'Samsung').
        model_number: The validated model number of the appliance.
        symptom_text: A description of the problem/symptom.
        error_code: Any active error code shown on the display (or empty string if none).

    Returns:
        A dictionary representing the created case, containing 'case_id'.
    """
    db_path = tool_context.state.get("db_path", "appliance_fixer.db")
    store = CaseStore(db_path)
    case_id = f"case-{str(uuid.uuid4())[:8]}"
    ec_val = error_code if error_code and error_code.lower() != "none" else None
    
    store.new_case(
        case_id=case_id,
        user_id="user-default",
        appliance=appliance,
        brand=brand,
        model_number=model_number,
        status="diagnosing",
        symptom_text=symptom_text,
    )
    
    if ec_val:
        store.save_case(case_id, error_code=ec_val)

    tool_context.state["case_id"] = case_id
    tool_context.state["brand"] = brand
    tool_context.state["model_number"] = model_number
    tool_context.state["appliance"] = appliance
    tool_context.state["symptom_text"] = symptom_text
    tool_context.state["error_code"] = error_code or "None"
    tool_context.state["history_summary"] = store.recap(case_id)

    return {"success": True, "case_id": case_id}


def lookup_fixes(appliance: str, brand: str, model_number: str, symptom: str, error_code: str) -> dict:
    """Look up safety-approved repair steps/fixes for the symptom and model.

    Args:
        appliance: The type of appliance (e.g., 'refrigerator').
        brand: The brand name of the appliance.
        model_number: The model number.
        symptom: The symptom description.
        error_code: Any active error code (or empty string if none).

    Returns:
        A dictionary with a list of 'fixes'.
    """
    ec_val = error_code if error_code and error_code.lower() != "none" else None
    fixes = get_fixes(appliance, brand, model_number, symptom, ec_val)
    return {"fixes": fixes}


def record_step_result(
    case_id: str, step_id: int, instruction: str, user_result: str, outcome: str, tool_context: ToolContext
) -> dict:
    """Record the outcome of a troubleshooting step performed by the user.

    Args:
        case_id: The unique ID of the case.
        step_id: The sequential number of the step (starting from 1).
        instruction: The instruction/action that was performed.
        user_result: The description of what the user observed/did.
        outcome: The result of the check (must be one of 'resolved', 'not_resolved', 'unsure', 'skipped').

    Returns:
        A dictionary with 'success' (bool).
    """
    db_path = tool_context.state.get("db_path", "appliance_fixer.db")
    store = CaseStore(db_path)
    case = store.load_case(case_id)
    if not case:
        return {"success": False, "error": "Case not found."}

    steps = case["data"].get("steps", [])
    # Append the new step
    steps.append({
        "step_id": step_id,
        "instruction": instruction,
        "user_result": user_result,
        "outcome": outcome,
    })

    status = "resolved" if outcome.lower() == "resolved" else "diagnosing"
    
    # Save the updated steps
    store.save_case(case_id, steps=steps, status=status)
    tool_context.state["history_summary"] = store.recap(case_id)

    return {"success": True}


def generate_escalation_draft(case_id: str, tool_context: ToolContext) -> dict:
    """Generate a service escalation email draft summarizing all findings and steps taken.

    Args:
        case_id: The unique ID of the case.

    Returns:
        A dictionary containing the 'recipient', 'subject', and 'body' of the draft.
    """
    db_path = tool_context.state.get("db_path", "appliance_fixer.db")
    store = CaseStore(db_path)
    draft = draft_escalation(case_id, store)
    if not draft:
        return {"success": False, "error": "Failed to generate draft."}
    
    tool_context.state["history_summary"] = store.recap(case_id)
    return {"success": True, "draft": draft}


system_instruction = """You are a helpful, professional, safety-first household appliance troubleshooting assistant.
Current Case Information:
- Case ID: {case_id}
- Appliance Type: {appliance}
- Brand: {brand}
- Model Number: {model_number}
- Symptom: {symptom_text}
- Error Code: {error_code}

Prior History Recap:
{history_summary}

Your task is to guide the user in diagnosing and fixing their appliance (refrigerator is our primary focus).
Follow these guidelines:
1. Intake Phase: If the brand or model number is unknown, ask the user to provide them or upload a photo of the appliance spec plate. If they upload a photo, use the `read_spec_plate` tool with the path to the photo to extract details, then use `verify_model_number` to check if it's supported.
2. Case Creation Phase: If this is a new case and you have the brand, model, and symptom, use `initialize_new_case` to register the case and get a case ID. Mention the case ID to the user.
3. Reopening Phase: If the user requests to reopen/resume a case, call `reopen_existing_case` with their case ID to load all previous steps and state. Show them the recap.
4. Diagnostics Phase: Once the appliance brand/model is validated, use `lookup_fixes` to find recommended troubleshooting steps. Suggest the fixes one by one, from easiest/safest to most complex.
5. Ingestion/Verification Phase: After proposing a step, ask the user if they completed it and what the outcome was. Use `record_step_result` to log the result of each step. Set outcome to 'resolved' if it fixed the issue, 'not_resolved' if it didn't, or 'unsure'/'skipped'.
6. Escalation Phase: If all fixes are exhausted and the issue is not resolved, or if the user requests a professional technician, call `generate_escalation_draft` to draft a support email recap and set status to escalated. Tell the user we have prepared the draft.
7. Safety rules: Do NOT recommend any actions involving gas lines, high/mains voltage testing/wiring, sealed refrigerant systems, or water leaking onto electrical elements. Refer them to professional service if they request these or if the issue is too dangerous.
"""

root_agent = Agent(
    name="appliance_fixer_agent",
    model="gemini-2.5-flash",
    instruction=system_instruction,
    tools=[
        read_spec_plate,
        verify_model_number,
        reopen_existing_case,
        initialize_new_case,
        lookup_fixes,
        record_step_result,
        generate_escalation_draft,
    ],
    before_agent_callback=initialize_state,
    before_model_callback=before_model_callback,
)
