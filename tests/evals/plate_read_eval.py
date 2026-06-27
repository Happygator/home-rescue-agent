"""Runnable spec-plate read eval.

This module is intentionally import-safe: live model code is imported only inside
the scoring path that needs it.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLATES_DIR = REPO_ROOT / "spikes" / "datasets" / "plates"
LABELS_PATH = PLATES_DIR / "labels.csv"


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


def load_labels():
    with LABELS_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def gate_for_total(total):
    if total <= 0:
        return 0
    return min(total, math.ceil(total * 7 / 8))


def score_plate(read_fn=None, labels=None, limit=None):
    if labels is None:
        labels = load_labels()
    rows = labels[:limit] if limit else list(labels)
    if read_fn is None:
        from home_rescue.tools import read_spec_plate

        read_fn = read_spec_plate
    from home_rescue.tools import canonicalize_symbols, normalize_model

    def _ocr_match(read_model, true_model):
        a = canonicalize_symbols(normalize_model(read_model))
        b = canonicalize_symbols(normalize_model(true_model))
        return bool(a) and bool(b) and (a == b or a in b or b in a)

    misses = []
    correct = 0
    quota_blocked = False

    for row in rows:
        filename = row["filename"]
        try:
            result = read_fn(PLATES_DIR / filename) or {}
        except Exception as exc:
            reason = "quota" if _is_quota_error(exc) else "error"
            misses.append({"filename": filename, "reason": reason, "error": str(exc)})
            quota_blocked = quota_blocked or reason == "quota"
            if reason == "quota":
                remaining = rows[rows.index(row) + 1 :]
                misses.extend(
                    {"filename": r["filename"], "reason": "quota"} for r in remaining
                )
                break
            continue

        read_model = result.get("model_number")
        if _ocr_match(read_model, row["true_model"]):
            correct += 1
        else:
            misses.append(
                {
                    "filename": filename,
                    "reason": "mismatch",
                    "true_model": row["true_model"],
                    "read_model": read_model,
                    "brand": result.get("brand"),
                }
            )

    return {
        "total": len(rows),
        "correct": correct,
        "misses": misses,
        "gate": gate_for_total(len(rows)),
        "quota_blocked": quota_blocked,
    }


def _fixture_read(fixtures):
    def read(path):
        filename = Path(path).name
        if filename not in fixtures:
            raise KeyError(f"missing fixture for {filename}")
        return fixtures[filename]

    return read


def _retrying_live_read(sleep_seconds):
    from home_rescue.tools import read_spec_plate

    def read(path):
        attempts = 0
        while True:
            try:
                return read_spec_plate(path)
            except Exception as exc:
                if not _is_quota_error(exc) or attempts >= 2:
                    raise
                attempts += 1
                time.sleep(sleep_seconds)

    return read


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score spec-plate reads.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--fixtures", default=None)
    parser.add_argument("--sleep", type=float, default=4.0)
    args = parser.parse_args(argv)

    fixtures = _load_json_mapping(args.fixtures)
    read_fn = _fixture_read(fixtures) if fixtures is not None else _retrying_live_read(args.sleep)
    result = score_plate(read_fn, load_labels(), limit=args.limit)
    print(f"plate_read: {result['correct']}/{result['total']}")
    if result["quota_blocked"]:
        print("plate_read: quota-blocked")
        return 0
    return 0 if result["correct"] >= result["gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
