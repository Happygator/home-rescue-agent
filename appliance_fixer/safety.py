"""Deterministic SafetyGuard callbacks for the Appliance Fixer agent.

after_model_callback scans the model's response (a before_model callback fires before generation
and cannot see output); before_tool_callback blocks a dangerous tool invocation. On a trip the
case is force-escalated (safety_forced=True) so the dangerous-DIY path still ends with a clean,
service-ready packet. Pure keyword logic -- unit-testable, no model.
"""
from __future__ import annotations

import re

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from appliance_fixer.case_store import CaseStore
from appliance_fixer import escalation as esc

# Dangerous action classes -> trigger phrases (specific enough to mean "do this", not just nouns).
DANGER_KEYWORDS = {
    "gas-system work": (
        "gas line", "gas valve", "gas supply", "burner", "igniter", "pilot light",
        "propane", "natural gas", "gas leak",
    ),
    "mains/high-voltage electrical work": (
        "live wire", "live wires", "mains voltage", "high voltage", "capacitor",
        "bare wire", "120v", "240v", "house wiring", "hot wire", "electrocut", "wire nut",
        "junction box", "while it is plugged in", "while plugged in",
    ),
    "sealed refrigerant-system work": (
        "refrigerant", "freon", "recharge", "sealed system", "compressor terminal",
        "puncture the coil", "puncture the evaporator", "braze",
    ),
    "water on live electrical parts": (
        "water on the wir", "water onto electr", "wet wiring", "spray water near the outlet",
        "water near the live",
    ),
}

# If any of these appear in the SAME sentence as a danger phrase, it is a refusal/caveat,
# not an instruction -- do not trip.
REFUSAL_CUES = (
    "won't", "wont", "will not", "do not", "don't", "dont", "never", "avoid", "not safe",
    "unsafe", "needs a pro", "need a pro", "professional", "a technician", "do not attempt",
    "should not", "shouldn't", "cannot guide", "can't help", "too dangerous", "i refuse",
    "leave that to", "call a", "stay away",
)

REFUSAL_MESSAGE = (
    "Safety stop: {reason} is not safe to do yourself, so I can't walk you through it. "
    "I've prepared a professional escalation with a service-ready inspection packet you can "
    "share with a technician."
)


def scan_for_danger(text):
    """Return (is_dangerous, reason). A danger phrase trips ONLY if its sentence has no
    refusal/negation cue (so the agent's own caveats do not self-trip)."""
    low = (text or "").lower()
    sentences = re.split(r"[.!?\n]+", low)
    for reason, phrases in DANGER_KEYWORDS.items():
        for sent in sentences:
            if any(cue in sent for cue in REFUSAL_CUES):
                continue
            if any(p in sent for p in phrases):
                return True, reason
    return False, None


def _force_escalate(state):
    """Force a safety escalation for the active case, if any. Best-effort; never raises."""
    case_id = state.get("case_id") if state else None
    if not case_id or case_id == "Unknown":
        return
    try:
        store = CaseStore(state.get("db_path", "appliance_fixer.db"))
        esc.escalate_case(case_id, store, safety_forced=True)
    except Exception:
        pass


def _response_text(llm_response):
    parts = []
    content = getattr(llm_response, "content", None)
    if content and getattr(content, "parts", None):
        for p in content.parts:
            if getattr(p, "text", None):
                parts.append(p.text)
    return " ".join(parts)


async def after_model_callback(callback_context, llm_response):
    """Scan the assembled model turn; on danger, force escalation and REPLACE the turn with a
    refusal. Returns a new LlmResponse to override, or None to let the turn through."""
    dangerous, reason = scan_for_danger(_response_text(llm_response))
    if not dangerous:
        return None
    _force_escalate(getattr(callback_context, "state", {}) or {})
    content = types.Content(role="model", parts=[types.Part(text=REFUSAL_MESSAGE.format(reason=reason))])
    return LlmResponse(content=content)


def before_tool_callback(tool, args, tool_context):
    """Block a tool call whose arguments describe dangerous work. Returns a dict (used as the
    tool result, short-circuiting the real call) or None to allow it."""
    blob = " ".join(str(v) for v in (args or {}).values())
    dangerous, reason = scan_for_danger(blob)
    if not dangerous:
        return None
    _force_escalate(getattr(tool_context, "state", {}) or {})
    return {"blocked": True, "reason": reason, "message": REFUSAL_MESSAGE.format(reason=reason)}
