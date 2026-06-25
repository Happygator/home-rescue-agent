from __future__ import annotations

FALLBACK_REPLY = ("I'm having trouble reaching the diagnosis service right now, but your case is "
                  "saved. Please try again in a moment.")


def default_turn(case, recap, text, *, store):
    """Reopen-every-turn agent turn -> yields SSE event dicts. Runs the ADK agent in a fresh
    session with the recap injected; on ANY error (e.g. quota/network) yields a graceful fallback
    so the stream never 500s."""
    import json  # noqa
    try:
        import asyncio
        from google.adk.runners import InMemoryRunner
        from google.genai import types
        from appliance_fixer.agent import root_agent

        async def _run():
            runner = InMemoryRunner(agent=root_agent, app_name="appliance_fixer")
            data = case.get("data") or {}
            state = {
                "db_path": str(store.db_path), "case_id": case["case_id"],
                "brand": case.get("brand") or "Unknown", "model_number": case.get("model_number") or "Unknown",
                "appliance": case.get("appliance") or "refrigerator",
                "symptom_text": data.get("symptom_text") or "None",
                "error_code": data.get("error_code") or "None", "history_summary": recap,
            }
            await runner.session_service.create_session(app_name="appliance_fixer", user_id="user-default",
                                                        session_id=case["case_id"], state=state)
            msg = types.Content(role="user", parts=[types.Part(text=text)])
            out = []
            async for ev in runner.run_async(user_id="user-default", session_id=case["case_id"], new_message=msg):
                if ev.content and ev.content.parts:
                    for p in ev.content.parts:
                        if getattr(p, "text", None):
                            out.append(p.text)
            return "".join(out) or FALLBACK_REPLY

        reply = asyncio.run(_run())
    except Exception:
        reply = FALLBACK_REPLY
    # chunk the reply into token events so the client streams visibly
    words = reply.split()
    for i in range(0, len(words), 4):
        yield {"type": "token", "text": " ".join(words[i:i + 4])}
    fresh = store.load_case(case["case_id"])
    yield {"type": "done", "status": (fresh or case)["status"]}


def default_plate(case_id, media_ref, store):
    """Read the spec plate for an uploaded media ref (Gemini). Degrades to all-None on error."""
    try:
        from appliance_fixer.tools import read_and_cache_plate
        from pathlib import Path
        photo = Path("media") / case_id / (media_ref or "")
        result = read_and_cache_plate(case_id, photo, store)
        return {"brand": result.get("brand"), "model": result.get("matched_model") or result.get("model_number"),
                "error_code": result.get("error_code")}
    except Exception:
        return {"brand": None, "model": None, "error_code": None}
