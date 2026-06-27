"""Live Gemini billing / quota probe.

Makes REAL calls to the Gemini API (gemini-2.5-flash by default) using the
project's AI Studio API key (via home_rescue.tools.load_key) and reports
whether calls succeed and whether paid billing appears to be active, vs.
free-tier rate limiting.

This is a diagnostic, not a test fixture: it spends a tiny amount of real
quota. Run:  py scripts/check_billing.py [--model M] [--burst N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the repo root importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from home_rescue.tools import load_key  # noqa: E402


def _err_detail(exc):
    """Best-effort (status, message) extraction from a google.genai error."""
    code = getattr(exc, "code", None)
    status = getattr(exc, "status", None)
    message = getattr(exc, "message", None)
    details = getattr(exc, "details", None)
    parts = []
    if code is not None:
        parts.append(f"code={code}")
    if status:
        parts.append(f"status={status}")
    if message:
        parts.append(f"message={message}")
    if details:
        parts.append(f"details={details}")
    if not parts:
        parts.append(f"{type(exc).__name__}: {exc}")
    return " ".join(parts)


def _is_quota(text):
    t = (text or "").lower()
    return "429" in t or "resource_exhausted" in t or "quota" in t


def _is_auth(text):
    t = (text or "").lower()
    return (
        "401" in t
        or "403" in t
        or "api key" in t
        or "api_key" in t
        or "permission_denied" in t
        or "unauthenticated" in t
    )


def _call(client, model, prompt):
    """Return (ok, text, detail). detail is the error string on failure."""
    try:
        resp = client.models.generate_content(model=model, contents=prompt)
        return True, (getattr(resp, "text", "") or "").strip(), resp
    except Exception as exc:  # noqa: BLE001 - we classify and report it
        return False, None, _err_detail(exc)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Live Gemini billing/quota probe (spends a little real quota)."
    )
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--burst", type=int, default=8,
                        help="Rapid follow-up calls to probe per-minute limits.")
    parser.add_argument("--prompt", default="Reply with exactly the single word: OK")
    args = parser.parse_args(argv)

    try:
        from google import genai
    except ImportError as exc:
        print(f"Missing google-genai SDK: {exc}", file=sys.stderr)
        return 2

    key = load_key()
    client = genai.Client(api_key=key)
    print(f"model: {args.model}")
    print(f"key:   ...{key[-4:]} (len {len(key)})")
    print("-" * 60)

    # 1) Single warm-up call.
    ok, text, payload = _call(client, args.model, args.prompt)
    if ok:
        print(f"single call OK -> {text!r}")
        usage = getattr(payload, "usage_metadata", None)
        if usage is not None:
            print(
                "  tokens: prompt={}, candidates={}, total={}".format(
                    getattr(usage, "prompt_token_count", "?"),
                    getattr(usage, "candidates_token_count", "?"),
                    getattr(usage, "total_token_count", "?"),
                )
            )
    else:
        print(f"single call FAILED -> {payload}")
        print("-" * 60)
        if _is_quota(payload):
            print("RESULT: quota exhausted / billing not active.")
        elif _is_auth(payload):
            print("RESULT: authentication/key problem (not a billing test result).")
        else:
            print("RESULT: call failed for another reason.")
        return 1

    # 2) Burst test to probe free-tier per-minute rate limits.
    successes = 1  # the warm-up counts
    first_failure = None
    for i in range(args.burst):
        ok, _text, payload = _call(client, args.model, args.prompt)
        if ok:
            successes += 1
        elif first_failure is None:
            first_failure = payload
    total = args.burst + 1
    print("-" * 60)
    print(f"burst: {successes}/{total} calls succeeded")
    if first_failure:
        print(f"  first failure: {first_failure}")

    # 3) Classify.
    print("-" * 60)
    if first_failure is None:
        print("RESULT: calls succeeded; no rate-limit hit in this run.")
        print("        (Billing looks active, or free-tier quota was available.)")
        return 0
    if _is_quota(first_failure):
        print("RESULT: calls work but hit a rate/quota limit "
              "(likely free-tier limits; billing may NOT be active).")
    elif _is_auth(first_failure):
        print("RESULT: authentication/key problem (not a billing test result).")
    else:
        print("RESULT: some calls failed for another reason.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
