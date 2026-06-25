from __future__ import annotations

from fastapi.testclient import TestClient

import app.fast_api_app as fast_api_app
from app.fast_api_app import create_app
from appliance_fixer.case_store import CaseStore
from appliance_fixer.next_step import ESCALATED_NEXT


def make_client(tmp_path):
    calls = []

    def turn_fn(case, recap, text, *, store):
        calls.append({"recap": recap, "text": text, "case_id": case["case_id"]})
        yield {"type": "token", "text": "Try"}
        yield {"type": "token", "text": "this step."}
        yield {"type": "done", "status": case["status"]}

    def plate_fn(case_id, media_ref, store):
        return {"brand": "Samsung", "model": "RF28R7201", "error_code": None}

    store = CaseStore(tmp_path / "api.db")
    app = create_app(store=store, turn_fn=turn_fn, plate_fn=plate_fn)
    return TestClient(app), store, calls


def test_create_then_derived_next_step_in_list(tmp_path):
    client, _store, _calls = make_client(tmp_path)

    response = client.post("/api/issues", json={"appliance": "Refrigerator"})

    assert response.status_code == 200
    case_id = response.json()["case_id"]
    listed = client.get("/api/issues").json()
    created = [item for item in listed if item["case_id"] == case_id][0]
    assert created["status"] == "intake"
    assert created["next_step"]


def test_media_lands_on_filesystem(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    monkeypatch.setattr(fast_api_app, "MEDIA_ROOT", media_root)
    client, _store, _calls = make_client(tmp_path)
    case_id = client.post("/api/issues", json={"appliance": "Refrigerator"}).json()["case_id"]

    response = client.post(
        f"/api/issues/{case_id}/media",
        files={"file": ("p.jpg", b"xx", "image/jpeg")},
        data={"kind": "plate"},
    )

    assert response.status_code == 200
    ref = response.json()["ref"]
    assert (media_root / case_id / ref).exists()
    detail = client.get(f"/api/issues/{case_id}").json()
    assert detail["media"]


def test_escalate_returns_packet_and_resolve_hides_it(tmp_path):
    client, _store, _calls = make_client(tmp_path)

    response = client.post("/api/issues/case-2b8e1d40/escalate")

    assert response.status_code == 200
    data = response.json()
    assert data["drafted_email"]
    assert len(data["inspection_guide"]) >= 1
    assert data["packet"]["steps_tried"] >= 0
    assert data["packet"]["shots_total"] >= 1
    assert client.get("/api/issues/case-2b8e1d40").json()["status"] == "escalated"

    resolved = client.post("/api/issues/case-2b8e1d40/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    open_cases = client.get("/api/issues").json()
    assert "case-2b8e1d40" not in {item["case_id"] for item in open_cases}


def test_sse_streams_and_reopen_every_turn(tmp_path):
    client, _store, calls = make_client(tmp_path)

    response = client.post("/api/issues/case-7f3a9c21/message", json={"text": "hi"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"type": "token"' in response.text
    assert '"type": "done"' in response.text

    second = client.post("/api/issues/case-7f3a9c21/message", json={"text": "again"})
    assert second.status_code == 200
    assert len(calls) == 2
    assert calls[0]["recap"]
    assert calls[1]["recap"]


def test_derived_next_step_is_live(tmp_path):
    client, _store, _calls = make_client(tmp_path)

    detail = client.get("/api/issues/case-7f3a9c21").json()

    assert detail["next_step"]
    assert detail["next_step"] != ESCALATED_NEXT
