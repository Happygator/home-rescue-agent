"""Escalation: drafted message + inspection-video guide + service-ready packet.

Draft/prepared ONLY -- nothing is auto-sent. The packet references an inspection video by
`video_ref` (a filesystem ref owned by the media layer); bytes are never inlined here.
"""
from __future__ import annotations

from home_rescue.appliances import fridge
from home_rescue.grounding import get_escalation_steps, get_inspection_shots, get_manual
from home_rescue.transitions import transition

# Inspection-video constraints (bound upload size for flaky signal; share-sheet compatible).
MAX_SHOT_SECONDS = 20
VIDEO_MIME = "video/mp4"          # H.264 in MP4 for OS share-sheet compatibility
VIDEO_CODEC = "h264"

_FAULT_KEYWORDS = {
    "sealed_system": ("compressor", "refrigerant", "sealed", "relay", "freon"),
    "airflow_defrost": ("airflow", "coil", "frost", "defrost", "evaporator", "vent", "fan"),
}


def support_contact_for(brand):
    """Return {name,email,phone} for the brand, falling back to DEFAULT_SUPPORT_CONTACT."""
    if not brand:
        return dict(fridge.DEFAULT_SUPPORT_CONTACT)
    return dict(fridge.SUPPORT_CONTACTS.get(brand.upper(), fridge.DEFAULT_SUPPORT_CONTACT))


def fault_class_for(case):
    """Classify the case for inspection-shot selection from its diagnosis/symptom text."""
    data = case.get("data") or {}
    diag = (data.get("diagnosis") or {}).get("hypothesis", "") if data.get("diagnosis") else ""
    text = f"{diag} {data.get('symptom_text', '')}".lower()
    for fault, kws in _FAULT_KEYWORDS.items():
        if any(k in text for k in kws):
            return fault
    return "default"


def manual_ref_for(case):
    """Return a compact manufacturer-manual reference for the packet/email, or None if the model
    has no curated manual on file. Projects the curated MANUALS record (via grounding.get_manual)."""
    manual = get_manual(case.get("appliance"), case.get("brand"), case.get("model_number"))
    if not manual:
        return None
    pages = manual.get("pages") or {}
    return {
        "product_line": manual.get("product_line"),
        "manual_url": manual.get("manual_url"),
        "error_code_url": manual.get("error_code_url"),
        "error_code_page": pages.get("service_error_codes") or pages.get("error_codes"),
        "warranty_note": manual.get("warranty_note"),
    }


def generate_escalation_draft(case, store=None):
    """Build the drafted escalation message. Returns
    {recipient, recipient_name, phone, subject, body, sent:False}. Never sends.

    `store` (optional) is used only to render the recap; if absent, a recap is built inline from
    the case dict.
    """
    brand = case.get("brand") or "Unknown"
    model = case.get("model_number") or "Unknown model"
    appliance = case.get("appliance") or "appliance"
    contact = support_contact_for(case.get("brand"))
    data = case.get("data") or {}
    symptom = data.get("symptom_text") or "(symptom not recorded)"
    steps = data.get("steps") or []

    tried = "\n".join(
        f"  - {s.get('instruction','')}: {s.get('user_result') or s.get('outcome','no result')}"
        for s in steps
    ) or "  - (no troubleshooting steps recorded yet)"
    manual = manual_ref_for(case)
    manual_line = f"Manufacturer manual: {manual['manual_url']}\n\n" if manual and manual.get("manual_url") else ""

    subject = f"Service request: {brand} {appliance} ({model})"
    body = (
        f"Hello {contact['name']} Support,\n\n"
        f"I need to schedule a service visit for my {brand} {appliance} (model {model}).\n\n"
        f"Symptom: {symptom}\n\n"
        f"Steps already tried:\n{tried}\n\n"
        f"These did not resolve the issue. Please advise on next steps or dispatch a technician.\n\n"
        f"{manual_line}"
        f"Thank you."
    )
    return {
        "recipient": contact["email"],
        "recipient_name": contact["name"],
        "phone": contact["phone"],
        "subject": subject,
        "body": body,
        "drafted_email": body,
        "sent": False,
    }


def generate_inspection_guide(case):
    """Produce an ordered shot list from the case + curated inspection_shots.

    Each shot is {shot_no, what_to_film, where, narration, max_seconds}. When an error code is
    present, exactly one shot is specialized to film the display showing that code; otherwise a
    generic display shot is used. The guide is identical whether or not the escalation was
    safety-forced.
    """
    data = case.get("data") or {}
    error_code = data.get("error_code")
    base = get_inspection_shots(fault_class_for(case), case.get("appliance"))
    shots = []
    for i, hint in enumerate(base, start=1):
        what = hint["what_to_film"]
        narr = hint["narration"]
        # Specialize the DISPLAY shot when we have an error code (not a physical "back panel").
        if error_code and ("display" in what.lower() or "display" in hint["where"].lower()):
            what = f"The display showing the {error_code} code"
            narr = f"Show the {error_code} code on the display so the tech can read it."
        shots.append({
            "shot_no": i,
            "what_to_film": what,
            "where": hint["where"],
            "narration": narr,
            "max_seconds": MAX_SHOT_SECONDS,
        })
    return shots


def assemble_packet(case, inspection_guide, video_ref=None):
    """Assemble the service-ready packet that references (not inlines) the inspection video."""
    data = case.get("data") or {}
    brand = case.get("brand") or "Unknown"
    appliance = case.get("appliance") or "appliance"
    symptom = data.get("symptom_text") or "(symptom not recorded)"
    steps = data.get("steps") or []
    diag = (data.get("diagnosis") or {}).get("hypothesis") if data.get("diagnosis") else None
    manual = manual_ref_for(case)
    summary = (
        f"{brand} {appliance}: {symptom}"
        + (f" Working diagnosis: {diag}." if diag else "")
        + f" {len(steps)} step(s) tried, not resolved."
    )
    return {
        "summary": summary,
        "model": case.get("model_number"),
        "error_code": data.get("error_code"),
        "steps_tried": len(steps),
        "video_ref": video_ref,
        "video_mime": VIDEO_MIME,
        "max_shot_seconds": MAX_SHOT_SECONDS,
        "shots_captured": 0,
        "shots_total": len(inspection_guide),
        "warranty_status": (manual["warranty_note"] if manual and manual.get("warranty_note") else "checking..."),
        "manual": manual,
    }


def escalate_case(case_id, store, video_ref=None, safety_forced=False):
    """Full escalation: draft + guide + packet, set status to escalated via transition(), and
    persist case.data.escalation. Returns the escalation dict. Draft/prepared only -- sent=False.

    Raises ValueError (via transition) if the case is already in a terminal state that cannot
    escalate, EXCEPT when already escalated (idempotent: re-assemble without re-transitioning).
    """
    case = store.load_case(case_id)
    if case is None:
        raise ValueError(f"Case '{case_id}' not found.")

    draft = generate_escalation_draft(case, store=store)
    guide = generate_inspection_guide(case)
    packet = assemble_packet(case, guide, video_ref=video_ref)
    steps = get_escalation_steps(case.get("appliance"), case.get("brand"))
    escalation = {
        "recipient": draft["recipient"],
        "drafted_email": draft["drafted_email"],
        "subject": draft["subject"],
        "inspection_guide": guide,
        "escalation_steps": steps,
        "packet": packet,
        "safety_forced": bool(safety_forced),
        "sent": False,
    }

    # Status transition (idempotent when already escalated).
    if case["status"] != "escalated":
        new_status = transition(case, "escalate")
    else:
        new_status = "escalated"
    store.save_case(case_id, status=new_status, escalation=escalation)
    return escalation
