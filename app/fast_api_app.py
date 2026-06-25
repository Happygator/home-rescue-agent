from __future__ import annotations

import datetime
import json
import os
import sqlite3
import uuid
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.models import (
    CreateIssueRequest,
    CreateIssueResponse,
    EscalateResponse,
    InspectionShot,
    IssueDetail,
    IssueSummary,
    MediaResponse,
    MessageRequest,
    Packet,
    PlateRequest,
    PlateResponse,
    ResolveResponse,
)
from app.seed_store import seed_store
from app.store_mappers import case_to_detail, case_to_summary
from app.turns import default_plate, default_turn
from appliance_fixer import escalation as esc
from appliance_fixer.case_store import CaseStore
from appliance_fixer.transitions import transition


MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "media"))


def _new_id() -> str:
    return "case-" + uuid.uuid4().hex[:8]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def create_app(store=None, turn_fn=None, plate_fn=None):
    store = store or CaseStore(os.environ.get("APP_DB", "appliance_fixer.db"))
    seed_store(store)
    turn_fn = turn_fn or default_turn
    plate_fn = plate_fn or default_plate

    app = FastAPI(
        title="Appliance Fixer API",
        version="0.1.0",
        description="Stub REST and SSE contract for the Appliance Fixer client.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.store = store
    app.state.turn_fn = turn_fn
    app.state.plate_fn = plate_fn

    def _load(case_id):
        case = store.load_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Issue not found")
        return case

    @app.get("/api/issues", response_model=list[IssueSummary])
    def list_issues(status: str = "open") -> list[IssueSummary]:
        issues = store.list_cases()
        if status == "open":
            issues = [issue for issue in issues if issue["status"] != "resolved"]
        elif status == "resolved":
            issues = [issue for issue in issues if issue["status"] == "resolved"]
        issues = sorted(issues, key=lambda issue: issue.get("updated_at") or "", reverse=True)
        return [case_to_summary(issue) for issue in issues]

    @app.get("/api/issues/{case_id}", response_model=IssueDetail)
    def get_issue(case_id: str) -> IssueDetail:
        return case_to_detail(_load(case_id))

    @app.post("/api/issues", response_model=CreateIssueResponse)
    def create_issue(payload: CreateIssueRequest = Body(...)) -> CreateIssueResponse:
        case_id = _new_id()
        store.new_case(
            case_id,
            payload.user_id or "user-default",
            appliance=payload.appliance,
            brand=payload.brand,
            model_number=payload.model_number,
            status="intake",
            symptom_text=payload.symptom or "",
            error_code=payload.error_code,
        )
        return CreateIssueResponse(case_id=case_id)

    @app.post("/api/issues/{case_id}/media", response_model=MediaResponse)
    def upload_media(
        case_id: str,
        file: UploadFile = File(...),
        kind: str = Form("symptom"),
    ) -> MediaResponse:
        case = _load(case_id)
        content = file.file.read()
        suffix = Path(file.filename or "").suffix or ".bin"
        media_kind = kind if kind in {"plate", "symptom", "inspection_video"} else "symptom"
        ref = f"{kind}-{uuid.uuid4().hex[:8]}{suffix}"
        target_dir = MEDIA_ROOT / case_id
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / ref).write_bytes(content)
        data = case.get("data") or {}
        media = list(data.get("media") or [])
        media.append({
            "kind": media_kind,
            "ref": ref,
            "mime": file.content_type or "application/octet-stream",
            "taken_at": _now_iso(),
        })
        store.save_case(case_id, media=media)
        return MediaResponse(ref=ref)

    @app.post("/api/issues/{case_id}/plate", response_model=PlateResponse)
    def read_plate(
        case_id: str,
        payload: PlateRequest = Body(...),
    ) -> PlateResponse:
        case = _load(case_id)
        result = plate_fn(case_id, payload.media_ref, store)
        brand = result.get("brand")
        model = result.get("model")
        error_code = result.get("error_code")
        updates = {}
        if brand and not case.get("brand"):
            updates["brand"] = brand
        if model and not case.get("model_number"):
            updates["model_number"] = model
        if updates:
            store.save_case(case_id, **updates)
        return PlateResponse(brand=brand, model=model, error_code=error_code)

    @app.post("/api/issues/{case_id}/message")
    def message_issue(
        case_id: str,
        payload: MessageRequest = Body(...),
    ) -> StreamingResponse:
        case = _load(case_id)
        recap = store.recap(case_id)

        def generator():
            for ev in turn_fn(case, recap, payload.text, store=store):
                yield f"data: {json.dumps(ev)}\n\n"

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/issues/{case_id}/escalate", response_model=EscalateResponse)
    def escalate_issue(case_id: str) -> EscalateResponse:
        _load(case_id)
        escalation = esc.escalate_case(case_id, store)
        return EscalateResponse(
            drafted_email=escalation["drafted_email"],
            inspection_guide=[
                InspectionShot(**{k: s[k] for k in ("shot_no", "what_to_film", "where", "narration")})
                for s in escalation["inspection_guide"]
            ],
            packet=Packet(**{k: escalation["packet"].get(k) for k in (
                "summary", "model", "error_code", "steps_tried", "video_ref",
                "shots_captured", "shots_total", "warranty_status",
            )}),
        )

    @app.post("/api/issues/{case_id}/resolve", response_model=ResolveResponse)
    def resolve_issue(case_id: str) -> ResolveResponse:
        case = _load(case_id)
        try:
            new = transition(case, "resolve")
        except ValueError:
            new = "resolved"
        store.save_case(case_id, status=new)
        return ResolveResponse(case_id=case_id, status=new)

    return app


app = create_app()


def reset_store() -> None:
    store = app.state.store
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("DELETE FROM cases")
    seed_store(store)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
