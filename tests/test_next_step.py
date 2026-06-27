from __future__ import annotations

from home_rescue.case_store import CaseStore
from home_rescue.grounding import get_fixes
from home_rescue.next_step import ESCALATED_NEXT, derive_next_step


def _store(tmp_path):
    return CaseStore(tmp_path / "cases.db")


def test_escalated_next_step(tmp_path):
    store = _store(tmp_path)
    case = store.new_case("case-1", "user-default", status="escalated")

    assert derive_next_step(case) == ESCALATED_NEXT


def test_resolved_next_step(tmp_path):
    store = _store(tmp_path)
    case = store.new_case("case-1", "user-default", status="resolved")

    assert derive_next_step(case) == ""


def test_unsure_step_asks_user_to_report_back(tmp_path):
    store = _store(tmp_path)
    case = store.new_case("case-1", "user-default", status="awaiting_user")
    instruction = "Check the water-line shutoff valve."
    store.save_case(
        "case-1",
        steps=[{
            "step_id": 1,
            "instruction": instruction,
            "asked_at": None,
            "user_result": None,
            "outcome": "unsure",
        }],
    )

    next_step = derive_next_step(store.load_case("case-1"))

    assert "Check the water-line shutoff valve" in next_step
    assert "report back" in next_step


def test_diagnosing_known_fridge_symptom_returns_curated_fix(tmp_path):
    store = _store(tmp_path)
    case = store.new_case(
        "case-1",
        "user-default",
        appliance="refrigerator",
        status="diagnosing",
        symptom_text="fresh food warm freezer fine",
    )

    next_step = derive_next_step(case)

    assert next_step
    assert next_step != ESCALATED_NEXT


def test_tried_first_curated_fix_returns_different_fix(tmp_path):
    store = _store(tmp_path)
    symptom = "fresh food warm freezer fine"
    case = store.new_case(
        "case-1",
        "user-default",
        appliance="refrigerator",
        status="diagnosing",
        symptom_text=symptom,
    )
    first_fix = get_fixes("refrigerator", "", "", symptom)[0]["instruction"]
    store.save_case(
        case["case_id"],
        steps=[{
            "step_id": 1,
            "instruction": first_fix,
            "asked_at": None,
            "user_result": "no change",
            "outcome": "not_resolved",
        }],
    )

    next_step = derive_next_step(store.load_case(case["case_id"]))

    assert next_step
    assert next_step != first_fix
