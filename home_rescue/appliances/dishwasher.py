from __future__ import annotations

APPLIANCE = "dishwasher"

# Supported model numbers per brand (normalized, uppercase). Used by validate_model.
SUPPORTED_MODELS = {
    "LG": ["LDFC2423V", "LDFN4542", "LDP6810"],
}

# Per-brand model-number regex (loose; catches malformed reads before membership check).
MODEL_PATTERNS = {
    "LG": r"^L[DT][A-Z0-9]{3,}",
}

# Per-brand support contact (email + phone + display name) for escalation drafting.
SUPPORT_CONTACTS = {
    "LG": {"name": "LG", "email": "support@lg.com", "phone": "1-800-243-0000"},
}
DEFAULT_SUPPORT_CONTACT = {"name": "Appliance Service", "email": "support@appliance-repair.com", "phone": "1-800-000-0000"}

# Brand-specific error codes -> meaning + ranked fixes + DIY-safe flag + fault_class + source.
# Meanings + steps verified against LG US support 2026-06-25.
# An out-of-table code must NEVER be guessed.
_LG_LIST = "https://www.lg.com/us/support/help-library/lg-dishwasher-error-code-list-CT10000009-20150933422943"
_LG_AE = "https://www.lg.com/us/support/help-library/ae-e1-error-code-dish-washer--20150140935066"
_LG_OE = "https://www.lg.com/us/support/help-library/oe-error-code-dishwasher--20150986144736"
ERROR_CODES = {
    "LG": {
        "CL": {"meaning": "Child Lock / Control Lock is ON (not a fault).", "safe": True, "fixes": [
            "Open the door, press POWER, select a cycle, then hold RINSE and SPRAY together for 3 seconds to turn Control Lock off.",
        ], "fault_class": "default", "source": _LG_LIST},
        "bE": {"meaning": "Suds/detergent error - wrong detergent or the unit is not level (NOT a lock code).", "safe": True, "fixes": [
            "Use ONLY dishwasher detergent (never dish-washing liquid), filled to the line.",
            "Confirm the dishwasher is level.",
            "To clear existing suds, place 4-7 oz of milk in a bowl on the upper rack and run AUTO.",
        ], "fault_class": "default", "source": _LG_LIST},
        "PF": {"meaning": "Power-failure protection after an outage/interruption (not a fault).", "safe": True, "fixes": [
            "Press any control-panel key to clear PF after power is restored.",
            "Confirm the unit is on a dedicated grounded 120V/60Hz/15A+ circuit with no extension cord.",
        ], "fault_class": "default", "source": _LG_LIST},
        "IE": {"meaning": "Fill error - water did not reach level after about 10 minutes of filling.", "safe": True, "fixes": [
            "Confirm the water-supply valve under the sink is fully ON.",
            "Straighten any kinked fill line; confirm house water pressure (20-120 PSI).",
            "Make sure the drain-hose outlet is 10+ inches above the dishwasher base.",
            "In cold weather, check for frozen supply components; level the unit; remove flood-safe hoses if present.",
        ], "fault_class": "fill", "source": _LG_LIST},
        "OE": {"meaning": "Drain error - the dishwasher is not draining properly.", "safe": True, "fixes": [
            "Clean the bottom filter / coin trap.",
            "Check the drain hose for kinks or blockages; confirm a tight seal at the connection.",
            "If newly installed, confirm the garbage-disposal knockout plug was removed; clear sink-disposal clogs.",
        ], "fault_class": "drain", "source": _LG_OE},
        "AE": {"meaning": "Leak detected - water reached the base and tripped the float switch (also shows as E1).", "safe": False, "fixes": [
            "Confirm the unit is level (water pools to one side if not).",
            "Clean the door gasket; inspect for damage; clear/inspect the spray arms.",
            "Use only dishwasher detergent, correct amount (excess suds can trip the float).",
            "Turn the breaker OFF, remove the kick plate, dry the drain pan, allow 24-48h to evaporate, then reset. If the leak recurs, book service.",
        ], "fault_class": "leak", "source": _LG_AE},
        "E1": {"meaning": "Leak detected (same float-switch trip as AE).", "safe": False, "fixes": [
            "Follow the AE steps: level, gasket/spray-arm check, correct detergent, dry the drain pan 24-48h, then reset. If it recurs, book service.",
        ], "fault_class": "leak", "source": _LG_AE},
        "FE": {"meaning": "Overfill - too much water detected; the drain pump turns on automatically.", "safe": False, "fixes": [
            "Power OFF, switch the circuit breaker OFF for 10 seconds, restore power, restart.",
            "If FE returns, the inlet valve is likely stuck open - book service.",
        ], "fault_class": "fill", "source": _LG_LIST},
        "tE": {"meaning": "Thermal error - water temperature above about 194 F, or a thermistor problem.", "safe": False, "fixes": [
            "Power OFF, breaker OFF 10 s, restore power, restart once.",
            "If tE returns, book service (thermistor/heater).",
        ], "fault_class": "heater", "source": _LG_LIST},
        "HE": {"meaning": "Heater error - unable to heat the water, or water overheated above 149 F.", "safe": False, "fixes": [
            "Power OFF, breaker OFF 10 s, restore power, restart once - do NOT open the heater circuit.",
            "If HE returns, book service (heating element - not a DIY repair).",
        ], "fault_class": "heater", "source": _LG_LIST},
        "LE": {"meaning": "Motor error - possible motor or wiring-harness issue.", "safe": False, "fixes": [
            "Power OFF, breaker OFF 10 s, restore power, restart once (a transient glitch can clear).",
            "If LE returns, book service (motor/wiring).",
        ], "fault_class": "motor", "source": _LG_LIST},
        "CE": {"meaning": "Motor error - same motor/wiring family as LE.", "safe": False, "fixes": [
            "Power OFF, breaker OFF 10 s, restore power, restart once.",
            "If CE returns, book service (motor/control).",
        ], "fault_class": "motor", "source": _LG_LIST},
        "nE": {"meaning": "Vario motor error - the motor that controls the spray arms.", "safe": False, "fixes": [
            "Disconnect power for a few minutes and retry once.",
            "If nE returns, book service (vario motor).",
        ], "fault_class": "motor", "source": _LG_LIST},
    },
}

# Symptom key -> ranked, safety-approved fixes (easiest/safest first).
# Citation for the symptom path: the curated buckets are distilled from these dishwasher repair guides.
SYMPTOM_SOURCE = "https://www.ifixit.com/Device/Dishwasher"
SYMPTOM_FIXES = {
    "not_draining": [
        "Clean the bottom filter / coin trap.",
        "Check the drain hose for kinks and the disposal knockout plug.",
        "Run the sink disposal to clear shared-line clogs.",
    ],
    "dishes_not_clean": [
        "Clear and rinse the spray-arm nozzles.",
        "Use fresh detergent + rinse aid; don't overload or block the arms.",
        "Run a hot cycle with a dishwasher cleaner to clear scale/grease.",
    ],
    "wont_start": [
        "Confirm the door latches fully and Control Lock (CL) is off.",
        "Check the cycle isn't in Delay Start; confirm the breaker.",
        "Confirm the water supply valve is on.",
    ],
    "leaking": [
        "Stop the cycle and turn off the water supply.",
        "Check the door gasket for food debris; if it recurs, book service.",
    ],
    "not_drying": [
        "Add/refill rinse aid.",
        "Select the heat-dry / extra-dry option; open the door at cycle end.",
    ],
}

# Ordered (key, required-keywords) rules for the keyword fallback matcher. First match wins.
_SYMPTOM_KEYWORDS = [
    ("not_draining", ("not drain", "won't drain", "wont drain", "standing water", "water in the bottom", "draining")),
    ("dishes_not_clean", ("not clean", "dirty", "not washing", "film", "spots", "residue", "gritty")),
    ("not_drying", ("not dry", "wet dishes", "won't dry", "wont dry", "drying")),
    ("leaking", ("leak", "leaking", "water on the floor", "puddle")),
    ("wont_start", ("won't start", "wont start", "not starting", "won't turn on", "wont turn on", "dead")),
]


def match_symptom_key(symptom):
    """Map a free-text dishwasher symptom to a SYMPTOM_FIXES key, or None. Pure keyword heuristics."""
    s = (symptom or "").lower()
    for key, kws in _SYMPTOM_KEYWORDS:
        if any(k in s for k in kws):
            return key
    return None


# Safety rules: action classes the agent must REFUSE and escalate (defense-in-depth with safety.py).
SAFETY_RULES = [
    "Never advise opening the heating element / heater circuit (HE/tE) - escalate.",
    "Never advise mains-voltage, motor-winding, or control-board electrical work (LE/CE/nE).",
    "Never advise working on water lines under pressure - have the user shut the supply off first.",
    "Treat any standing-water + electrical situation as escalate-now (AE/E1/FE).",
    "Never advise defeating the door interlock to run the unit with the door open.",
]

# ~3-5 targeted corrections: nuances the model commonly gets wrong. Used in the persona/prompt.
CORRECTIONS = [
    {"id": "lg_cl_not_fault", "when": "an LG dishwasher shows CL",
     "correct": "CL is Child/Control Lock, not a fault - hold RINSE+SPRAY 3 s to unlock."},
    {"id": "lg_bE_is_suds", "when": "an LG dishwasher shows bE",
     "correct": "bE is a suds/detergent (or not-level) error, NOT a lock code - switch to dishwasher detergent and level the unit."},
    {"id": "lg_oe_install", "when": "OE appears on the first cycle after install",
     "correct": "Suspect the drain-hose height/kink or a left-in disposal knockout plug, not a pump failure."},
    {"id": "out_of_table_code", "when": "a code is not in this table",
     "correct": "Do NOT guess its meaning; point the user to that exact code on the LG support page / manual."},
]

# Clarifying-question hints when intake info is missing.
CLARIFYING_HINTS = {
    "appliance": "Is it a dishwasher? Front-control or top-control?",
    "brand": "What brand is on the door or the inner-door spec plate?",
    "model_number": "Read the model number off the plate on the inner door edge (e.g. LDFC2423V).",
    "symptom": "What is it doing - not draining, not cleaning, not starting, or leaking?",
    "error_code": "Is a code blinking on the panel (IE, OE, FE, LE/CE, tE, HE, AE/E1, nE, bE, CL, PF)?",
}

# Per-appliance inspection-shot hints for the escalation video guide.
# fault_class -> ordered shot hints. 'default' is the generic fallback list.
INSPECTION_SHOTS = {
    "default": [
        {"what_to_film": "The spec / model plate", "where": "Inner door edge", "narration": "Read out the model number."},
        {"what_to_film": "The control panel / any code", "where": "Front or top control panel", "narration": "Show any code on the display."},
        {"what_to_film": "The symptom area", "where": "Tub, floor, or racks", "narration": "Show what is wrong (water, dirty dishes)."},
        {"what_to_film": "Narrate the problem and steps tried", "where": "Standing at the dishwasher", "narration": "Say the symptom and what you already tried."},
    ],
    "drain": [
        {"what_to_film": "The spec / model plate", "where": "Inner door edge", "narration": "Read out the model number."},
        {"what_to_film": "The bottom filter / coin trap", "where": "Bottom of the tub", "narration": "Show the filter and any debris."},
        {"what_to_film": "The drain hose path", "where": "Under the sink", "narration": "Show the hose routing and disposal connection."},
        {"what_to_film": "Narrate the problem and steps tried", "where": "Standing at the dishwasher", "narration": "Say the symptom and what you already tried."},
    ],
    "leak": [
        {"what_to_film": "The spec / model plate", "where": "Inner door edge", "narration": "Read out the model number."},
        {"what_to_film": "The base/floor under the unit", "where": "Front kick-plate area", "narration": "Show where the water is coming from."},
        {"what_to_film": "The door gasket", "where": "Around the door", "narration": "Show the gasket and any debris or damage."},
        {"what_to_film": "Narrate the problem and steps tried", "where": "Standing at the dishwasher", "narration": "Say the symptom and what you already tried."},
    ],
    "motor": [
        {"what_to_film": "The spec / model plate", "where": "Inner door edge", "narration": "Read out the model number."},
        {"what_to_film": "The sump / spray arms", "where": "Bottom of the tub", "narration": "Show the spray arms and sump area."},
        {"what_to_film": "The control panel code", "where": "Front or top control panel", "narration": "Show the code on the display."},
        {"what_to_film": "Narrate the problem and steps tried", "where": "Standing at the dishwasher", "narration": "Say the symptom and what you already tried."},
    ],
}

# Manual reference record (see fridge.py MANUALS). LG documents dishwasher codes on support pages
# rather than a manual page number, so `pages` is empty and `error_code_url` carries the citation.
MANUALS = {
    "LG": {
        "LDFC2423V": {
            "product_line": "LG Front-Control Dishwasher w/ QuadWash (LDFC2423V.APZEEUS)",
            "manual_url": "https://www.lg.com/us/support/product-help/LDFC2423V.APZEEUS",
            "error_code_url": _LG_LIST,
            "revision": "Owner's Manual 2023-09-11 (LG support, verified 2026-06-26)",
            "retrieved_at": "2026-06-26",
            "warranty_note": "1 yr parts/labor; 10 yr direct-drive motor (verify per unit).",
            "recalls": [],
            "pages": {},
        },
    },
}

# No brand-specific escalation steps yet; all brands fall back to the generic default
# (projections.DEFAULT_ESCALATION_STEPS). Add brand keys here as technician requirements are learned.
ESCALATION_STEPS = {}
