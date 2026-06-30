"""HomeRescue agent: gather-then-fix loop (single ADK LlmAgent) + tool wiring.

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

from home_rescue.case_store import make_case_store
from home_rescue.transitions import transition
from home_rescue.reopen import reopen_case
from home_rescue.grounding import get_fixes, get_manual as _lookup_manual, has_error_code_data, _UNSET
from home_rescue.appliances import normalize_appliance
from home_rescue.tools import read_spec_plate as _read_plate, validate_model, load_key
from home_rescue import symptom_router
from home_rescue import escalation as esc
from home_rescue.safety import after_model_callback, before_tool_callback
from home_rescue.mcp_server.toolset import maybe_mcp_toolset, mcp_enabled
from home_rescue.mcp_server.client import call_oem_tool

AGENT_MODEL = os.environ.get("AGENT_MODEL", os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
DEFAULT_DB = "home_rescue.db"
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
    # google.genai logs a warning on EVERY Client() when both GOOGLE_API_KEY and GEMINI_API_KEY are
    # set. We standardize on GOOGLE_API_KEY (ADC-safe, see above), so drop the redundant GEMINI_API_KEY
    # to keep the logs clean. load_key() prefers GOOGLE_API_KEY / GEMINI_KEY.txt, so nothing breaks.
    if os.environ.get("GOOGLE_API_KEY"):
        os.environ.pop("GEMINI_API_KEY", None)
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
    # Dedup guard: a step may be recorded more than once for the same fix - e.g. 'unsure' when the
    # user only asks about it, then 'not_resolved' when they actually try it. Update the existing
    # entry in place (latest outcome wins) instead of appending a duplicate, so 'Steps taken' stays
    # one row per distinct fix. Status still transitions on the new outcome `o` either way.
    norm = (instruction or "").strip().lower()
    existing = next((s for s in steps if (s.get("instruction") or "").strip().lower() == norm), None)
    if existing is not None:
        existing.update({"user_result": user_result, "outcome": o, "asked_at": _now()})
    else:
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
    return make_case_store(tool_context.state.get("db_path", DEFAULT_DB))


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


def update_case_facts(brand: str, model_number: str, error_code: str,
                      tool_context: ToolContext) -> dict:
    """Persist the brand, model number, and/or error code onto the EXISTING case once the user
    provides them (or you read them from a spec plate). Use this instead of initialize_new_case when
    a case already exists. Pass '' for any field you do not have yet.

    Args:
        brand: Brand name, or '' if still unknown.
        model_number: Model number, or '' if still unknown.
        error_code: Error code on the display, or '' if none.
    Returns:
        dict with 'success' and the updated 'brand', 'model_number', 'error_code'.
    """
    s = tool_context.state
    case_id = s.get("case_id")
    if not case_id or case_id == "Unknown":
        return {"success": False, "error": "No existing case to update."}
    store = _store(tool_context)
    if store.load_case(case_id) is None:
        return {"success": False, "error": "Case not found."}
    updates = {}
    b = (brand or "").strip()
    m = (model_number or "").strip()
    ec = (error_code or "").strip()
    if b:
        updates["brand"] = b
        s["brand"] = b
    if m:
        updates["model_number"] = m
        s["model_number"] = m
    if ec and ec.lower() != "none":
        updates["error_code"] = ec
        s["error_code"] = ec
    if updates:
        store.save_case(case_id, **updates)
        s["history_summary"] = store.recap(case_id)
    return {"success": True, "brand": s.get("brand"), "model_number": s.get("model_number"),
            "error_code": s.get("error_code")}


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


async def lookup_fixes(appliance: str, brand: str, model_number: str, symptom: str, error_code: str) -> dict:
    """Look up ranked, safety-approved fixes for the symptom/model/code.

    Args:
        appliance: Appliance type.
        brand: Brand name.
        model_number: Model number.
        symptom: Symptom description.
        error_code: Active code or '' if none.
    Returns:
        dict with 'fixes' (ordered list of {instruction, safe, source, citation}), 'manual'
        (the model's manufacturer-manual reference, or None), and 'via' ('oem_workflow' when the
        steps came from the OEM pre-service workflow, else 'curated'). 'error_code_data_available'
        is True when a known error code would change the recommended fix for this brand/model
        (curated code data exists), so you should ask the user to read any code off the display
        before relying on symptom-only fixes.
    """
    ec = error_code if (error_code and error_code.lower() != "none") else None
    fixes = None
    via = "curated"
    # When the OEM MCP integration is enabled, the authoritative pre-service workflow is the source
    # of the steps, fetched over the MCP transport from the in-process mounted server; fall back to
    # the curated table if it yields nothing or errors (the design section 11 degrade-to-curated rule).
    if mcp_enabled():
        try:
            workflow = await call_oem_tool(
                "get_pre_service_workflow",
                {"model": model_number, "symptom": symptom or "", "error_code": ec or ""},
            )
            steps = workflow.get("steps") or []
            if steps:
                fixes = [{"instruction": s["instruction"], "safe": s["safe"],
                          "source": s["source"], "citation": s.get("citation")} for s in steps]
                via = "oem_workflow"
        except Exception:
            fixes = None
    if fixes is None:
        # Option 2 router: when no error code pins the fixes and the schema router is active, resolve
        # the curated bucket via structured NLU (symptom_router) and pass it as an explicit override.
        # classify_symptom degrades to keyword matching on any extraction failure, so this is safe.
        # The schema router's buckets are REFRIGERATOR-only, so only apply it to refrigerators;
        # other appliances use their module's own keyword matcher (via get_fixes).
        symptom_key = _UNSET
        if (ec is None and normalize_appliance(appliance) == "refrigerator"
                and symptom_router.active_mode() == "schema"):
            symptom_key = symptom_router.classify_symptom(symptom, ec)
        fixes = get_fixes(appliance, brand, model_number, symptom, ec, symptom_key=symptom_key)
    manual = _lookup_manual(appliance, brand, model_number)
    error_code_data = has_error_code_data(appliance, brand, model_number)
    return {"fixes": fixes, "manual": manual, "via": via,
            "error_code_data_available": error_code_data}


def get_manual(appliance: str, brand: str, model_number: str) -> dict:
    """Look up the manufacturer manual reference for this model so you can cite WHERE to find
    information instead of guessing it.

    Use this when the user asks where to find a setting, a part, or the manual itself, or shows an
    error code you cannot confidently explain - then give them the exact link/page it returns.

    Args:
        appliance: Appliance type.
        brand: Brand name.
        model_number: Model number.
    Returns:
        dict with 'found'; when found, 'manual' (product_line, manual_url, error-code page/section,
        warranty_note). 'found' is False when no manual is on file for this model.
    """
    manual = _lookup_manual(appliance, brand, model_number)
    if not manual:
        return {"found": False}
    return {"found": True, "manual": manual}


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


SYSTEM_INSTRUCTION = """You are HomeRescue, a safety-first household-appliance repair assistant.
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
   the symptom. When the user attaches a photo it is already visible to you THIS turn - read it
   directly. Do NOT call read_spec_plate for an attached photo (that tool is only for flows that pass
   a file path; it cannot see an inline image and will fail). First decide what the photo shows:
   - A spec/data plate -> read the BRAND and the MODEL number (the model code, NOT the serial or part
     number) plus any error code, then call verify_model_number and save them with update_case_facts.
   - A symptom (a leak, frost, a damaged part, a code on the display, etc.) -> describe plainly IN
     YOUR REPLY exactly what you observe (what it is and where). Stating it in your reply is what
     records it for later turns; the image itself is NOT kept, so never assume the photo is still
     visible on a future turn.
   If a plate is blurry or unreadable, say so and ask the user to retype the brand/model rather than
   guessing. If a photo is sideways, rotated, or upside down so you cannot read it, say so and ask
   the user to re-send the image upright (rotated so the text reads left-to-right). Ask the user for
   anything still missing. Do NOT propose a fix until these facts are gathered.
2. USE THE EXISTING CASE. If the Case ID above is already set (anything other than 'Unknown'), the
   case ALREADY EXISTS - do NOT call initialize_new_case; use that exact Case ID for
   record_step_result and every other tool. When the user provides the brand, model number, or error
   code for an existing case (or you read them from a spec plate), call update_case_facts to SAVE
   them onto the case before proposing a fix. Never re-ask for a fact the user has already given in
   the conversation. Only when there is no case yet (Case ID is 'Unknown') and you have appliance +
   brand + model + symptom should you call initialize_new_case and tell the user the case id. If the
   user gives a different case id to resume, call reopen_existing_case.
3. FIX LOOP - ONE NEW FIX AT A TIME, RECORDED, NEVER REPEATED. Call lookup_fixes, then propose
   exactly ONE fix at a time, safest/easiest first. lookup_fixes also returns the model's 'manual'
   reference, and each fix has a 'citation'; you may note a step is from the <brand> manual and offer
   the manual link if the user wants detail - but stay brief and do NOT paste links into every step.
   ASK FOR AN ERROR CODE WHEN IT HELPS. If lookup_fixes returns error_code_data_available true and
   the Error code above is still 'None', do NOT propose a generic symptom fix yet: first ask the
   user, in one short sentence, to check the appliance display for any error or fault code, because
   for this brand/model a code points to the exact fix. Ask this only ONCE - if the user gives a
   code, save it with update_case_facts; if they say there is no code (or do not know), proceed with
   the symptom-based fixes below and never re-ask.
   Before proposing a fix, read "Steps taken" in the history recap and the conversation so far, and
   obey these rules:
   (a) RECORD BEFORE RE-PROPOSING. If you proposed a fix on an earlier turn and the user is now
       responding to it - even with a question, a vague reply, a confirmation, or by re-asking "what
       can I do to fix this now" - you MUST call record_step_result for THAT already-proposed fix
       BEFORE you propose anything else. Map the outcome honestly: it worked -> resolved; they tried
       it and it did not help -> not_resolved; they confirmed the condition was already fine (e.g.
       "it's level") or did not act on it -> skipped; anything unclear -> unsure.
   (b) NEVER RECORD THE SAME STEP TWICE. If a fix's instruction already appears in "Steps taken", do
       NOT call record_step_result for it again - it is already handled.
   (c) NEVER RE-PROPOSE A HANDLED FIX. Never propose a fix whose instruction already appears in
       "Steps taken". After recording, advance to the NEXT, different un-tried fix from lookup_fixes.
       If every safe fix is already in "Steps taken", stop looping and escalate per rule 5 instead of
       repeating a fix.
   Keep looping one NEW fix at a time until resolved or no safe fixes remain.
4. CITE THE MANUAL, DON'T GUESS. If the user asks where to find a setting, a part, or the manual, or
   shows an error code you cannot confidently explain, call get_manual (or use the 'manual' from
   lookup_fixes) and give them the exact reference it returns (the manual link, and the error-code
   page or support page). Never invent a code's meaning or a manual page number.
5. ESCALATE. When safe fixes are exhausted (or safety requires it), you MUST call
   generate_escalation_draft FIRST, and only AFTER it returns may you tell the user anything about
   escalating. NEVER say you are escalating, will escalate, or are setting up service unless you
   called generate_escalation_draft on THIS turn - announcing it without the tool call leaves the
   case stuck and gives the user no way to proceed. Once it returns, reply in 2-3 sentences that
   (a) explain WHY you are escalating - name the specific safe fixes already tried and that they did
   not resolve it, or state the safety reason - and (b) offer to set up professional service from
   here. Do NOT paste
   the drafted email, do NOT say the draft is shown in the chat, and do NOT claim you have contacted
   anyone; the user reviews and sends everything from the service packet screen. You never send
   anything yourself.
6. SAFETY. NEVER advise gas-line, mains/high-voltage, sealed refrigerant-system, or
   water-on-live-electrics work. If the only remaining fix is dangerous, refuse and escalate.

BREVITY. Keep every reply short - aim for 2-3 sentences. Get to the point: skip greetings,
restating what the user just told you, and filler preamble. NEVER narrate your own actions or tool
use - do not say things like "I have updated the case", "I will look up fixes", "let me check", or
"now that I have the information"; just use your tools silently and give the user the result (a brief
plate confirmation if you read one, then the single next fix). Ask only for the information you
still need, in one or two plain sentences. Do not use bold or other markdown emphasis, bullet
lists, or step-by-step explanations of where to find things unless the user asks. One step at a
time, stated plainly.
"""


def build_agent():
    _ensure_api_env()
    tools = [
        read_spec_plate, verify_model_number, update_case_facts, reopen_existing_case, initialize_new_case,
        lookup_fixes, get_manual, record_step_result, generate_escalation_draft, generate_inspection_guide,
    ]
    # Gated mock OEM MCP server (off by default); falls back to the in-process curated tools.
    mcp_toolset = maybe_mcp_toolset()
    if mcp_toolset is not None:
        tools.append(mcp_toolset)
    return Agent(
        name="home_rescue_agent",
        model=AGENT_MODEL,
        instruction=SYSTEM_INSTRUCTION,
        tools=tools,
        before_agent_callback=initialize_state,
        after_model_callback=after_model_callback,
        before_tool_callback=before_tool_callback,
    )


root_agent = build_agent()
