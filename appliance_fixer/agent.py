"""Appliance Fixer agent: gather-then-fix loop (single ADK LlmAgent) + tool wiring.

The deterministic case logic lives in the _core helpers (store-based, no model); the ADK tool
wrappers adapt them to ToolContext. record_step_result drives status ONLY via transition().
"""
from __future__ import annotations

import datetime
import os
import uuid

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext

from appliance_fixer.case_store import CaseStore
from appliance_fixer.transitions import transition
from appliance_fixer.reopen import reopen_case
from appliance_fixer.grounding import get_fixes
from appliance_fixer.tools import read_spec_plate as _read_plate, validate_model, load_key
from appliance_fixer import escalation as esc
from appliance_fixer.safety import after_model_callback, before_tool_callback

AGENT_MODEL = os.environ.get("AGENT_MODEL", os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
DEFAULT_DB = "appliance_fixer.db"
VALID_OUTCOMES = ("resolved", "not_resolved", "unsure", "skipped")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _ensure_api_env():
    """Ensure google.genai (used by ADK) authenticates with the API key, not ADC.

    ADK's google.genai client auto-detects credentials; if GOOGLE_API_KEY is unset it can fall
    back to Application Default Credentials (an OAuth token) that the AI Studio endpoint rejects
    with ACCESS_TOKEN_TYPE_UNSUPPORTED. Having only GEMINI_API_KEY set does NOT prevent that, so
    always populate GOOGLE_API_KEY from the resolved key.
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        try:
            os.environ["GOOGLE_API_KEY"] = load_key()
        except Exception:
            pass
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "0")


# ---------- deterministic, store-based core (unit-tested directly) ----------

def core_initialize_new_case(store, appliance, brand, model_number, symptom_text, error_code=None):
    """Create a case (intake) then move it to diagnosing via transition(). Returns case_id."""
    case_id = "case-" + uuid.uuid4().hex[:8]
    ec = error_code if (error_code and str(error_code).lower() not in ("", "none")) else None
    store.new_case(case_id, "user-default", appliance=appliance, brand=brand,
                   model_number=model_number, status="intake", symptom_text=symptom_text, error_code=ec)
    case = store.load_case(case_id)
    store.save_case(case_id, status=transition(case, "start_diagnosis"))
    return case_id


def core_record_step_result(store, case_id, step_id, instruction, user_result, outcome):
    """Append a step and set status via transition() ONLY. Deterministic outcome mapping:
      resolved -> resolve (-> resolved)
      unsure   -> await_user (-> awaiting_user)
      not_resolved / skipped -> keep working (awaiting_user -> user_responded -> diagnosing,
                                                else stay diagnosing)
    Returns {success, outcome, status}.
    """
    case = store.load_case(case_id)
    if case is None:
        return {"success": False, "error": "Case not found."}
    o = (outcome or "").lower().strip()
    if o not in VALID_OUTCOMES:
        o = "unsure"
    steps = list((case.get("data") or {}).get("steps", []))
    steps.append({"step_id": step_id, "instruction": instruction, "asked_at": _now(),
                  "user_result": user_result, "outcome": o})

    cur = case["status"]
    if cur == "intake":
        cur = transition({"status": cur}, "start_diagnosis")  # promote before recording
    if o == "resolved":
        new_status = transition({"status": cur}, "resolve")
    elif o == "unsure":
        new_status = transition({"status": cur}, "await_user")
    else:  # not_resolved or skipped -> stay in the loop
        new_status = transition({"status": cur}, "user_responded") if cur == "awaiting_user" else cur
    store.save_case(case_id, steps=steps, status=new_status)
    return {"success": True, "outcome": o, "status": new_status}


# ---------- ADK helpers ----------

def _store(tool_context):
    return CaseStore(tool_context.state.get("db_path", DEFAULT_DB))


async def initialize_state(callback_context: CallbackContext) -> None:
    """Seed session state so prompt template keys never KeyError."""
    defaults = {
        "case_id": "Unknown", "brand": "Unknown", "model_number": "Unknown",
        "appliance": "refrigerator", "symptom_text": "None", "error_code": "None",
        "history_summary": "No prior history.", "db_path": DEFAULT_DB,
    }
    for k, v in defaults.items():
        if k not in callback_context.state:
            callback_context.state[k] = v


# ---------- ADK tool wrappers ----------

def read_spec_plate(photo_path: str) -> dict:
    """Read brand/model_number/error_code from a spec-plate photo.

    Args:
        photo_path: Absolute path to the spec-plate photo.
    Returns:
        dict with 'brand', 'model_number', 'error_code'.
    """
    try:
        return _read_plate(photo_path)
    except Exception as e:
        return {"brand": None, "model_number": None, "error_code": None, "error": str(e)}


def verify_model_number(model_number: str, brand: str) -> dict:
    """Validate a model number against supported models.

    Args:
        model_number: The model code read or typed.
        brand: The appliance brand.
    Returns:
        dict with 'valid' (bool) and 'matched_model' (str or null).
    """
    m = validate_model(model_number, brand)
    return {"valid": m is not None, "matched_model": m}


def reopen_existing_case(case_id: str, tool_context: ToolContext) -> dict:
    """Reopen a saved case by id and load its recap into the chat.

    Args:
        case_id: The case id to reopen.
    Returns:
        dict with 'success', 'recap', 'brand', 'model_number' (or 'error').
    """
    store = _store(tool_context)
    try:
        case, recap = reopen_case(case_id, store)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    s = tool_context.state
    s["case_id"] = case_id
    s["brand"] = case.get("brand") or "Unknown"
    s["model_number"] = case.get("model_number") or "Unknown"
    s["appliance"] = case.get("appliance") or "refrigerator"
    s["symptom_text"] = (case.get("data") or {}).get("symptom_text") or "None"
    s["error_code"] = (case.get("data") or {}).get("error_code") or "None"
    s["history_summary"] = recap
    return {"success": True, "recap": recap, "brand": s["brand"], "model_number": s["model_number"]}


def initialize_new_case(appliance: str, brand: str, model_number: str, symptom_text: str,
                        error_code: str, tool_context: ToolContext) -> dict:
    """Create a new troubleshooting case once appliance, brand, model, and symptom are known.

    Args:
        appliance: Appliance type (e.g. 'refrigerator').
        brand: Brand name.
        model_number: Validated model number.
        symptom_text: The problem in the user's words.
        error_code: Any code on the display, or '' if none.
    Returns:
        dict with 'success' and 'case_id'.
    """
    store = _store(tool_context)
    case_id = core_initialize_new_case(store, appliance, brand, model_number, symptom_text, error_code)
    s = tool_context.state
    s.update({"case_id": case_id, "brand": brand, "model_number": model_number,
              "appliance": appliance, "symptom_text": symptom_text,
              "error_code": error_code or "None", "history_summary": store.recap(case_id)})
    return {"success": True, "case_id": case_id}


def lookup_fixes(appliance: str, brand: str, model_number: str, symptom: str, error_code: str) -> dict:
    """Look up ranked, safety-approved fixes for the symptom/model/code.

    Args:
        appliance: Appliance type.
        brand: Brand name.
        model_number: Model number.
        symptom: Symptom description.
        error_code: Active code or '' if none.
    Returns:
        dict with 'fixes' (ordered list of {instruction, safe, source}).
    """
    ec = error_code if (error_code and error_code.lower() != "none") else None
    return {"fixes": get_fixes(appliance, brand, model_number, symptom, ec)}


def record_step_result(case_id: str, step_id: int, instruction: str, user_result: str,
                       outcome: str, tool_context: ToolContext) -> dict:
    """Record the outcome of a step the user performed. Outcome must be one of
    'resolved', 'not_resolved', 'unsure', 'skipped'. Sets status deterministically.

    Args:
        case_id: The case id.
        step_id: Sequential step number (1-based).
        instruction: The step that was performed.
        user_result: What the user observed/reported.
        outcome: One of resolved/not_resolved/unsure/skipped.
    Returns:
        dict with 'success', 'outcome', 'status'.
    """
    store = _store(tool_context)
    result = core_record_step_result(store, case_id, step_id, instruction, user_result, outcome)
    if result.get("success"):
        tool_context.state["history_summary"] = store.recap(case_id)
    return result


def generate_escalation_draft(case_id: str, tool_context: ToolContext) -> dict:
    """Draft the escalation message + inspection-video guide + service packet (draft only, never
    sends). Use when safe fixes are exhausted or a professional is required.

    Args:
        case_id: The case id.
    Returns:
        dict with 'success' and 'escalation' (recipient, drafted_email, inspection_guide, packet).
    """
    store = _store(tool_context)
    try:
        escalation = esc.escalate_case(case_id, store)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    tool_context.state["history_summary"] = store.recap(case_id)
    return {"success": True, "escalation": escalation}


def generate_inspection_guide(case_id: str, tool_context: ToolContext) -> dict:
    """Produce just the shot-by-shot inspection-video guide for the case.

    Args:
        case_id: The case id.
    Returns:
        dict with 'success' and 'inspection_guide' (list of shots).
    """
    store = _store(tool_context)
    case = store.load_case(case_id)
    if case is None:
        return {"success": False, "error": "Case not found."}
    return {"success": True, "inspection_guide": esc.generate_inspection_guide(case)}


SYSTEM_INSTRUCTION = """You are Appliance Fixer, a safety-first household-appliance repair assistant.
Primary appliance: refrigerator. You work like a real technician: GATHER, then FIX, then ESCALATE.

Current case state:
- Case ID: {case_id}
- Appliance: {appliance}
- Brand: {brand}
- Model: {model_number}
- Symptom: {symptom_text}
- Error code: {error_code}

Prior history recap:
{history_summary}

Rules:
1. GATHER FIRST. Before recommending ANY fix you must know the appliance, brand, model number, and
   the symptom. If a spec-plate photo is provided, call read_spec_plate then verify_model_number.
   Ask the user for anything still missing. Do NOT propose a fix until these facts are gathered.
2. CREATE THE CASE. Once you have appliance + brand + model + symptom, call initialize_new_case and
   tell the user the case id. If the user gives a case id to resume, call reopen_existing_case.
3. FIX LOOP. Call lookup_fixes, then propose exactly ONE fix at a time (safest/easiest first).
   After the user tries it, call record_step_result with outcome resolved/not_resolved/unsure/
   skipped. Keep looping one fix at a time until resolved or no safe fixes remain.
4. ESCALATE. When safe fixes are exhausted (or safety requires it), call generate_escalation_draft
   to prepare the message + inspection-video guide + packet, and tell the user it is ready to share
   (you never send it).
5. SAFETY. NEVER advise gas-line, mains/high-voltage, sealed refrigerant-system, or
   water-on-live-electrics work. If the only remaining fix is dangerous, refuse and escalate.
Be concise and concrete. One step at a time.
"""


def build_agent():
    _ensure_api_env()
    return Agent(
        name="appliance_fixer_agent",
        model=AGENT_MODEL,
        instruction=SYSTEM_INSTRUCTION,
        tools=[
            read_spec_plate, verify_model_number, reopen_existing_case, initialize_new_case,
            lookup_fixes, record_step_result, generate_escalation_draft, generate_inspection_guide,
        ],
        before_agent_callback=initialize_state,
        after_model_callback=after_model_callback,
        before_tool_callback=before_tool_callback,
    )


root_agent = build_agent()
