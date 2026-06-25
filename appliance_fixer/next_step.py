"""derive_next_step: the single pure 3-tier 'what to do next' function (no LLM, never persisted)."""
from __future__ import annotations

from appliance_fixer.grounding import get_fixes

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
        if instr and instr.lower() not in tried:
            return instr
    if status == "intake":
        return "Capture the model plate to begin diagnosis."
    return "Add more detail so we can suggest the next step."
