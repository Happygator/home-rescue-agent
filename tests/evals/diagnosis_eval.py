"""Runnable first-fix diagnosis eval.

The scorer is a simple keyword-overlap heuristic stand-in for the LLM judge used
in the spike. It awards 2 when a key noun from a reference first fix appears in
the reply, 1 when the reply names a plausible secondary appliance area, and 0
otherwise.
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import math
import os
import re
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "spikes" / "datasets" / "diagnosis_symptoms.jsonl"

KEY_TERMS = (
    "evaporator",
    "condenser",
    "coil",
    "coils",
    "drain",
    "filter",
    "relay",
    "gasket",
    "vent",
    "vents",
    "defrost",
    "fill tube",
    "inlet valve",
    "fan",
    "compressor",
    "water supply",
    "shutoff",
    "heater",
    "thermostat",
    "icemaker",
)


def _is_quota_error(exc):
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(
        marker in text
        for marker in (
            "429",
            "quota",
            "resource_exhausted",
            "resource exhausted",
            "rate limit",
            "rate_limit",
        )
    )


def _load_json_mapping(path):
    if path is None:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_symptoms():
    rows = []
    for line in DATA_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _reference_terms(ground_truth_first_fixes):
    terms = set()
    refs = " ".join(ground_truth_first_fixes or []).lower()
    for term in KEY_TERMS:
        if term in refs:
            terms.add(term)
    return terms


def score_first_fix(agent_reply, ground_truth_first_fixes):
    reply = (agent_reply or "").lower()
    reference_terms = _reference_terms(ground_truth_first_fixes)
    if any(term in reply for term in reference_terms):
        return 2
    if any(term in reply for term in KEY_TERMS):
        return 1
    return 0


_FOLLOWUPS = (
    "Yes, the brand, model, and symptom are exactly as I stated and are confirmed. "
    "Give the single safest first troubleshooting step now.",
    "Please stop asking questions. State the single most likely first fix and the one step to check it.",
)

JUDGE_PROMPT = (
    "You are scoring an appliance-repair assistant's FIRST troubleshooting step against a list "
    "of known-likely-correct first fixes for the same symptom. Score 2 if the reply names or "
    "clearly targets one of the reference fixes; 1 if it targets a plausible related component "
    "or area but not a listed fix; 0 if it is off-target, empty, or merely asks a question. "
    "Respond with ONLY compact JSON, no markdown: "
    '{"score": <0|1|2>, "reason": <short string>}.'
)


def _extract_json(text):
    """Pull the first {...} JSON object out of a model reply; return {} on failure."""
    if not text:
        return {}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except Exception:
        return {}


def _judge_client():
    from google import genai

    from home_rescue.tools import load_key

    return genai.Client(api_key=load_key())


def judge_first_fix(reply, ground_truth_first_fixes, *, client=None, model=None):
    """LLM-judge a first-fix reply as 0/1/2 against the reference fixes."""
    reply = (reply or "").strip()
    if not reply:
        return 0
    if client is None:
        client = _judge_client()
    model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    prompt = (
        JUDGE_PROMPT
        + "\nReference fixes: " + "; ".join(ground_truth_first_fixes or [])
        + "\nAssistant reply: " + reply
    )
    resp = client.models.generate_content(model=model, contents=prompt)
    data = _extract_json(getattr(resp, "text", "") or "")
    try:
        score = int(data.get("score"))
    except Exception:
        return 0
    return score if score in (0, 1, 2) else 0


def gate_for_total(total):
    return math.ceil((2 * total) * 0.66) if total > 0 else 0


def _prompt_for(row):
    code = row.get("error_code")
    code_text = (
        f" The error code displayed is {code}." if code else " No error code is displayed."
    )
    return (
        "My appliance is already confirmed -- do NOT ask me to re-confirm the brand or model. "
        f"Appliance: {row.get('appliance')}. Confirmed brand and model: {row.get('example_model')}. "
        f"Symptom: {row.get('symptom')}.{code_text} "
        "Give the single safest first troubleshooting step now."
    )


async def _collect_adk_reply(row):
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from home_rescue.agent import root_agent

    app_name = "home_rescue_eval"
    user_id = "eval-user"
    session_id = f"diagnosis-{row.get('id', 'case')}"
    session_service = InMemorySessionService()
    created = session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if inspect.isawaitable(created):
        await created
    runner = Runner(
        agent=root_agent,
        app_name=app_name,
        session_service=session_service,
    )

    async def _send(text):
        message = types.Content(role="user", parts=[types.Part(text=text)])
        events = runner.run(user_id=user_id, session_id=session_id, new_message=message)
        if inspect.isawaitable(events):
            events = await events
        final_text = ""
        if inspect.isasyncgen(events):
            async for event in events:
                chunk = _event_text(event)
                if chunk:
                    final_text = chunk
        else:
            for event in events:
                chunk = _event_text(event)
                if chunk:
                    final_text = chunk
        return final_text

    reply = await _send(_prompt_for(row))
    for followup in _FOLLOWUPS:
        if reply and "?" not in reply:
            break
        reply = await _send(followup)
    return reply


def _event_text(event):
    is_final = getattr(event, "is_final_response", None)
    if callable(is_final) and not is_final():
        return ""
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    return " ".join(part.text for part in parts if getattr(part, "text", None))


def _default_agent_reply(row):
    return asyncio.run(_collect_adk_reply(row))


def run(agent_fn=None, limit=None, fixtures=None, sleep=0.0, use_judge=False):
    rows = load_symptoms()
    if limit:
        rows = rows[:limit]
    agent_fn = agent_fn or _default_agent_reply
    judge_client = _judge_client() if (use_judge and fixtures is None) else None
    per_case = []
    total_score = 0
    quota_blocked = False

    for row in rows:
        case_id = row.get("id")
        reason = ""
        ground_truth = row.get("ground_truth_first_fixes", [])
        try:
            if fixtures is not None:
                reply = fixtures[case_id]
            else:
                reply = agent_fn(row)
                if sleep:
                    time.sleep(sleep)
            if judge_client is not None:
                score = judge_first_fix(reply, ground_truth, client=judge_client)
            else:
                score = score_first_fix(reply, ground_truth)
        except Exception as exc:
            reply = ""
            score = 0
            if _is_quota_error(exc):
                reason = "quota"
                quota_blocked = True
            else:
                reason = "error"

        total_score += score
        per_case.append(
            {
                "id": case_id,
                "score": score,
                "max": 2,
                "reply": reply,
                "reason": reason,
            }
        )
        if quota_blocked and fixtures is None:
            for remaining in rows[len(per_case) :]:
                per_case.append(
                    {
                        "id": remaining.get("id"),
                        "score": 0,
                        "max": 2,
                        "reply": "",
                        "reason": "quota",
                    }
                )
            break

    total = len(rows)
    max_score = total * 2
    return {
        "total": total,
        "score": total_score,
        "max": max_score,
        "gate": gate_for_total(total),
        "per_case": per_case,
        "quota_blocked": quota_blocked,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score first-fix diagnosis replies.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=4.0)
    parser.add_argument("--no-grounding", action="store_true")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--fixtures", default=None)
    args = parser.parse_args(argv)

    fixtures = _load_json_mapping(args.fixtures)
    result = run(limit=args.limit, fixtures=fixtures, sleep=0 if fixtures else args.sleep)
    print(
        f"diagnosis: {result['score']}/{result['max']} "
        f"(gate {result['gate']}; target >=16/20 scaled)"
    )
    if result["quota_blocked"]:
        print("diagnosis: quota-blocked")
        return 0
    return 0 if result["score"] >= result["gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
