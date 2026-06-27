from __future__ import annotations

from fastapi.testclient import TestClient

import app.fast_api_app as fast_api_app
from app.fast_api_app import create_app
from home_rescue.case_store import CaseStore
from home_rescue.next_step import ESCALATED_NEXT


def make_client(tmp_path):
    calls = []

    def turn_fn(case, recap, text, *, store, image_path=None):
        calls.append({"recap": recap, "text": text, "case_id": case["case_id"],
                      "image_path": image_path})
        yield {"type": "token", "text": "Try"}
        yield {"type": "token", "text": "this step."}
        yield {"type": "done", "status": case["status"]}

    def plate_fn(case_id, media_ref, store):
        return {"brand": "Samsung", "model": "RF28R7201", "error_code": None}

    store = CaseStore(tmp_path / "api.db")
    app = create_app(store=store, turn_fn=turn_fn, plate_fn=plate_fn, seed=True)
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


def test_update_persists_symptom_and_appends_transcript(tmp_path):
    client, _store, _calls = make_client(tmp_path)
    case_id = client.post("/api/issues", json={"appliance": "Refrigerator"}).json()["case_id"]

    updated = client.post(
        f"/api/issues/{case_id}",
        json={
            "symptom_text": "fridge is 50F",
            "model_number": "RF28R7201",
            "messages": [
                {"role": "agent", "text": "Hi! I'm your HomeRescue assistant."},
                {"role": "user", "text": "fridge is 50F"},
            ],
        },
    )

    assert updated.status_code == 200
    body = updated.json()
    # The symptom the user entered is no longer dropped.
    assert body["symptom"] == "fridge is 50F"
    assert body["model_number"] == "RF28R7201"
    assert [m["text"] for m in body["messages"]] == [
        "Hi! I'm your HomeRescue assistant.",
        "fridge is 50F",
    ]
    # And it is durable: a fresh GET still has it.
    reloaded = client.get(f"/api/issues/{case_id}").json()
    assert reloaded["symptom"] == "fridge is 50F"
    assert len(reloaded["messages"]) == 2


def test_message_turn_is_appended_to_transcript(tmp_path):
    client, _store, _calls = make_client(tmp_path)
    case_id = client.post("/api/issues", json={"appliance": "Refrigerator"}).json()["case_id"]

    client.post(f"/api/issues/{case_id}/message", json={"text": "the freezer is fine"})

    detail = client.get(f"/api/issues/{case_id}").json()
    roles = [m["role"] for m in detail["messages"]]
    texts = [m["text"] for m in detail["messages"]]
    # Both sides of the turn persist (user text + reconstructed agent reply).
    assert roles == ["user", "agent"]
    assert texts[0] == "the freezer is fine"
    assert texts[1] == "Try this step."

    # A second turn keeps prior history rather than replacing it.
    client.post(f"/api/issues/{case_id}/message", json={"text": "still warm"})
    detail2 = client.get(f"/api/issues/{case_id}").json()
    assert len(detail2["messages"]) == 4


def test_media_get_serves_uploaded_file(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    monkeypatch.setattr(fast_api_app, "MEDIA_ROOT", media_root)
    client, _store, _calls = make_client(tmp_path)
    case_id = client.post("/api/issues", json={"appliance": "Refrigerator"}).json()["case_id"]
    ref = client.post(
        f"/api/issues/{case_id}/media",
        files={"file": ("p.jpg", b"imgbytes", "image/jpeg")},
        data={"kind": "symptom"},
    ).json()["ref"]

    got = client.get(f"/api/issues/{case_id}/media/{ref}")

    assert got.status_code == 200
    assert got.content == b"imgbytes"
    assert got.headers["content-type"].startswith("image/jpeg")

    # Unknown ref (and unknown case) 404 rather than leaking the filesystem.
    assert client.get(f"/api/issues/{case_id}/media/nope.jpg").status_code == 404
    assert client.get(f"/api/issues/unknown/media/{ref}").status_code == 404


def test_start_passes_attached_image_to_agent(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    monkeypatch.setattr(fast_api_app, "MEDIA_ROOT", media_root)
    client, _store, calls = make_client(tmp_path)
    case_id = client.post("/api/issues", json={"appliance": "Refrigerator"}).json()["case_id"]
    ref = client.post(
        f"/api/issues/{case_id}/media",
        files={"file": ("plate.jpg", b"xx", "image/jpeg")},
        data={"kind": "symptom"},
    ).json()["ref"]
    client.post(
        f"/api/issues/{case_id}",
        json={
            "symptom_text": "fridge is 50F",
            "messages": [{"role": "user", "text": "fridge is 50F", "media_ref": ref}],
        },
    )

    response = client.post(f"/api/issues/{case_id}/start")

    assert response.status_code == 200
    assert len(calls) == 1
    # The agent received the attached image so it can evaluate the photo in context.
    assert calls[0]["image_path"] is not None
    assert calls[0]["image_path"].endswith(ref)


def test_message_passes_attached_image_to_agent(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    monkeypatch.setattr(fast_api_app, "MEDIA_ROOT", media_root)
    client, store, calls = make_client(tmp_path)
    case_id = client.post("/api/issues", json={"appliance": "Refrigerator"}).json()["case_id"]
    ref = client.post(
        f"/api/issues/{case_id}/media",
        files={"file": ("plate.jpg", b"xx", "image/jpeg")},
        data={"kind": "symptom"},
    ).json()["ref"]

    response = client.post(f"/api/issues/{case_id}/message", json={"text": "", "media_ref": ref})

    assert response.status_code == 200
    assert len(calls) == 1
    # The chat turn forwarded the attached photo so the agent can read/assess it.
    assert calls[0]["image_path"] is not None
    assert calls[0]["image_path"].endswith(ref)
    # The user turn is persisted with its media_ref so the transcript renders the photo on reopen.
    fresh = store.load_case(case_id)
    user_turns = [m for m in (fresh.get("data") or {}).get("messages") or [] if m.get("role") == "user"]
    assert any(m.get("media_ref") == ref for m in user_turns)


def test_start_kicks_off_first_fix_once(tmp_path):
    client, _store, calls = make_client(tmp_path)
    case_id = client.post("/api/issues", json={"appliance": "Refrigerator"}).json()["case_id"]
    client.post(
        f"/api/issues/{case_id}",
        json={"symptom_text": "fridge is 50F", "messages": [{"role": "user", "text": "fridge is 50F"}]},
    )

    response = client.post(f"/api/issues/{case_id}/start")

    assert response.status_code == 200
    assert '"type": "token"' in response.text
    # The agent was invoked exactly once and its reply was appended after the symptom.
    assert len(calls) == 1
    detail = client.get(f"/api/issues/{case_id}").json()
    assert detail["status"] != "intake"  # diagnosis has started (one-shot marker)
    assert [m["role"] for m in detail["messages"]] == ["user", "agent"]
    assert detail["messages"][-1]["text"] == "Try this step."

    # Idempotent: a second /start does NOT invoke the agent again or duplicate the reply.
    client.post(f"/api/issues/{case_id}/start")
    assert len(calls) == 1
    detail2 = client.get(f"/api/issues/{case_id}").json()
    assert len([m for m in detail2["messages"] if m["role"] == "agent"]) == 1


def test_update_can_edit_appliance_and_brand(tmp_path):
    client, _store, _calls = make_client(tmp_path)
    case_id = client.post(
        "/api/issues", json={"appliance": "Refrigerator", "brand": "Samsung"}
    ).json()["case_id"]

    updated = client.post(
        f"/api/issues/{case_id}",
        json={"appliance": "Freezer", "brand": "LG", "model_number": "X1"},
    )

    assert updated.status_code == 200
    body = updated.json()
    assert body["appliance"] == "Freezer"
    assert body["brand"] == "LG"
    assert body["model_number"] == "X1"


def test_delete_removes_case(tmp_path):
    client, _store, _calls = make_client(tmp_path)
    case_id = client.post("/api/issues", json={"appliance": "Refrigerator"}).json()["case_id"]

    response = client.delete(f"/api/issues/{case_id}")

    assert response.status_code == 200
    assert response.json() == {"case_id": case_id, "deleted": True}
    # The case is gone: a fresh GET 404s and it no longer appears in the list.
    assert client.get(f"/api/issues/{case_id}").status_code == 404
    assert case_id not in {item["case_id"] for item in client.get("/api/issues").json()}


def test_delete_unknown_case_404s(tmp_path):
    client, _store, _calls = make_client(tmp_path)

    assert client.delete("/api/issues/case-does-not-exist").status_code == 404


def test_start_is_noop_without_symptom(tmp_path):
    client, _store, calls = make_client(tmp_path)
    case_id = client.post("/api/issues", json={"appliance": "Refrigerator"}).json()["case_id"]

    response = client.post(f"/api/issues/{case_id}/start")

    assert response.status_code == 200
    assert len(calls) == 0  # no symptom -> no agent call
    assert client.get(f"/api/issues/{case_id}").json()["status"] == "intake"
