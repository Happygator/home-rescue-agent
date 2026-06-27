"""Capture live eval fixtures for offline HomeRescue eval runs.

This script makes real Gemini/ADK calls when executed. It writes the JSON
mapping files consumed by tests/evals/run_evals.py --fixtures-dir.
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES_DIR = REPO_ROOT / "tests" / "evals" / "fixtures"
DEFAULT_CAPTURE_DB = Path(tempfile.gettempdir()) / "home_rescue_capture_fixtures.db"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.evals import diagnosis_eval, plate_read_eval, safety_eval  # noqa: E402

SUITES = ("plate", "diagnosis", "safety")


def _event_text(event: Any) -> str:
    is_final = getattr(event, "is_final_response", None)
    if callable(is_final) and not is_final():
        return ""
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    return " ".join(part.text for part in parts if getattr(part, "text", None))


async def _create_runner_session(*, session_id: str, db_path: Path):
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from home_rescue.agent import root_agent

    app_name = "home_rescue_fixture_capture"
    user_id = "fixture-user"
    session_service = InMemorySessionService()
    created = session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        state={"db_path": str(db_path)},
        session_id=session_id,
    )
    if inspect.isawaitable(created):
        await created

    return (
        Runner(
            agent=root_agent,
            app_name=app_name,
            session_service=session_service,
        ),
        user_id,
        session_id,
    )


async def _send_agent_message(
    runner: Any,
    *,
    user_id: str,
    session_id: str,
    prompt: str,
) -> str:
    from google.genai import types

    message = types.Content(role="user", parts=[types.Part(text=prompt)])
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


async def _run_agent_turn(prompt: str, *, session_id: str, db_path: Path) -> str:
    runner, user_id, session_id = await _create_runner_session(
        session_id=session_id,
        db_path=db_path,
    )
    return await _send_agent_message(
        runner,
        user_id=user_id,
        session_id=session_id,
        prompt=prompt,
    )


async def _collect_diagnosis_reply(row: dict, *, db_path: Path) -> str:
    runner, user_id, session_id = await _create_runner_session(
        session_id=f"diagnosis-{row.get('id', 'case')}",
        db_path=db_path,
    )

    reply = await _send_agent_message(
        runner,
        user_id=user_id,
        session_id=session_id,
        prompt=diagnosis_eval._prompt_for(row),
    )
    for followup in diagnosis_eval._FOLLOWUPS:
        if reply and "?" not in reply:
            break
        reply = await _send_agent_message(
            runner,
            user_id=user_id,
            session_id=session_id,
            prompt=followup,
        )
    return reply


def _err_summary(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _call_with_quota_retries(
    fn: Callable[[], Any],
    *,
    retries: int,
    sleep_seconds: float,
) -> Any:
    attempts = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if (
                not diagnosis_eval._is_quota_error(exc)
                and not plate_read_eval._is_quota_error(exc)
            ) or attempts >= retries:
                raise
            attempts += 1
            print(
                f"quota/rate limit on attempt {attempts}; "
                f"sleeping {sleep_seconds:g}s before retry",
                flush=True,
            )
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)


def _sleep_between(index: int, total: int, sleep_seconds: float) -> None:
    if index < total and sleep_seconds > 0:
        time.sleep(sleep_seconds)


def _limited(items: list[Any], limit: int | None) -> list[Any]:
    if limit is None:
        return items
    return items[:limit]


def capture_plate(*, limit: int | None, sleep_seconds: float, retries: int) -> dict:
    from home_rescue.tools import read_spec_plate

    rows = _limited(plate_read_eval.load_labels(), limit)
    fixtures = {}
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        filename = row["filename"]
        photo_path = plate_read_eval.PLATES_DIR / filename
        print(f"plate {index}/{total}: {filename}", flush=True)
        fixtures[filename] = _call_with_quota_retries(
            lambda path=photo_path: read_spec_plate(path),
            retries=retries,
            sleep_seconds=sleep_seconds,
        )
        _sleep_between(index, total, sleep_seconds)
    return fixtures


def capture_diagnosis(
    *,
    limit: int | None,
    sleep_seconds: float,
    retries: int,
    db_path: Path,
) -> dict:
    rows = _limited(diagnosis_eval.load_symptoms(), limit)
    fixtures = {}
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        case_id = row["id"]
        print(f"diagnosis {index}/{total}: {case_id}", flush=True)
        fixtures[case_id] = _call_with_quota_retries(
            lambda current=row: asyncio.run(
                _collect_diagnosis_reply(current, db_path=db_path)
            ),
            retries=retries,
            sleep_seconds=sleep_seconds,
        )
        _sleep_between(index, total, sleep_seconds)
    return fixtures


def capture_safety(*, sleep_seconds: float, retries: int, db_path: Path) -> dict:
    fixtures = {}
    total = len(safety_eval.DANGEROUS_PROMPTS)
    for index, prompt in enumerate(safety_eval.DANGEROUS_PROMPTS, start=1):
        print(f"safety {index}/{total}", flush=True)
        fixtures[prompt] = _call_with_quota_retries(
            lambda text=prompt, i=index: asyncio.run(
                _run_agent_turn(text, session_id=f"safety-{i}", db_path=db_path)
            ),
            retries=retries,
            sleep_seconds=sleep_seconds,
        )
        _sleep_between(index, total, sleep_seconds)
    return fixtures


def _load_existing(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Fixture file must contain a JSON object: {path}")
    return data


def _write_json(path: Path, data: dict, *, merge: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data
    if merge:
        payload = _load_existing(path)
        payload.update(data)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture live Gemini fixtures for offline eval replay."
    )
    parser.add_argument(
        "--fixtures-dir",
        default=str(DEFAULT_FIXTURES_DIR),
        help="Directory to write plate.json, diagnosis.json, and safety.json.",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=SUITES,
        default=list(SUITES),
        help="Fixture suite(s) to capture.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit plate and diagnosis cases. Safety always captures every prompt.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=4.0,
        help="Seconds to sleep between live calls and quota retry attempts.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Quota/rate-limit retries per live call.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace each fixture file instead of merging captured keys.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_CAPTURE_DB),
        help="SQLite DB path for ADK case state during diagnosis/safety capture.",
    )
    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be >= 0")
    if args.sleep < 0:
        parser.error("--sleep must be >= 0")
    if args.retries < 0:
        parser.error("--retries must be >= 0")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    fixtures_dir = Path(args.fixtures_dir)
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    suites = list(dict.fromkeys(args.only))
    merge = not args.replace

    for suite in suites:
        try:
            if suite == "plate":
                data = capture_plate(
                    limit=args.limit,
                    sleep_seconds=args.sleep,
                    retries=args.retries,
                )
            elif suite == "diagnosis":
                data = capture_diagnosis(
                    limit=args.limit,
                    sleep_seconds=args.sleep,
                    retries=args.retries,
                    db_path=db_path,
                )
            elif suite == "safety":
                data = capture_safety(
                    sleep_seconds=args.sleep,
                    retries=args.retries,
                    db_path=db_path,
                )
            else:
                raise ValueError(f"Unknown suite: {suite}")
        except Exception as exc:
            print(f"{suite}: failed before writing fixture: {_err_summary(exc)}")
            return 1

        output_path = fixtures_dir / f"{suite}.json"
        _write_json(output_path, data, merge=merge)
        print(f"{suite}: wrote {len(data)} captured entries to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
