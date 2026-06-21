"""Plate-read spike: can Gemini read the model number off a data-plate photo?

Scores extracted model numbers against spikes/datasets/plates/labels.csv.
Run:  py spikes/plate_read_spike.py [--model M] [--limit N]
ASCII only. Throwaway.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gemini_client import (  # noqa: E402
    REPO_ROOT, DEFAULT_MODEL, make_client, extract_json, generate_text,
)

PLATES = REPO_ROOT / "spikes" / "datasets" / "plates"
LABELS = PLATES / "labels.csv"

PROMPT = (
    "You are reading the data/spec plate of a household appliance from a photo. "
    "Identify the MODEL number (the manufacturer model code, NOT the serial number, "
    "NOT the part number). Respond with ONLY compact JSON, no prose: "
    '{"brand": <string or null>, "model_number": <string or null>, '
    '"error_code": <string or null>}.'
)


def normalize_model(s):
    if not s:
        return ""
    s = str(s).upper()
    s = "".join(ch for ch in s if not ch.isspace())
    if "/" in s:  # drop region suffix like /AA
        s = s.split("/", 1)[0]
    if len(s) > 4 and s.endswith("00"):  # drop trailing revision 00
        s = s[:-2]
    keep = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-()")
    return "".join(ch for ch in s if ch in keep)


def verdict(true_model, extracted):
    nt, ne = normalize_model(true_model), normalize_model(extracted)
    if not ne:
        return "MISS"
    if nt and nt == ne:
        return "EXACT"
    if nt and (nt in ne or ne in nt):
        return "LOOSE"
    return "MISS"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds between calls (free-tier pacing)")
    args = ap.parse_args()

    if not LABELS.exists():
        print(f"labels.csv not found at {LABELS}")
        return 2
    rows = list(csv.DictReader(LABELS.open(encoding="utf-8")))
    if args.limit:
        rows = rows[: args.limit]

    client = make_client()
    from google.genai import types

    print(f"== plate-read spike | model={args.model} | {len(rows)} labeled images ==")
    results = []
    for r in rows:
        fn = r["filename"]
        img = PLATES / fn
        if not img.exists():
            print(f"  MISSING  {fn}  (save the image here)")
            continue
        part = types.Part.from_bytes(data=img.read_bytes(), mime_type="image/jpeg")
        text = generate_text(client, args.model, [part, PROMPT])
        j = extract_json(text) or {}
        got = j.get("model_number") or ""
        v = verdict(r["true_model"], got)
        results.append((r, v))
        print(f"  [{v:5}] {r['difficulty']:6} true={r['true_model']:18} got={got}")
        time.sleep(args.sleep)

    if not results:
        print("\nNo images scored.")
        return 1

    tot = len(results)
    exact = sum(1 for _, v in results if v == "EXACT")
    loose = sum(1 for _, v in results if v == "LOOSE")
    print(f"\nEXACT {exact}/{tot}   EXACT+LOOSE {exact + loose}/{tot}")
    for diff in ("easy", "medium", "hard"):
        sub = [(r, v) for r, v in results if r["difficulty"] == diff]
        if sub:
            e = sum(1 for _, v in sub if v == "EXACT")
            el = sum(1 for _, v in sub if v in ("EXACT", "LOOSE"))
            print(f"  {diff:6}: EXACT {e}/{len(sub)}   EXACT+LOOSE {el}/{len(sub)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
