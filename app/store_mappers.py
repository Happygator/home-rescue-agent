from __future__ import annotations

from app.models import (Diagnosis, Escalation, InspectionShot, IssueDetail, IssueSummary,
                        MediaRef, Packet, Step)
from appliance_fixer.next_step import derive_next_step


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
    return Escalation(recipient=e.get("recipient", ""), drafted_email=e.get("drafted_email", ""),
                      inspection_guide=guide, packet=_map_packet(e.get("packet")),
                      sent=bool(e.get("sent", False)))


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
    return IssueDetail(
        case_id=case["case_id"], title=_title(case), brand=case.get("brand"),
        appliance=case.get("appliance"), model_number=case.get("model_number"),
        status=case["status"], symptom=data.get("symptom_text") or "",
        error_code=data.get("error_code"),
        diagnosis=Diagnosis(hypothesis=diag["hypothesis"], confidence=diag.get("confidence", ""))
        if diag else None,
        steps=steps, next_step=derive_next_step(case), media=media,
        escalation=_map_escalation(data.get("escalation")),
        created_at=case.get("created_at") or "", updated_at=case.get("updated_at") or "",
    )
