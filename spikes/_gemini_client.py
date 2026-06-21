"""Shared helpers for the throwaway Gemini spike harness. ASCII only.

Key resolution order: GEMINI_KEY.txt at the repo root, then GOOGLE_API_KEY /
GEMINI_API_KEY env vars.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "gemini-2.5-flash"


def load_key() -> str:
    f = REPO_ROOT / "GEMINI_KEY.txt"
    raw = ""
    if f.exists():
        raw = f.read_text(encoding="utf-8").strip()
    if not raw:
        raw = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not raw:
        raise RuntimeError(
            "No API key found. Put it in GEMINI_KEY.txt at the repo root, "
            "or set GOOGLE_API_KEY."
        )
    # Tolerate "NAME=value" lines and surrounding quotes.
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY"):
        if raw.upper().startswith(name + "="):
            raw = raw.split("=", 1)[1].strip()
    return raw.strip().strip('"').strip("'").strip()


def make_client():
    from google import genai
    return genai.Client(api_key=load_key())


def extract_json(text):
    """Best-effort: pull the first {...} object out of a model response."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        v = json.loads(t[start:end + 1])
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def _parse_retry_delay(msg):
    m = re.search(r"retry\s*delay['\"]?\s*[:=]\s*['\"]?(\d+)", msg, re.IGNORECASE)
    return int(m.group(1)) if m else None


def generate_text(client, model, contents, use_search=False, retries=6, base_sleep=8.0):
    """Return resp.text (stripped) or None.

    Retries free-tier rate-limit 429s, honoring the API's retryDelay when given.
    Gives up immediately ONLY on genuinely depleted billing credits, where
    retrying cannot help. A plain "exceeded your current quota" is a transient
    per-minute limit and IS retried.
    """
    from google.genai import types
    cfg = None
    if use_search:
        cfg = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=cfg)
            return (resp.text or "").strip()
        except Exception as exc:
            msg = str(exc)
            low = msg.lower()
            permanent = ("prepayment" in low) or ("deplet" in low)
            is_429 = ("429" in msg) or ("resource_exhausted" in low)
            if is_429 and not permanent:
                if attempt == retries - 1:
                    break
                wait = _parse_retry_delay(msg)
                wait = min(70.0, wait + 2) if wait is not None else min(60.0, base_sleep * (2 ** attempt))
                print(f"  [rate-limit] waiting {wait:.0f}s then retrying")
                time.sleep(wait)
                continue
            print(f"  [billing] credits depleted: {msg[:120]}" if permanent else f"  [api error] {msg[:200]}")
            return None
    print("  [rate-limit] gave up after retries")
    return None
