"""derive_next_step: the single pure 3-tier 'what to do next' function (no LLM, never persisted)."""
from __future__ import annotations

from home_rescue.grounding import get_fixes

ESCALATED_NEXT = "Pro service required - escalation email + inspection video guide ready to send."


def derive_next_step(case):
    """Three tiers, cheapest first: escalated banner -> a pending step awaiting the user ->
    the first un-tried curated fix. Pure; no model call; result is never stored."""
    status = case.get("status")
    data = case.get("data") or {}
    if status == "escalated":
        return ESCALATED_NEXT
    if status == "resolved":
        return ""
    steps = data.get("steps") or []
    for s in reversed(steps):
        if s.get("outcome") in ("unsure", "pending"):
            instr = (s.get("instruction") or "").strip().rstrip(".")
            return f"You were asked to: {instr} - report back."
    tried = {(s.get("instruction") or "").strip().lower() for s in steps}
    fixes = get_fixes(
        case.get("appliance") or "refrigerator", case.get("brand") or "",
        case.get("model_number") or "", data.get("symptom_text") or "", data.get("error_code"),
    )
    for f in fixes:
        instr = (f.get("instruction") or "").strip()
        if not instr or instr.lower() in tried:
            continue
        # Curated / error-code / manual fixes are trustworthy to surface deterministically.
        # A generic 'fallback' guess is NOT -- defer to the chat, where Gemini gives a real,
        # symptom-specific first fix (auto-kickoff), rather than show a misleading canned step.
        if f.get("source") == "fallback":
            break
        return instr
    if status == "intake":
        return "Capture the model plate to begin diagnosis."
    return "Continue in the chat for your next step."
