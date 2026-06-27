"""Appliance data modules + the appliance registry.

The registry maps a normalized appliance type to its data module so grounding,
model validation, and escalation can resolve curated data by appliance instead
of hardcoding the fridge module. Fridge stays the default for backward
compatibility: every existing caller that omits an appliance keeps working.
"""
from __future__ import annotations

import re

from . import dishwasher, fridge

# Normalized appliance type -> data module.
REGISTRY = {
    fridge.APPLIANCE: fridge,          # "refrigerator"
    dishwasher.APPLIANCE: dishwasher,  # "dishwasher"
}

# Default module when an appliance is unknown/omitted (back-compat with fridge-only callers).
DEFAULT_MODULE = fridge

# Synonyms / loose phrasings -> canonical appliance key.
_SYNONYMS = {
    "fridge": fridge.APPLIANCE,
    "refrigerator": fridge.APPLIANCE,
    "freezer": fridge.APPLIANCE,
    "dishwasher": dishwasher.APPLIANCE,
    "dish washer": dishwasher.APPLIANCE,
    "dish-washer": dishwasher.APPLIANCE,
    "dishwaser": dishwasher.APPLIANCE,
}


def normalize_appliance(appliance):
    """Map free-text appliance to a canonical registry key. Empty -> default appliance."""
    if not appliance:
        return DEFAULT_MODULE.APPLIANCE
    key = str(appliance).strip().lower()
    return _SYNONYMS.get(key, key)


def module_for(appliance):
    """Return the data module for an appliance type, defaulting to fridge for back-compat."""
    return REGISTRY.get(normalize_appliance(appliance), DEFAULT_MODULE)


# Appliance-type hints (appliance, regex word-stems), checked in order; on a tie the earlier wins.
# Word-boundary matching means "washer" does NOT fire inside "dishwasher".
_TYPE_HINTS = (
    ("dishwasher", ("dishwasher", "dish ?washer", "dishes", "rinse aid")),
    ("refrigerator", ("refrigerator", "fridge", "freezer", "fresh ?food", "ice ?maker", "crisper")),
    ("washer", ("washing machine", "washer", "laundry", "spin cycle")),
)


def infer_appliance(text):
    """Best-effort appliance-type guess from free text (e.g. the user's symptom).

    Deterministic keyword match (no model). Returns a canonical appliance key
    ("refrigerator" / "dishwasher" / "washer") or None when the text gives no clear hint.
    """
    if not text:
        return None
    t = str(text).lower()
    best, best_score = None, 0
    for appliance, patterns in _TYPE_HINTS:
        score = sum(1 for p in patterns if re.search(r"\b" + p + r"\b", t))
        if score > best_score:
            best, best_score = appliance, score
    return best
