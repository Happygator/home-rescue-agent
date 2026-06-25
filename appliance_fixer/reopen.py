"""Deterministic reopen: load a saved case by id, build its recap, continue in a fresh
session. This is the project's headline 'memory' feature and uses NO model calls."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from appliance_fixer.case_store import CaseStore

# Keys every healthy CaseFile blob must contain.
REQUIRED_CASEFILE_KEYS = ("symptom_text", "media", "steps")


class CaseNotFoundError(ValueError):
    """Raised when a case id does not exist."""


class CorruptCaseError(ValueError):
    """Raised when a case row exists but its data blob is missing/corrupt."""


def reopen_case(case_id: str, store: CaseStore) -> tuple[dict, str]:
    """Load a case by id and return (case, recap_text).

    Raises CaseNotFoundError if the id is unknown, CorruptCaseError if the row exists
    but its CaseFile blob is missing required keys / not a dict.
    """
    case = store.load_case(case_id)
    if case is None:
        raise CaseNotFoundError(f"Could not find that repair (case '{case_id}').")
    data = case.get("data")
    if not isinstance(data, dict) or not all(k in data for k in REQUIRED_CASEFILE_KEYS):
        raise CorruptCaseError(f"Case '{case_id}' has corrupt or missing data.")
    return case, store.recap(case_id)


def make_reopen_message(case: dict, recap: str) -> str:
    """Deterministic 'continue' message a fresh session replays to the user. No LLM.

    Format:
        Resuming {Brand Model} ({appliance}) - case {case_id}.
        Here is where we left off:

        {recap}

        What would you like to do next?
    """
    # Build a short appliance label from brand/model/appliance (any may be None).
    brand = case.get("brand")
    model = case.get("model_number")
    appliance = case.get("appliance") or "appliance"
    label_bits = [b for b in (brand, model) if b]
    label = " ".join(label_bits) if label_bits else appliance
    header = f"Resuming {label} ({appliance}) - case {case['case_id']}."
    return (
        f"{header}\n"
        f"Here is where we left off:\n\n"
        f"{recap}\n\n"
        f"What would you like to do next?"
    )


def reopen_and_continue(case_id: str, store: CaseStore) -> dict:
    """Full headline path in one call: load -> recap -> continue message.

    Returns {case_id, status, recap, message}. Raises CaseNotFoundError/CorruptCaseError.
    This is the deterministic stand-in for 'a fresh session replays the recap'; the real
    ADK agent wiring lands in B5 and will call reopen_case()/make_reopen_message().
    """
    case, recap = reopen_case(case_id, store)
    return {
        "case_id": case["case_id"],
        "status": case["status"],
        "recap": recap,
        "message": make_reopen_message(case, recap),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reopen an Appliance Fixer case by id.")
    parser.add_argument("case_id", help="The case id to reopen.")
    parser.add_argument("--db", default="appliance_fixer.db", help="SQLite db path.")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: database '{db_path}' does not exist.", file=sys.stderr)
        return 1
    store = CaseStore(db_path)
    try:
        result = reopen_and_continue(args.case_id, store)
    except ValueError as exc:  # CaseNotFoundError / CorruptCaseError
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(result["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
