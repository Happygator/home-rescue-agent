"""Reopen: Logic and entry point for resuming/reopening a case file."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from appliance_fixer.case_store import CaseStore


def reopen_case(case_id: str, store: CaseStore) -> tuple[dict, str]:
    """Load case by ID, generate recap, and prepare session/state data.

    Raises ValueError for missing or invalid cases.
    """
    case = store.load_case(case_id)
    if not case:
        raise ValueError(f"Case '{case_id}' not found.")
    
    # Verify the JSON payload has necessary structure
    if "data" not in case or not isinstance(case["data"], dict):
        raise ValueError(f"Case '{case_id}' has corrupt or missing data.")

    # Check for required CaseFile schema keys
    required_keys = ("symptom_text", "photos", "steps")
    if not all(k in case["data"] for k in required_keys):
        raise ValueError(f"Case '{case_id}' has corrupt or missing data.")

    recap_text = store.recap(case_id)
    return case, recap_text


def main():
    parser = argparse.ArgumentParser(description="Reopen an Appliance Fixer case by ID.")
    parser.add_argument("case_id", help="The unique ID of the case to reopen.")
    parser.add_argument(
        "--db",
        default="appliance_fixer.db",
        help="Path to the SQLite database file.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database file '{db_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    store = CaseStore(db_path)
    try:
        case, recap_text = reopen_case(args.case_id, store)
        print(recap_text)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
