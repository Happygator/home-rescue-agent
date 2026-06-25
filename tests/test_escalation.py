from appliance_fixer.case_store import CaseStore
from appliance_fixer.escalation import (
    MAX_SHOT_SECONDS,
    VIDEO_MIME,
    assemble_packet,
    escalate_case,
    generate_escalation_draft,
    generate_inspection_guide,
)


def _case_with_history(tmp_path, case_id="case-x", *, error_code=None):
    store = CaseStore(tmp_path / f"{case_id}.db")
    store.new_case(
        case_id,
        "user-1",
        appliance="refrigerator",
        brand="Samsung",
        model_number="RF28R7201",
        status="diagnosing",
        symptom_text="Fresh food section is warm while freezer is still cold.",
        error_code=error_code,
    )
    steps = [
        {
            "step_id": "s1",
            "instruction": "Confirm the freezer fan is running",
            "asked_at": "t1",
            "user_result": "Fan is running",
            "outcome": "not_resolved",
        },
        {
            "step_id": "s2",
            "instruction": "Check that fridge vents are not blocked",
            "asked_at": "t2",
            "user_result": "Vents are clear",
            "outcome": "not_resolved",
        },
        {
            "step_id": "s3",
            "instruction": "Inspect freezer back panel for frost",
            "asked_at": "t3",
            "user_result": "Heavy frost on the panel",
            "outcome": "not_resolved",
        },
    ]
    diagnosis = {
        "hypothesis": "Airflow or defrost fault at the evaporator fan",
        "confidence": 0.8,
    }
    assert store.save_case(case_id, steps=steps, diagnosis=diagnosis)
    return store, store.load_case(case_id)


def test_draft_has_model_steps_contact_and_never_sends(tmp_path):
    _, case = _case_with_history(tmp_path)

    draft = generate_escalation_draft(case)

    assert "RF28R7201" in draft["body"]
    assert "Fresh food section is warm while freezer is still cold." in draft["body"]
    assert "Confirm the freezer fan is running" in draft["body"]
    assert draft["recipient"] == "support@samsung.com"
    assert draft["sent"] is False


def test_inspection_guide_with_error_code(tmp_path):
    _, case = _case_with_history(tmp_path, error_code="OF OF")

    guide = generate_inspection_guide(case)
    code_mentions = [
        shot
        for shot in guide
        if "OF OF" in shot["what_to_film"] or "OF OF" in shot["narration"]
    ]

    assert guide
    assert len(code_mentions) == 1


def test_inspection_guide_without_error_code(tmp_path):
    _, case = _case_with_history(tmp_path)

    guide = generate_inspection_guide(case)
    shot_text = " ".join(
        f"{shot['what_to_film']} {shot['where']} {shot['narration']}"
        for shot in guide
    )

    assert guide
    assert "OF OF" not in shot_text
    assert any(
        "display" in shot["what_to_film"].lower()
        or "panel" in shot["what_to_film"].lower()
        or "display" in shot["where"].lower()
        or "panel" in shot["where"].lower()
        for shot in guide
    )
    for shot in guide:
        assert shot["max_seconds"] == MAX_SHOT_SECONDS
        assert {"shot_no", "what_to_film", "where", "narration"}.issubset(shot)


def test_safety_forced_still_produces_packet(tmp_path):
    safety_store, _ = _case_with_history(tmp_path, case_id="case-safety")
    normal_store, _ = _case_with_history(tmp_path, case_id="case-normal")

    safety = escalate_case("case-safety", safety_store, safety_forced=True)
    normal = escalate_case("case-normal", normal_store, safety_forced=False)

    assert safety["safety_forced"] is True
    assert safety["packet"]["video_mime"] == VIDEO_MIME
    assert safety["packet"]["shots_total"] == len(safety["inspection_guide"])
    assert len(safety["inspection_guide"]) == len(normal["inspection_guide"])


def test_packet_shape_and_video_ref(tmp_path):
    _, case = _case_with_history(tmp_path)
    guide = generate_inspection_guide(case)

    packet = assemble_packet(case, guide)
    packet_with_video = assemble_packet(
        case,
        guide,
        video_ref="media/case-x/inspection.mp4",
    )

    assert packet["video_ref"] is None
    assert packet["video_mime"] == "video/mp4"
    assert packet["shots_total"] == len(guide)
    assert packet["steps_tried"] == len(case["data"]["steps"])
    assert packet_with_video["video_ref"] == "media/case-x/inspection.mp4"


def test_escalate_case_sets_status_and_persists(tmp_path):
    store, _ = _case_with_history(tmp_path)

    escalation = escalate_case("case-x", store)
    reloaded = store.load_case("case-x")
    second = escalate_case("case-x", store)
    reloaded_again = store.load_case("case-x")

    assert reloaded["status"] == "escalated"
    assert reloaded["data"]["escalation"]["inspection_guide"]
    assert reloaded["data"]["escalation"]["packet"]
    assert escalation["sent"] is False
    assert second["sent"] is False
    assert reloaded_again["status"] == "escalated"


def test_escalate_case_video_mime_constraint():
    assert VIDEO_MIME == "video/mp4"
    assert isinstance(MAX_SHOT_SECONDS, int)
    assert 0 < MAX_SHOT_SECONDS <= 30
