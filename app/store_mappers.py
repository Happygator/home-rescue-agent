from __future__ import annotations

from app.models import (ChatTurn, Diagnosis, Escalation, EscalationStep, InspectionShot,
                        IssueDetail, IssueSummary, MediaRef, Packet, Step)
from home_rescue.next_step import derive_next_step


# Phrases in an agent reply that indicate it is RECOMMENDING a professional / escalation. Used only
# to SURFACE an in-chat escalation button (never to auto-commit the case to escalation).
_ESCALATION_SUGGESTION_PHRASES = (
    "professional", "technician", "schedule a service", "schedule service", "service visit",
    "call support", "contact support", "qualified", "escalate",
)
# Specific negations that mean the opposite ("no need for a pro"); when present we do NOT suggest.
_ESCALATION_NEGATIONS = (
    "no need for a pro", "no need for a professional", "don't need a pro",
    "doesn't need a professional", "do not need a professional", "without a professional",
    "not necessary to call", "no need to call",
)


def _suggests_escalation(case):
    """True when the LAST agent message recommends a professional / escalation. Considers only the
    most recent agent turn, so the hint clears once the agent moves on to another fix."""
    messages = (case.get("data") or {}).get("messages") or []
    last_agent = next((m for m in reversed(messages) if m.get("role") == "agent"), None)
    if not last_agent:
        return False
    text = (last_agent.get("text") or "").lower()
    if not text:
        return False
    if any(neg in text for neg in _ESCALATION_NEGATIONS):
        return False
    return any(phrase in text for phrase in _ESCALATION_SUGGESTION_PHRASES)


def _title(case):
    return f"{case.get('brand') or 'New'} \u00b7 {case.get('appliance') or 'Appliance'}"


def _map_packet(p):
    if not p:
        return None
    return Packet(
        summary=p.get("summary", ""), model=p.get("model"), error_code=p.get("error_code"),
        steps_tried=p.get("steps_tried", 0), video_ref=p.get("video_ref"),
        shots_captured=p.get("shots_captured", 0), shots_total=p.get("shots_total", 0),
        warranty_status=p.get("warranty_status"),
    )


def _map_escalation(e):
    if not e:
        return None
    guide = [InspectionShot(shot_no=s.get("shot_no", i + 1), what_to_film=s.get("what_to_film", ""),
                            where=s.get("where", ""), narration=s.get("narration", ""))
             for i, s in enumerate(e.get("inspection_guide") or [])]
    steps = [EscalationStep(order=s.get("order", i + 1), instruction=s.get("instruction", ""),
                            kind=s.get("kind", "action"), wait_hours=s.get("wait_hours"))
             for i, s in enumerate(e.get("escalation_steps") or [])]
    return Escalation(recipient=e.get("recipient", ""), phone=e.get("phone"),
                      drafted_email=e.get("drafted_email", ""),
                      inspection_guide=guide, escalation_steps=steps,
                      packet=_map_packet(e.get("packet")), sent=bool(e.get("sent", False)))


def case_to_summary(case):
    return IssueSummary(
        case_id=case["case_id"], title=_title(case), brand=case.get("brand"),
        appliance=case.get("appliance"), model_number=case.get("model_number"),
        status=case["status"], symptom=(case.get("data") or {}).get("symptom_text") or "",
        next_step=derive_next_step(case), updated_at=case.get("updated_at") or "",
    )


def case_to_detail(case):
    data = case.get("data") or {}
    diag = data.get("diagnosis")
    steps = [Step(step_id=s.get("step_id", i + 1), instruction=s.get("instruction", ""),
                  outcome=s.get("outcome", "pending"), user_result=s.get("user_result"))
             for i, s in enumerate(data.get("steps") or [])]
    media = [MediaRef(kind=m.get("kind", "symptom"), ref=m.get("ref", ""),
                      mime=m.get("mime", "application/octet-stream"), taken_at=m.get("taken_at"))
             for m in data.get("media") or []]
    messages = [ChatTurn(role=m.get("role", "agent"), text=m.get("text", ""), ts=m.get("ts"),
                         media_ref=m.get("media_ref"))
                for m in data.get("messages") or []]
    return IssueDetail(
        case_id=case["case_id"], title=_title(case), brand=case.get("brand"),
        appliance=case.get("appliance"), model_number=case.get("model_number"),
        status=case["status"], symptom=data.get("symptom_text") or "",
        error_code=data.get("error_code"),
        diagnosis=Diagnosis(hypothesis=diag["hypothesis"], confidence=diag.get("confidence", ""))
        if diag else None,
        steps=steps, next_step=derive_next_step(case), media=media, messages=messages,
        escalation=_map_escalation(data.get("escalation")),
        escalation_suggested=(case["status"] not in ("escalated", "resolved")
                              and _suggests_escalation(case)),
        created_at=case.get("created_at") or "", updated_at=case.get("updated_at") or "",
    )
