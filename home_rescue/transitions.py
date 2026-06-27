"""Status state machine for HomeRescue cases.

This module is the ONLY place that decides a case's next status. Every tool and
endpoint that changes status MUST call transition() to get the new status, rather
than assigning status strings directly. This kills scattered status logic.
"""
from __future__ import annotations

# All valid case statuses.
VALID_STATUSES = ("intake", "diagnosing", "awaiting_user", "escalated", "resolved")

# Terminal statuses cannot transition further.
TERMINAL_STATUSES = ("escalated", "resolved")

# Legal moves: {current_status: {event: next_status}}.
LEGAL_TRANSITIONS = {
    "intake": {
        "start_diagnosis": "diagnosing",
        "escalate": "escalated",
    },
    "diagnosing": {
        "start_diagnosis": "diagnosing",  # idempotent re-entry
        "await_user": "awaiting_user",
        "resolve": "resolved",
        "escalate": "escalated",
    },
    "awaiting_user": {
        "user_responded": "diagnosing",
        "await_user": "awaiting_user",  # idempotent
        "resolve": "resolved",
        "escalate": "escalated",
    },
    "escalated": {},  # terminal
    "resolved": {},  # terminal
}


def transition(case_or_status, event: str) -> str:
    """Return the new status for `event` applied to the current status.

    `case_or_status` may be either a case dict (its "status" key is read) or a
    status string. Raises ValueError on an unknown status, unknown/illegal event,
    or any move out of a terminal status.
    """
    if isinstance(case_or_status, dict):
        current = case_or_status.get("status")
    else:
        current = case_or_status

    if current not in LEGAL_TRANSITIONS:
        raise ValueError(f"Unknown status: {current!r}")

    allowed = LEGAL_TRANSITIONS[current]
    if event not in allowed:
        raise ValueError(
            f"Illegal transition: cannot apply event {event!r} to status {current!r}"
        )
    return allowed[event]
