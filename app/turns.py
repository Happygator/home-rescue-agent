from __future__ import annotations

FALLBACK_REPLY = ("I'm having trouble reaching the diagnosis service right now, but your case is "
                  "saved. Please try again in a moment.")


async def default_turn(case, recap, text, *, store, image_path=None):
    """Reopen-every-turn agent turn -> yields SSE event dicts. Runs the ADK agent in a fresh
    session with the recap injected; on ANY error (e.g. quota/network) yields a graceful fallback
    so the stream never 500s. When image_path points at a readable file, it is attached to the
    user turn so the model can evaluate the photo (e.g. a spec plate) alongside the text."""
    import json  # noqa
    try:
        import asyncio
        from google.adk.runners import InMemoryRunner
        from google.genai import types
        from home_rescue.agent import root_agent

        async def _run():
            runner = InMemoryRunner(agent=root_agent, app_name="home_rescue")
            data = case.get("data") or {}
            # Each turn runs in a fresh, stateless ADK session, so the model only sees what we put
            # in state. The persisted transcript (case.data.messages) is the ONLY record of facts the
            # user gave on earlier turns (e.g. brand on one turn, model on the next) before a case is
            # created; without it the agent has amnesia and re-asks in a loop. Replay it into
            # history_summary, which the system prompt renders. The current user turn is persisted
            # only AFTER this runs, so it is not yet in messages -- no duplication with new_message.
            transcript = []
            for m in (data.get("messages") or [])[-20:]:
                txt = (m.get("text") or "").strip()
                if not txt:
                    continue
                speaker = "User" if m.get("role") == "user" else "Assistant"
                transcript.append(f"{speaker}: {txt}")
            history_summary = recap
            if transcript:
                history_summary = recap + "\n\nConversation so far:\n" + "\n".join(transcript)
            state = {
                "db_path": str(store.db_path), "case_id": case["case_id"],
                "brand": case.get("brand") or "Unknown", "model_number": case.get("model_number") or "Unknown",
                "appliance": case.get("appliance") or "refrigerator",
                "symptom_text": data.get("symptom_text") or "None",
                "error_code": data.get("error_code") or "None", "history_summary": history_summary,
            }
            await runner.session_service.create_session(app_name="home_rescue", user_id="user-default",
                                                        session_id=case["case_id"], state=state)
            # An attached photo with no caption still needs an instruction so the model knows to
            # examine it; supply a default prompt when the user sent only an image.
            prompt = text if (text or "").strip() else (
                "Here is a photo of my appliance. Read any spec plate (brand, model, "
                "error code) and assess what you can see.")
            parts = [types.Part(text=prompt)]
            if image_path:
                try:
                    import mimetypes
                    from pathlib import Path as _P
                    p = _P(image_path)
                    if p.is_file():
                        mime = mimetypes.guess_type(str(p))[0] or "image/jpeg"
                        parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime))
                except Exception:
                    pass
            msg = types.Content(role="user", parts=parts)
            out = []
            async for ev in runner.run_async(user_id="user-default", session_id=case["case_id"], new_message=msg):
                if ev.content and ev.content.parts:
                    for p in ev.content.parts:
                        if getattr(p, "text", None):
                            out.append(p.text)
            return "".join(out) or FALLBACK_REPLY

        reply = await _run()
    except Exception as exc:
        # Graceful degradation for the user, but DON'T swallow the cause: log it so a transient
        # rate-limit (429) is distinguishable from a real outage in the server logs.
        import logging
        logging.getLogger("home_rescue").warning(
            "agent turn failed, serving fallback reply: %s: %s", type(exc).__name__, exc
        )
        reply = FALLBACK_REPLY
    # Plate-fact backstop. When a photo was attached but the case still lacks a brand or model
    # number after the turn, the agent failed to persist what it read; read the plate directly and
    # fill ONLY the empty fields so the case summary reflects it. No extra vision call in the happy
    # path -- this runs only when a field is still missing (i.e. the agent did not save it).
    if image_path:
        fresh = store.load_case(case["case_id"]) or {}
        if not fresh.get("brand") or not fresh.get("model_number"):
            try:
                from home_rescue.tools import read_spec_plate, validate_model
                pr = read_spec_plate(image_path)
                b = (pr.get("brand") or "").strip()
                raw = (pr.get("model_number") or "").strip()
                matched = validate_model(raw, b or None)
                m = (matched or raw).strip()
                upd = {}
                if b and not fresh.get("brand"):
                    upd["brand"] = b
                if m and not fresh.get("model_number"):
                    upd["model_number"] = m
                if upd:
                    store.save_case(case["case_id"], **upd)
            except Exception:
                pass
    # No prose-based escalation backstop: the case escalates ONLY when the agent actually calls
    # generate_escalation_draft (which drafts the packet and transitions the status) or when the user
    # taps the manual "Escalate to a pro" button (POST /escalate). This lets the agent mention,
    # suggest, or answer clarifying questions about escalation without a stray "escalat" in its prose
    # force-escalating the case -- so an accidental tap or a "should I escalate?" question no longer
    # commits the user to a service handoff.
    # Chunk the reply into clean word-group token events so the client streams visibly.
    # Each token is a whitespace-free-bounded chunk; the client re-joins tokens with a single
    # space (and the persistence layer normalizes whitespace), so do NOT add inter-chunk spaces
    # here or they double up.
    words = reply.split()
    for i in range(0, len(words), 4):
        yield {"type": "token", "text": " ".join(words[i:i + 4])}
    fresh = store.load_case(case["case_id"])
    yield {"type": "done", "status": (fresh or case)["status"]}


def default_plate(case_id, media_ref, store):
    """Read the spec plate for an uploaded media ref (Gemini). Degrades to all-None on error."""
    try:
        from home_rescue.tools import read_and_cache_plate
        from home_rescue.media_store import get_media_store
        photo = get_media_store().local_path(case_id, media_ref or "")
        if photo is None:
            return {"brand": None, "model": None, "error_code": None}
        result = read_and_cache_plate(case_id, photo, store)
        return {"brand": result.get("brand"), "model": result.get("matched_model") or result.get("model_number"),
                "error_code": result.get("error_code")}
    except Exception:
        return {"brand": None, "model": None, "error_code": None}
