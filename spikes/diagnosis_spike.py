"""Diagnosis spike: Gemini-alone vs +grounding vs +curated, LLM-judged 0/1/2.

Settles premise #2 (is grounding good enough, or author a curated KB?).
Run:  py spikes/diagnosis_spike.py [--model M] [--limit N] [--no-grounding]
ASCII only. Throwaway. LLM-judge scores are approximate; spot-check them.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gemini_client import (  # noqa: E402
    REPO_ROOT, DEFAULT_MODEL, make_client, extract_json, generate_text,
)

DATA = REPO_ROOT / "spikes" / "datasets" / "diagnosis_symptoms.jsonl"

SYSTEM = (
    "You are a careful household-appliance repair assistant. Given a symptom, name the single "
    "MOST LIKELY first thing to check or fix, in ONE short sentence. Never recommend unsafe work "
    "(gas, mains/live electrical, sealed refrigerant); for those, tell the user to call a professional."
)

JUDGE_TMPL = (
    "You are grading an appliance-repair answer.\n"
    "Symptom: {sym}\n"
    "Reference correct first-fixes: {ref}\n"
    "Candidate answer: {cand}\n"
    "Score 2 if the candidate names a correct AND safe first fix consistent with the reference; "
    "1 if plausible but incomplete or only partly right; 0 if wrong OR it recommends an unsafe action. "
    'Respond ONLY as JSON: {{"score": 0, "reason": "<short>"}} with score in 0,1,2.'
)


def ask(client, model, symptom, error_code, reference=None, use_search=False):
    parts = [SYSTEM]
    if reference:
        parts.append("Reference (known likely fixes, ranked): " + "; ".join(reference))
    line = "Symptom: " + symptom
    if error_code:
        line += " | Error code: " + str(error_code)
    parts.append(line)
    parts.append("Answer with ONE short sentence naming the first fix.")
    return generate_text(client, model, "\n".join(parts), use_search=use_search)


def judge(client, model, symptom, reference, candidate):
    if not candidate or candidate.startswith("("):
        return (None, "not scored")
    txt = generate_text(client, model, JUDGE_TMPL.format(
        sym=symptom, ref="; ".join(reference), cand=candidate))
    if txt is None:
        return (None, "judge unavailable (rate-limit?)")  # exclude, do NOT count as a real 0
    j = extract_json(txt) or {}
    try:
        sc = int(j.get("score"))
        if sc not in (0, 1, 2):
            raise ValueError
        return (sc, str(j.get("reason", ""))[:80])
    except Exception:
        return (0, "unparseable judge output")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-grounding", action="store_true")
    ap.add_argument("--no-judge", action="store_true",
                    help="skip LLM-judge calls; print candidates + ground truth for hand-scoring")
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds between symptoms (free-tier pacing)")
    args = ap.parse_args()

    if not DATA.exists():
        print(f"dataset not found at {DATA}")
        return 2
    rows = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    client = make_client()
    print(f"== diagnosis spike | model={args.model} | {len(rows)} symptoms | "
          f"grounding={'off' if args.no_grounding else 'on'} ==")
    print("(LLM-judge scores are approximate; spot-check them.)\n")

    labels = {"A": "alone    ", "B": "grounding", "C": "curated  "}
    tot = {"A": [], "B": [], "C": []}
    unsafe = {"A": False, "B": False, "C": False}

    for r in rows:
        sym, ec = r["symptom"], r.get("error_code")
        ref = r.get("ground_truth_first_fixes", [])
        cand = {
            "A": ask(client, args.model, sym, ec),
            "B": "(skipped)" if args.no_grounding else (
                ask(client, args.model, sym, ec, use_search=True) or "(grounding unavailable)"),
            "C": ask(client, args.model, sym, ec, reference=ref),
        }
        print(r.get("id", "?") + ":")
        if args.no_judge:
            print(f"  ground_truth: {'; '.join(ref)}")
        for k in ("A", "B", "C"):
            if args.no_judge:
                sc, reason = (None, "")
            else:
                sc, reason = judge(client, args.model, sym, ref, cand[k])
            if sc is not None:
                tot[k].append(sc)
                if sc == 0 and "unsafe" in reason.lower():
                    unsafe[k] = True
            scs = "-" if sc is None else str(sc)
            print(f"  {labels[k]} score={scs} :: {(cand[k] or '')[:100]}")
        print()
        time.sleep(args.sleep)

    if args.no_judge:
        print("== --no-judge: hand-score the 'alone' / 'curated' answers above against ground_truth ==")
        return 0

    print("== totals ==")
    pct = {}
    for k in ("A", "B", "C"):
        n, s = len(tot[k]), sum(tot[k])
        mx = 2 * n
        pct[k] = (100.0 * s / mx) if mx else 0.0
        extra = " [skipped]" if n == 0 else ""
        print(f"  {labels[k]}: {s}/{mx} ({pct[k]:.0f}%){extra}")

    if not args.no_grounding and tot["B"] and pct["B"] >= 80 and not unsafe["B"]:
        print("\n-> grounding looks sufficient; a thin KB (safety rules + error-code table) may be enough.")
    else:
        print("\n-> grounding shaky (or unsafe answers seen); author the curated table for the demo symptoms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
