from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.fast_api_app import app, reset_store


SUMMARY_KEYS = {
    "case_id",
    "title",
    "brand",
    "appliance",
    "model_number",
    "status",
    "symptom",
    "next_step",
    "updated_at",
}
DETAIL_KEYS = {
    "case_id",
    "title",
    "brand",
    "appliance",
    "model_number",
    "status",
    "symptom",
    "error_code",
    "diagnosis",
    "steps",
    "next_step",
    "media",
    "messages",
    "escalation",
    "created_at",
    "updated_at",
}


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_store()


def test_list_open_issues_shape() -> None:
    client = TestClient(app)
    response = client.get("/api/issues")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert {item["case_id"] for item in data} == {
        "case-7f3a9c21",
        "case-2b8e1d40",
        "case-9c4f7a02",
    }
    for item in data:
        assert set(item) == SUMMARY_KEYS
        assert item["status"] != "resolved"


def test_list_resolved() -> None:
    client = TestClient(app)
    response = client.get("/api/issues?status=resolved")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    assert all(item["status"] == "resolved" for item in data)


def test_get_detail_shape() -> None:
    client = TestClient(app)
    response = client.get("/api/issues/case-7f3a9c21")

    assert response.status_code == 200
    data = response.json()
    assert set(data) == DETAIL_KEYS
    assert set(data["diagnosis"]) == {"hypothesis", "confidence"}
    assert data["steps"]
    for step in data["steps"]:
        assert set(step) == {"step_id", "instruction", "outcome", "user_result"}
    assert data["next_step"]
    assert isinstance(data["media"], list)
    assert data["escalation"] is None

    missing = client.get("/api/issues/unknown")
    assert missing.status_code == 404


def test_create_issue_then_appears() -> None:
    client = TestClient(app)
    response = client.post("/api/issues", json={})

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"case_id"}

    detail = client.get(f"/api/issues/{data['case_id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "intake"

    open_cases = client.get("/api/issues").json()
    assert data["case_id"] in {item["case_id"] for item in open_cases}


def test_media_upload_returns_ref() -> None:
    client = TestClient(app)
    before = client.get("/api/issues/case-7f3a9c21").json()

    response = client.post(
        "/api/issues/case-7f3a9c21/media",
        files={"file": ("x.jpg", b"data", "image/jpeg")},
        data={"kind": "plate"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {"ref"}
    after = client.get("/api/issues/case-7f3a9c21").json()
    assert len(after["media"]) == len(before["media"]) + 1


def test_plate_returns_fields() -> None:
    client = TestClient(app)
    response = client.post("/api/issues/case-7f3a9c21/plate", json={})

    assert response.status_code == 200
    assert set(response.json()) == {"brand", "model", "error_code"}


def test_message_streams_sse() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/issues/case-7f3a9c21/message",
        json={"text": "hi"},
        headers={},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"type": "token"' in response.text
    assert '"type": "done"' in response.text


def test_escalate_then_resolve() -> None:
    client = TestClient(app)
    response = client.post("/api/issues/case-2b8e1d40/escalate")

    assert response.status_code == 200
    data = response.json()
    assert data["drafted_email"]
    assert len(data["inspection_guide"]) == 4
    assert data["packet"]["steps_tried"] >= 1
    assert data["packet"]["shots_total"] == 4
    assert client.get("/api/issues/case-2b8e1d40").json()["status"] == "escalated"

    resolved = client.post("/api/issues/case-2b8e1d40/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    open_cases = client.get("/api/issues").json()
    assert "case-2b8e1d40" not in {item["case_id"] for item in open_cases}


def test_openapi_snapshot_matches() -> None:
    snapshot = json.loads(Path("app/openapi_snapshot.json").read_text(encoding="utf-8"))
    current = json.loads(json.dumps(app.openapi(), sort_keys=True))

    assert snapshot == current
