from __future__ import annotations

import json
import sqlite3

from home_rescue.agent import core_initialize_new_case, core_record_step_result
from home_rescue.case_store import CaseStore
from home_rescue.escalation import escalate_case
from home_rescue.next_step import derive_next_step
from home_rescue.reopen import reopen_and_continue
from home_rescue.transitions import VALID_STATUSES


def _store(tmp_path):
    return CaseStore(tmp_path / "cases.db")


def test_multi_turn_state_stays_valid(tmp_path):
    store = _store(tmp_path)
    case_id = core_initialize_new_case(
        store,
        "refrigerator",
        "Samsung",
        "RF28R7201",
        "fresh food warm but freezer fine",
    )
    outcomes = ["not_resolved", "unsure"] * 6

    for idx, outcome in enumerate(outcomes, start=1):
        before = store.load_case(case_id)
        before_len = len(before["data"]["steps"])

        result = core_record_step_result(
            store,
            case_id,
            idx,
            f"Integrity check step {idx}.",
            "No change." if outcome == "not_resolved" else "I am not sure.",
            outcome,
        )

        assert result["success"] is True
        case = store.load_case(case_id)
        data = case["data"]
        assert isinstance(data, dict)
        assert {"symptom_text", "media", "steps", "cache"}.issubset(data)
        assert len(data["steps"]) == before_len + 1
        assert case["status"] in VALID_STATUSES

    final_case = store.load_case(case_id)
    assert len(final_case["data"]["steps"]) == 12

    with sqlite3.connect(store.db_path) as conn:
        raw_data = conn.execute(
            "SELECT data FROM cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()[0]
    assert isinstance(json.loads(raw_data), dict)


def test_repeated_reopen_is_stable(tmp_path):
    db_path = tmp_path / "cases.db"
    store = CaseStore(db_path)
    case_id = core_initialize_new_case(
        store,
        "refrigerator",
        "Whirlpool",
        "WRFF3336SZ",
        "fresh food warm but freezer fine",
    )
    core_record_step_result(
        store,
        case_id,
        1,
        "Listen for the evaporator fan.",
        "Fan is running.",
        "not_resolved",
    )
    core_record_step_result(
        store,
        case_id,
        2,
        "Check the evaporator coils for frost.",
        "I am not sure.",
        "unsure",
    )

    recaps = []
    for _ in range(3):
        reopen_store = CaseStore(db_path)
        result = reopen_and_continue(case_id, reopen_store)
        recaps.append(result["recap"])
        reloaded = reopen_store.load_case(case_id)
        assert len(reloaded["data"]["steps"]) == 2

    assert recaps[0] == recaps[1] == recaps[2]


def test_media_failure_mid_escalation_no_crash(tmp_path):
    store = _store(tmp_path)
    case_id = core_initialize_new_case(
        store,
        "refrigerator",
        "Samsung",
        "RF28R7201",
        "fresh food warm but freezer fine",
    )
    core_record_step_result(
        store,
        case_id,
        1,
        "Listen for the evaporator fan.",
        "No airflow.",
        "not_resolved",
    )

    escalation = escalate_case(case_id, store, video_ref=None)
    case = store.load_case(case_id)
    packet = escalation["packet"]

    assert case["status"] == "escalated"
    assert packet["video_ref"] is None
    assert packet["shots_total"] >= 1
    assert packet["shots_captured"] == 0

    updated = escalate_case(case_id, store, video_ref="media/x/inspection.mp4")
    assert updated["packet"]["video_ref"] == "media/x/inspection.mp4"
    assert store.load_case(case_id)["data"]["escalation"]["packet"]["video_ref"] == (
        "media/x/inspection.mp4"
    )


def test_derived_next_step_matches_after_advance(tmp_path):
    store = _store(tmp_path)
    case_id = core_initialize_new_case(
        store,
        "refrigerator",
        "Samsung",
        "RF28R7201",
        "fresh food warm but freezer fine",
    )
    case = store.load_case(case_id)
    first_step = derive_next_step(case)

    assert first_step

    core_record_step_result(
        store,
        case_id,
        1,
        first_step,
        "Still warm.",
        "not_resolved",
    )
    second_step = derive_next_step(store.load_case(case_id))

    assert second_step
    assert second_step != first_step

    core_record_step_result(
        store,
        case_id,
        2,
        second_step,
        "I am not sure what I saw.",
        "unsure",
    )
    report_back = derive_next_step(store.load_case(case_id))
    assert "report back" in report_back
    assert second_step.rstrip(".") in report_back
