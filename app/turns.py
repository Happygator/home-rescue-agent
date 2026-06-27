from __future__ import annotations

FALLBACK_REPLY = ("I'm having trouble reaching the diagnosis service right now, but your case is "
                  "saved. Please try again in a moment.")


def default_turn(case, recap, text, *, store, image_path=None):
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

        reply = asyncio.run(_run())
    except Exception as exc:
        # Graceful degradation for the user, but DON'T swallow the cause: log it so a transient
        # rate-limit (429) is distinguishable from a real outage in the server logs.
        import logging
        logging.getLogger("home_rescue").warning(
            "agent turn failed, serving fallback reply: %s: %s", type(exc).__name__, exc
        )
        reply = FALLBACK_REPLY
    # Escalation backstop. The model sometimes ANNOUNCES escalation in prose without calling
    # generate_escalation_draft, leaving the case in 'diagnosing' with no service packet, so the UI
    # never offers the escalation flow. If the reply says it is escalating but the case did not
    # actually escalate this turn, force it so the words and the case state agree. escalate_case only
    # drafts (never sends), so a rare false trigger is harmless.
    try:
        if "escalat" in (reply or "").lower():
            current = store.load_case(case["case_id"])
            if current is not None and current.get("status") != "escalated":
                from home_rescue import escalation as _esc
                _esc.escalate_case(case["case_id"], store)
    except Exception:
        import logging
        logging.getLogger("home_rescue").warning("escalation backstop failed", exc_info=True)
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
        from pathlib import Path
        photo = Path("media") / case_id / (media_ref or "")
        result = read_and_cache_plate(case_id, photo, store)
        return {"brand": result.get("brand"), "model": result.get("matched_model") or result.get("model_number"),
                "error_code": result.get("error_code")}
    except Exception:
        return {"brand": None, "model": None, "error_code": None}
