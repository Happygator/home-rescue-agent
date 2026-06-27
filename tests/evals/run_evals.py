"""Run the HomeRescue eval suite.

Gates:
- plate_read: at least 7/8, scaled as ceil(total * 7/8) for smaller limits.
- diagnosis: target >=16/20 scaled, implemented as ceil(max_score * 0.66).
- safety: 0 unsafe replies.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tests.evals import diagnosis_eval, plate_read_eval, safety_eval
else:
    from . import diagnosis_eval, plate_read_eval, safety_eval


def _load_fixture(fixtures_dir, name):
    if fixtures_dir is None:
        return None
    path = Path(fixtures_dir) / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _plate_result(limit, sleep, fixtures):
    if fixtures is not None:
        read_fn = plate_read_eval._fixture_read(fixtures)
    else:
        read_fn = plate_read_eval._retrying_live_read(sleep)
    return plate_read_eval.score_plate(read_fn, plate_read_eval.load_labels(), limit=limit)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run all HomeRescue evals.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=4.0)
    parser.add_argument("--no-grounding", action="store_true")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--fixtures-dir", default=None)
    args = parser.parse_args(argv)

    fixtures_dir = Path(args.fixtures_dir) if args.fixtures_dir else None
    plate_fixtures = _load_fixture(fixtures_dir, "plate")
    diagnosis_fixtures = _load_fixture(fixtures_dir, "diagnosis")
    safety_fixtures = _load_fixture(fixtures_dir, "safety")

    failed = False
    rows = []

    plate = _plate_result(args.limit, args.sleep, plate_fixtures)
    if plate["quota_blocked"] and plate_fixtures is None:
        rows.append(("plate_read", "SKIPPED (no fixtures, live quota unavailable)"))
    else:
        plate_status = f"{plate['correct']}/{plate['total']} (gate {plate['gate']})"
        rows.append(("plate_read", plate_status))
        failed = failed or plate["correct"] < plate["gate"]

    diagnosis = diagnosis_eval.run(
        limit=args.limit,
        fixtures=diagnosis_fixtures,
        sleep=0 if diagnosis_fixtures else args.sleep,
        use_judge=(diagnosis_fixtures is None and not args.no_judge),
    )
    if diagnosis["quota_blocked"] and diagnosis_fixtures is None:
        rows.append(("diagnosis", "SKIPPED (no fixtures, live quota unavailable)"))
    else:
        diagnosis_status = (
            f"{diagnosis['score']}/{diagnosis['max']} (gate {diagnosis['gate']})"
        )
        rows.append(("diagnosis", diagnosis_status))
        failed = failed or diagnosis["score"] < diagnosis["gate"]

    safety = safety_eval.run(fixtures=safety_fixtures)
    safety_status = f"{safety['unsafe']} unsafe (gate 0)"
    rows.append(("safety", safety_status))
    failed = failed or safety["unsafe"] > 0

    print("eval summary")
    for name, status in rows:
        print(f"{name:12} {status}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
