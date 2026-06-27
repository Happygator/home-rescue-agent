from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from home_rescue.agent import core_initialize_new_case, core_record_step_result
from home_rescue.case_store import CaseStore
from home_rescue.escalation import escalate_case
from home_rescue.next_step import derive_next_step
from home_rescue.reopen import reopen_and_continue
from home_rescue.safety import after_model_callback, scan_for_danger


APPLIANCE = "refrigerator"
BRAND = "Samsung"
MODEL = "RF28R7201"
SYMPTOM = "fresh food warm, freezer fine"


class FakeCallbackContext:
    def __init__(self, state: dict):
        self.state = state


def _response_text(llm_response: LlmResponse) -> str:
    return " ".join(
        part.text
        for part in llm_response.content.parts
        if getattr(part, "text", None)
    )


def _new_case(store: CaseStore, symptom: str = SYMPTOM) -> str:
    return core_initialize_new_case(
        store,
        APPLIANCE,
        BRAND,
        MODEL,
        symptom,
        error_code=None,
    )


def _record_not_resolved(
    store: CaseStore,
    case_id: str,
    step_id: int,
    instruction: str,
    user_result: str = "No change.",
) -> None:
    result = core_record_step_result(
        store,
        case_id,
        step_id,
        instruction,
        user_result,
        "not_resolved",
    )
    assert result["success"] is True, result
    assert result["status"] == "diagnosing", result


def beat_reopen(db_path: Path) -> None:
    store = CaseStore(db_path)
    case_id = _new_case(store)
    instruction = "Check that refrigerator-side vents are not blocked."
    _record_not_resolved(store, case_id, 1, instruction, "Vents are clear.")

    fresh_store = CaseStore(db_path)
    reopened = reopen_and_continue(case_id, fresh_store)
    recap = reopened["recap"]

    assert MODEL in recap, recap
    assert SYMPTOM in recap, recap
    assert instruction in recap, recap
    assert reopened["message"].startswith("Resuming"), reopened["message"]


def beat_happy_path(db_path: Path) -> None:
    store = CaseStore(db_path)
    case_id = _new_case(store)
    case = store.load_case(case_id)
    next_step = derive_next_step(case)

    assert next_step, "derive_next_step returned an empty step"
    assert "Capture the model plate" not in next_step, next_step

    result = core_record_step_result(
        store,
        case_id,
        1,
        next_step,
        "The refrigerator returned to normal temperature.",
        "resolved",
    )
    assert result["success"] is True, result
    assert result["status"] == "resolved", result

    resolved = store.load_case(case_id)
    assert resolved["status"] == "resolved", resolved
    open_ids = {case["case_id"] for case in store.list_cases(include_resolved=False)}
    assert case_id not in open_ids, open_ids


def beat_escalation_and_safety(db_path: Path) -> None:
    store = CaseStore(db_path)
    case_id = _new_case(store)
    _record_not_resolved(
        store,
        case_id,
        1,
        "Confirm the freezer fan is running.",
        "Fan is running.",
    )
    _record_not_resolved(
        store,
        case_id,
        2,
        "Check that fridge vents are not blocked.",
        "Vents are clear.",
    )

    escalation = escalate_case(case_id, store)
    case = store.load_case(case_id)
    guide = escalation["inspection_guide"]
    packet = escalation["packet"]

    assert case["status"] == "escalated", case
    assert MODEL in escalation["drafted_email"], escalation["drafted_email"]
    assert len(guide) >= 4, guide
    assert packet["steps_tried"] == 2, packet
    assert packet["video_ref"] is None, packet
    assert packet["shots_total"] == len(guide), packet

    video_ref = f"media/{case_id}/inspection.mp4"
    with_video = escalate_case(case_id, store, video_ref=video_ref)
    assert with_video["packet"]["video_ref"] == video_ref, with_video["packet"]

    dangerous, reason = scan_for_danger(
        "Disconnect the gas line and test the live wires while it's plugged in."
    )
    assert dangerous is True, reason
    assert reason, "danger reason was empty"

    refused = scan_for_danger(
        "I won't advise sealed-system work - that needs a pro."
    )
    assert refused == (False, None), refused

    safety_case_id = _new_case(store, symptom="oven smells like gas")
    response = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    text="Disconnect the gas line and clean the gas valve yourself."
                )
            ],
        )
    )
    ctx = FakeCallbackContext({"case_id": safety_case_id, "db_path": str(db_path)})
    replacement = asyncio.run(after_model_callback(ctx, response))

    assert isinstance(replacement, LlmResponse), replacement
    assert "Safety stop" in _response_text(replacement), _response_text(replacement)
    safety_case = store.load_case(safety_case_id)
    safety_escalation = safety_case["data"]["escalation"]
    assert safety_case["status"] == "escalated", safety_case
    assert safety_escalation["safety_forced"] is True, safety_escalation
    assert safety_escalation["packet"], safety_escalation


def rest_e2e() -> None:
    # ignore_cleanup_errors: on Windows the sqlite db file can still be briefly locked at
    # teardown; we don't want that to mask a passing REST run.
    with tempfile.TemporaryDirectory(prefix="home-rescue-rest-", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        os.environ["APP_DB"] = str(tmp_path / "import-side-effect.db")
        os.environ["MEDIA_ROOT"] = str(tmp_path / "media")

        from fastapi.testclient import TestClient
        import app.fast_api_app as fast_api_app

        def canned_turn(case, recap, text, *, store):
            assert recap
            assert text
            yield {"type": "token", "text": "canned-token"}
            yield {"type": "done", "status": case["status"]}

        def canned_plate(case_id, media_ref, store):
            assert case_id
            assert media_ref
            return {"brand": BRAND, "model": MODEL, "error_code": None}

        fast_api_app.MEDIA_ROOT = tmp_path / "media"
        store = CaseStore(tmp_path / "rest.db")
        app = fast_api_app.create_app(
            store=store,
            turn_fn=canned_turn,
            plate_fn=canned_plate,
        )
        client = TestClient(app)

        created = client.post(
            "/api/issues",
            json={"appliance": APPLIANCE, "symptom": SYMPTOM},
        )
        assert created.status_code == 200, created.text
        case_id = created.json()["case_id"]

        listed = client.get("/api/issues")
        assert listed.status_code == 200, listed.text
        created_summary = _find_issue(listed.json(), case_id)
        assert created_summary["next_step"], created_summary

        uploaded = client.post(
            f"/api/issues/{case_id}/media",
            files={"file": ("plate.jpg", b"plate-bytes", "image/jpeg")},
            data={"kind": "plate"},
        )
        assert uploaded.status_code == 200, uploaded.text
        media_ref = uploaded.json()["ref"]

        plate = client.post(
            f"/api/issues/{case_id}/plate",
            json={"media_ref": media_ref},
        )
        assert plate.status_code == 200, plate.text
        assert plate.json()["brand"] == BRAND, plate.text
        assert plate.json()["model"] == MODEL, plate.text

        detail = client.get(f"/api/issues/{case_id}")
        assert detail.status_code == 200, detail.text
        detail_json = detail.json()
        assert len(detail_json["media"]) == 1, detail_json
        assert detail_json["brand"] == BRAND, detail_json
        assert detail_json["model_number"] == MODEL, detail_json

        escalated = client.post(f"/api/issues/{case_id}/escalate")
        assert escalated.status_code == 200, escalated.text
        escalation_json = escalated.json()
        assert escalation_json["drafted_email"], escalation_json
        assert len(escalation_json["inspection_guide"]) >= 4, escalation_json
        assert escalation_json["packet"]["summary"], escalation_json
        assert escalation_json["packet"]["model"] == MODEL, escalation_json
        assert escalation_json["packet"]["shots_total"] == len(
            escalation_json["inspection_guide"]
        ), escalation_json

        resolved = client.post(f"/api/issues/{case_id}/resolve")
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["status"] == "resolved", resolved.text

        open_cases = client.get("/api/issues")
        assert open_cases.status_code == 200, open_cases.text
        open_ids = {issue["case_id"] for issue in open_cases.json()}
        assert case_id not in open_ids, open_ids

        message = client.post(
            f"/api/issues/{case_id}/message",
            json={"text": "What is the status?"},
        )
        assert message.status_code == 200, message.text
        assert '"type": "token"' in message.text, message.text
        assert '"type": "done"' in message.text, message.text


def _find_issue(issues: list[dict], case_id: str) -> dict:
    for issue in issues:
        if issue["case_id"] == case_id:
            return issue
    raise AssertionError(f"case {case_id} was not returned by /api/issues")


def _run(label: str, fn) -> bool:
    try:
        fn()
    except AssertionError as exc:
        print(f"{label} FAILED: {exc}")
        return False
    except Exception as exc:
        print(f"{label} FAILED: {type(exc).__name__}: {exc}")
        return False
    print(f"{label} PASS")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic HomeRescue demo E2E checks."
    )
    parser.add_argument(
        "--db",
        help="SQLite db path for deterministic core beats. Defaults to a temp file.",
    )
    args = parser.parse_args(argv)

    temp_dir = None
    if args.db:
        db_path = Path(args.db)
        db_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="home-rescue-e2e-")
        db_path = Path(temp_dir.name) / "e2e.db"

    checks = [
        ("BEAT 1", lambda: beat_reopen(db_path)),
        ("BEAT 2", lambda: beat_happy_path(db_path)),
        ("BEAT 3", lambda: beat_escalation_and_safety(db_path)),
        ("REST E2E", rest_e2e),
    ]

    try:
        passed = sum(1 for label, fn in checks if _run(label, fn))
        total = len(checks)
        print(f"E2E: {passed}/{total} beats passed")
        return 0 if passed == total else 1
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
