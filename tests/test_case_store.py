import pytest

from home_rescue.case_store import CaseStore
from home_rescue.transitions import transition


def test_json_round_trip(tmp_path):
    store = CaseStore(tmp_path / "t.db")
    store.new_case(
        "c1",
        "u1",
        appliance="washer",
        symptom_text="Won't drain",
        error_code="E20",
    )
    media = [
        {"kind": "photo", "ref": "a.jpg", "mime": "image/jpeg", "taken_at": "t1"},
        {"kind": "photo", "ref": "b.jpg", "mime": "image/jpeg", "taken_at": "t2"},
        {"kind": "video", "ref": "c.mp4", "mime": "video/mp4", "taken_at": "t3"},
    ]
    steps = [
        {
            "step_id": "s1",
            "instruction": "Check the drain hose",
            "asked_at": "t1",
            "user_result": "Clear",
            "outcome": "not_resolved",
        },
        {
            "step_id": "s2",
            "instruction": "Clean the filter",
            "asked_at": "t2",
            "user_result": "Found lint",
            "outcome": "not_resolved",
        },
        {
            "step_id": "s3",
            "instruction": "Run spin cycle",
            "asked_at": "t3",
            "user_result": "Drained",
            "outcome": "resolved",
        },
    ]
    diagnosis = {"hypothesis": "Clogged pump filter", "confidence": 0.9}

    assert store.save_case(
        "c1",
        error_code="E21",
        media=media,
        steps=steps,
        diagnosis=diagnosis,
    )

    case = store.load_case("c1")
    assert case["data"]["media"] == media
    assert case["data"]["steps"] == steps
    assert case["data"]["diagnosis"] == diagnosis
    assert case["data"]["error_code"] == "E21"
    assert "media" in case["data"]
    assert "photos" not in case["data"]
    assert "next_step" not in case["data"]


def test_unbounded_arrays(tmp_path):
    store = CaseStore(tmp_path / "t.db")
    store.new_case("c1", "u1")
    steps = [
        {
            "step_id": f"s{idx}",
            "instruction": f"Instruction {idx}",
            "asked_at": f"t{idx}",
            "user_result": f"Result {idx}",
            "outcome": "unknown",
        }
        for idx in range(60)
    ]
    media = [
        {
            "kind": "photo",
            "ref": f"{idx}.jpg",
            "mime": "image/jpeg",
            "taken_at": f"t{idx}",
        }
        for idx in range(60)
    ]

    assert store.save_case("c1", steps=steps, media=media)
    case = store.load_case("c1")
    assert len(case["data"]["steps"]) == 60
    assert len(case["data"]["media"]) == 60
    assert case["data"]["steps"][-1] == steps[-1]
    assert case["data"]["media"][-1] == media[-1]


def test_recap_renders(tmp_path):
    store = CaseStore(tmp_path / "t.db")
    store.new_case(
        "c1",
        "u1",
        appliance="dryer",
        brand="Acme",
        model_number="DRY-200",
        symptom_text="No heat",
    )
    steps = [
        {
            "step_id": "s1",
            "instruction": "Check lint screen",
            "asked_at": "t1",
            "user_result": "Clean",
            "outcome": "resolved",
        },
        {
            "step_id": "s2",
            "instruction": "Inspect vent",
            "asked_at": "t2",
            "user_result": "",
            "outcome": "not_resolved",
        },
    ]
    store.save_case("c1", steps=steps)

    recap = store.recap("c1")
    assert "DRY-200" in recap
    assert "No heat" in recap
    assert "Check lint screen" in recap
    assert "Inspect vent" in recap
    assert "RESOLVED" in recap
    assert "NOT_RESOLVED" in recap


def test_load_missing_returns_none(tmp_path):
    store = CaseStore(tmp_path / "t.db")
    assert store.load_case("nope") is None


def test_list_cases_orders_and_filters(tmp_path):
    store = CaseStore(tmp_path / "t.db")
    store.new_case("c1", "u1")
    store.new_case("c2", "u1")
    store.new_case("c3", "u2")
    resolved = transition("intake", "start_diagnosis")
    resolved = transition(resolved, "resolve")
    assert store.save_case("c2", status=resolved)

    unresolved = store.list_cases(include_resolved=False)
    assert {case["case_id"] for case in unresolved} == {"c1", "c3"}

    all_cases = store.list_cases()
    assert len(all_cases) == 3
    updated_at_values = [case["updated_at"] for case in all_cases]
    assert updated_at_values == sorted(updated_at_values, reverse=True)

    user_cases = store.list_cases(user_id="u1")
    assert {case["case_id"] for case in user_cases} == {"c1", "c2"}


def test_transition_table():
    assert transition("intake", "start_diagnosis") == "diagnosing"
    assert transition("diagnosing", "await_user") == "awaiting_user"
    assert transition("awaiting_user", "user_responded") == "diagnosing"
    assert transition("diagnosing", "resolve") == "resolved"
    assert transition("diagnosing", "escalate") == "escalated"
    assert transition({"status": "awaiting_user"}, "escalate") == "escalated"

    with pytest.raises(ValueError):
        transition("resolved", "start_diagnosis")
    with pytest.raises(ValueError):
        transition("escalated", "user_responded")
    with pytest.raises(ValueError):
        transition("intake", "resolve")
    with pytest.raises(ValueError):
        transition("diagnosing", "bogus_event")
    with pytest.raises(ValueError):
        transition("not_a_status", "escalate")
