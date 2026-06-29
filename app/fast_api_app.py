from __future__ import annotations

import datetime
import json
import os
import sqlite3
import uuid
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from app.models import (
    CreateIssueRequest,
    CreateIssueResponse,
    DeleteIssueResponse,
    EscalateResponse,
    EscalationStep,
    InspectionShot,
    IssueDetail,
    IssueSummary,
    MediaResponse,
    MessageRequest,
    Packet,
    PlateRequest,
    PlateResponse,
    ResolveResponse,
    UpdateIssueRequest,
)
from app.seed_store import seed_store
from app.store_mappers import case_to_detail, case_to_summary
from app.turns import default_plate, default_turn
from home_rescue import escalation as esc
from home_rescue.appliances import infer_appliance
from home_rescue.case_store import CaseStore
from home_rescue.transitions import transition


MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "media"))


def _new_id() -> str:
    return "case-" + uuid.uuid4().hex[:8]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


async def _aiter_events(source):
    """Iterate a turn_fn result that may be a sync OR async generator of event dicts.
    default_turn is now an async generator (runs on the server's event loop); injected
    test fakes are plain sync generators. This adapter consumes either."""
    if hasattr(source, "__aiter__"):
        async for ev in source:
            yield ev
    else:
        for ev in source:
            yield ev


def create_app(store=None, turn_fn=None, plate_fn=None, seed=False):
    store = store or CaseStore(os.environ.get("APP_DB", "home_rescue.db"))
    if seed:
        seed_store(store)
    turn_fn = turn_fn or default_turn
    plate_fn = plate_fn or default_plate

    app = FastAPI(
        title="HomeRescue API",
        version="0.1.0",
        description="Stub REST and SSE contract for the HomeRescue client.",
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
    def list_issues(
        status: str = "open",
        x_user_id: str | None = Header(default=None),
    ) -> list[IssueSummary]:
        # Scope the list to the calling device when it sends an id; with no
        # header (older clients / tests) fall back to returning every case.
        issues = store.list_cases(user_id=x_user_id)
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
    def create_issue(
        payload: CreateIssueRequest = Body(...),
        x_user_id: str | None = Header(default=None),
    ) -> CreateIssueResponse:
        case_id = _new_id()
        appliance = payload.appliance or infer_appliance(payload.symptom)
        # The device header is the source of truth for ownership; fall back to
        # the body field, then the shared default for header-less callers.
        owner = x_user_id or payload.user_id or "user-default"
        store.new_case(
            case_id,
            owner,
            appliance=appliance,
            brand=payload.brand,
            model_number=payload.model_number,
            status="intake",
            symptom_text=payload.symptom or "",
            error_code=payload.error_code,
        )
        return CreateIssueResponse(case_id=case_id)

    @app.post("/api/issues/{case_id}", response_model=IssueDetail)
    def update_issue(
        case_id: str,
        payload: UpdateIssueRequest = Body(...),
    ) -> IssueDetail:
        case = _load(case_id)
        updates = {}
        if payload.symptom_text is not None:
            updates["symptom_text"] = payload.symptom_text
        if payload.appliance is not None:
            updates["appliance"] = payload.appliance
        if payload.brand is not None:
            updates["brand"] = payload.brand
        if payload.model_number is not None:
            updates["model_number"] = payload.model_number
        if payload.error_code is not None:
            updates["error_code"] = payload.error_code
        if payload.messages:
            existing = list((case.get("data") or {}).get("messages") or [])
            for m in payload.messages:
                existing.append({"role": m.role, "text": m.text, "ts": m.ts or _now_iso(),
                                 "media_ref": getattr(m, "media_ref", None)})
            updates["messages"] = existing
        if updates:
            store.save_case(case_id, **updates)
        return case_to_detail(_load(case_id))

    @app.delete("/api/issues/{case_id}", response_model=DeleteIssueResponse)
    def delete_issue(case_id: str) -> DeleteIssueResponse:
        _load(case_id)  # 404 if the case does not exist
        store.delete_case(case_id)
        return DeleteIssueResponse(case_id=case_id, deleted=True)

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

    @app.get("/api/issues/{case_id}/media/{ref}")
    def get_media(case_id: str, ref: str) -> FileResponse:
        """Serve a previously uploaded media file so the client can render it inline in chat."""
        case = _load(case_id)
        media = (case.get("data") or {}).get("media") or []
        entry = next((m for m in media if m.get("ref") == ref), None)
        if entry is None:
            raise HTTPException(status_code=404, detail="Media not found")
        path = MEDIA_ROOT / case_id / ref
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Media file missing")
        return FileResponse(str(path), media_type=entry.get("mime") or "application/octet-stream")

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
    async def message_issue(
        case_id: str,
        payload: MessageRequest = Body(...),
    ) -> StreamingResponse:
        case = _load(case_id)
        recap = store.recap(case_id)
        # When the user attaches a photo to a chat turn, hand it to the agent so it can read the
        # spec plate / assess the symptom in context (mirrors the auto-kickoff /start path).
        ref = payload.media_ref
        image_path = str(MEDIA_ROOT / case_id / ref) if ref else None

        async def generator():
            parts = []
            kwargs = {"store": store}
            if image_path:
                kwargs["image_path"] = image_path
            async for ev in _aiter_events(turn_fn(case, recap, payload.text, **kwargs)):
                if isinstance(ev, dict) and ev.get("type") == "token" and ev.get("text"):
                    parts.append(ev["text"])
                yield f"data: {json.dumps(ev)}\n\n"
            # Persist the turn so the transcript survives reopen (reopen-every-turn invariant).
            fresh = store.load_case(case_id)
            if fresh is not None:
                messages = list((fresh.get("data") or {}).get("messages") or [])
                messages.append({"role": "user", "text": payload.text, "ts": _now_iso(),
                                 "media_ref": ref})
                # Tokens are word-chunked; collapse any boundary whitespace into single spaces.
                reply = " ".join(" ".join(parts).split())
                if reply:
                    messages.append({"role": "agent", "text": reply, "ts": _now_iso()})
                store.save_case(case_id, messages=messages)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/issues/{case_id}/start")
    async def start_issue(case_id: str) -> StreamingResponse:
        """Auto-kickoff: run ONE agent turn so Gemini produces the first fix for a freshly created
        case, instead of waiting for the user to type. One-shot and idempotent: only an `intake`
        case with a symptom is eligible, and the turn moves it out of `intake` so it never re-fires.
        """
        case = _load(case_id)
        data = case.get("data") or {}
        symptom = data.get("symptom_text") or ""
        eligible = case["status"] == "intake" and bool(symptom.strip())
        # Resolve an image to hand the agent on its first turn so Gemini can judge it in context
        # (spec plate vs symptom photo). Prefer one attached to a user message; else the latest media.
        msgs = data.get("messages") or []
        ref = next((m.get("media_ref") for m in reversed(msgs) if m.get("media_ref")), None)
        if ref is None:
            media = data.get("media") or []
            ref = media[-1]["ref"] if media else None
        image_path = str(MEDIA_ROOT / case_id / ref) if ref else None

        async def generator():
            if not eligible:
                yield f'data: {json.dumps({"type": "done", "status": case["status"]})}\n\n'
                return
            parts = []
            kwargs = {"store": store}
            if image_path:
                kwargs["image_path"] = image_path
            async for ev in _aiter_events(turn_fn(case, store.recap(case_id), symptom, **kwargs)):
                if isinstance(ev, dict) and ev.get("type") == "token" and ev.get("text"):
                    parts.append(ev["text"])
                yield f"data: {json.dumps(ev)}\n\n"
            fresh = store.load_case(case_id)
            if fresh is not None:
                messages = list((fresh.get("data") or {}).get("messages") or [])
                # The symptom is already in the transcript (intake), so append only Gemini's reply.
                reply = " ".join(" ".join(parts).split())
                if reply:
                    messages.append({"role": "agent", "text": reply, "ts": _now_iso()})
                # Leave 'intake' so the kickoff fires exactly once (durable one-shot marker).
                try:
                    new_status = (
                        transition(fresh, "start_diagnosis")
                        if fresh["status"] == "intake"
                        else fresh["status"]
                    )
                except ValueError:
                    new_status = fresh["status"]
                store.save_case(case_id, messages=messages, status=new_status)

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
            escalation_steps=[
                EscalationStep(**{k: s.get(k) for k in ("order", "instruction", "kind", "wait_hours")})
                for s in escalation.get("escalation_steps") or []
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
