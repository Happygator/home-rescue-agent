from __future__ import annotations

import sqlite3

from app.seed_data import build_seed
from appliance_fixer.case_store import CaseStore


def _detail_to_case(store: CaseStore, d) -> None:
    store.new_case(d.case_id, "user-default", appliance=d.appliance, brand=d.brand,
                   model_number=d.model_number, status="intake", symptom_text=d.symptom,
                   error_code=d.error_code)
    data_steps = [{"step_id": s.step_id, "instruction": s.instruction, "asked_at": None,
                   "user_result": s.user_result, "outcome": s.outcome} for s in d.steps]
    media = [{"kind": m.kind, "ref": m.ref, "mime": m.mime, "taken_at": m.taken_at} for m in d.media]
    diagnosis = {"hypothesis": d.diagnosis.hypothesis, "confidence": d.diagnosis.confidence} if d.diagnosis else None
    escalation = None
    if d.escalation:
        e = d.escalation
        escalation = {
            "recipient": e.recipient, "drafted_email": e.drafted_email,
            "inspection_guide": [{"shot_no": s.shot_no, "what_to_film": s.what_to_film,
                                  "where": s.where, "narration": s.narration} for s in e.inspection_guide],
            "packet": (e.packet.model_dump() if e.packet else None),
            "sent": e.sent,
        }
    store.save_case(d.case_id, status=d.status, error_code=d.error_code, media=media,
                    steps=data_steps, diagnosis=diagnosis, escalation=escalation)
    # CaseStore stamps updated_at on every write; restore the demo's varied timestamps so the
    # dashboard shows realistic "updated 2h/1d/3d ago" times matching the design mockups.
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("UPDATE cases SET created_at = ?, updated_at = ? WHERE case_id = ?",
                     (d.created_at, d.updated_at, d.case_id))


def seed_store(store: CaseStore) -> None:
    """Populate `store` with the demo cases if it has none."""
    if store.list_cases():
        return
    for d in build_seed().values():
        _detail_to_case(store, d)
