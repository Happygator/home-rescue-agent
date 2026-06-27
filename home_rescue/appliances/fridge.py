from __future__ import annotations

APPLIANCE = "refrigerator"

# Supported model numbers per brand (normalized, uppercase). Used by validate_model (B3).
SUPPORTED_MODELS = {
    "SAMSUNG": ["RF28T5001SR", "RF28R7201", "RSG257", "RF263"],
    "GE": ["GSS25"],
    "WHIRLPOOL": ["WRS555", "WRFF3336SZ", "WRX735SDHZ"],
    "MAYTAG": ["MFI257"],
    "LG": ["LFXS26973S", "LFXS26"],
    "FRIGIDAIRE": ["FFHB2750"],
    "KITCHENAID": ["KDTM354"],
    "BOSCH": ["B36CL80SNS"],
}

# Per-brand model-number regex (loose; catches malformed reads before membership check).
MODEL_PATTERNS = {
    "SAMSUNG": r"^R[FS][A-Z0-9]{3,}",
    "GE": r"^G[A-Z]{2}\d{2,}",
    "WHIRLPOOL": r"^W[A-Z]{2}[A-Z0-9]{3,}",
    "MAYTAG": r"^M[A-Z]{2}\d{2,}",
    "LG": r"^L[A-Z]{2}[A-Z0-9]{3,}",
    "FRIGIDAIRE": r"^F[A-Z]{3}\d{3,}",
    "KITCHENAID": r"^K[A-Z]{2}[A-Z0-9]{3,}",
    "BOSCH": r"^B\d{2}[A-Z0-9]{3,}",
}

# Per-brand support contact (email + phone + display name) for escalation drafting (B7).
SUPPORT_CONTACTS = {
    "SAMSUNG": {"name": "Samsung", "email": "support@samsung.com", "phone": "1-800-726-7864"},
    "GE": {"name": "GE Appliances", "email": "support@geappliances.com", "phone": "1-800-432-2737"},
    "WHIRLPOOL": {"name": "Whirlpool", "email": "support@whirlpool.com", "phone": "1-866-698-2538"},
    "MAYTAG": {"name": "Maytag", "email": "support@maytag.com", "phone": "1-800-344-1274"},
    "LG": {"name": "LG", "email": "support@lg.com", "phone": "1-800-243-0000"},
    "FRIGIDAIRE": {"name": "Frigidaire", "email": "support@frigidaire.com", "phone": "1-800-374-4432"},
    "KITCHENAID": {"name": "KitchenAid", "email": "support@kitchenaid.com", "phone": "1-800-422-1230"},
    "BOSCH": {"name": "Bosch", "email": "support@bosch-home.com", "phone": "1-800-944-2904"},
}
DEFAULT_SUPPORT_CONTACT = {"name": "Appliance Service", "email": "support@appliance-repair.com", "phone": "1-800-000-0000"}

# Brand-specific error codes -> meaning + ranked fixes + whether the action class is DIY-safe.
# An out-of-table code must NEVER be guessed (grounding returns a 'check your manual' step).
ERROR_CODES = {
    "WHIRLPOOL": {
        "PF": {"meaning": "Power Failure (not a fault)", "safe": True, "fixes": [
            "Press any button on the display to dismiss the PF code.",
            "Confirm the refrigerator temperature is recovering over the next few hours.",
        ]},
    },
    "LG": {
        "OE": {"meaning": "Drain Error", "safe": True, "fixes": [
            "Check the drain hose for kinks or blockages.",
            "Clean the drain-pump filter / coin trap at the bottom of the unit.",
        ]},
    },
    "SAMSUNG": {
        "OF OF": {"meaning": "Demo / Showroom Mode (cooling disabled)", "safe": True, "fixes": [
            "Press and hold Power Freeze and Freezer (or Energy Saver) together for 3-5 seconds to exit Demo mode.",
        ], "source": "https://www.samsung.com/us/support/troubleshooting/TSG01201784/"},
        "OFF": {"meaning": "Demo / Showroom Mode (cooling disabled)", "safe": True, "fixes": [
            "Press and hold Power Freeze and Freezer together for 3-5 seconds to exit Demo mode.",
        ], "source": "https://www.samsung.com/us/support/troubleshooting/TSG01201784/"},
    },
    # NOTE: WHIRLPOOL "PF" and LG "OE" above predate the source convention and are left uncited:
    # on Whirlpool refrigerators the power-interruption code is actually "PO" (PF is a laundry code),
    # and LG refrigerator "OE" is questionable (OE is an LG dishwasher drain code). Verify/correct
    # before adding a source. Their fixes still fall back to the model's overall manual reference.
}

# Symptom key -> ranked, safety-approved fixes (easiest/safest first). Grounded in iFixit/RepairClinic.
# Citation for the symptom path: the curated buckets are distilled from these refrigerator repair guides.
SYMPTOM_SOURCE = "https://www.ifixit.com/Device/Refrigerator"
SYMPTOM_FIXES = {
    "fresh_food_warm_freezer_fine": [
        "Listen for the evaporator fan in the freezer; confirm it is spinning and you feel cold airflow.",
        "Check the evaporator coils behind the freezer back panel for heavy frost (a defrost-system fault).",
        "Make sure the vents between the freezer and fridge compartments are not blocked by food.",
    ],
    "both_warm_compressor_running": [
        "Unplug the fridge and vacuum dust off the condenser coils (underneath or behind the unit).",
        "Check that the condenser fan near the compressor spins freely.",
        "Inspect the compressor start relay on the side of the compressor.",
    ],
    "runs_constantly": [
        "Unplug and clean the condenser coils.",
        "Do a dollar-bill test on the door gaskets to check the seal.",
        "Leave 2 inches of clearance around the vents and avoid overpacking.",
    ],
    "water_pooling_crisper": [
        "Flush the defrost drain hole (under the evaporator coils) with warm water to clear a clog.",
        "Inspect the water-filter housing and lines for slow leaks.",
    ],
    "ice_maker_stopped": [
        "Check the fill tube for ice and confirm the water supply / shutoff valve is on.",
        "Test the water inlet valve at the lower rear of the fridge.",
        "Confirm the ice-maker arm is in the down (active) position.",
    ],
    "freezer_frosting": [
        "Inspect the door gasket for tears and confirm the door closes fully.",
        "Test the defrost heater and defrost thermostat for continuity.",
    ],
    "warm_with_buzzing": [
        "Unplug and manual-defrost (doors open 24-48h) to clear ice blocking the evaporator fan.",
        "Inspect the evaporator fan blades for damage.",
    ],
}

# Safety rules: action classes the agent must REFUSE and escalate (defense-in-depth with safety.py).
SAFETY_RULES = [
    "Never advise gas-line, burner, igniter, or pilot-light work.",
    "Never advise mains-voltage / live-wire / capacitor / heating-element electrical work.",
    "Never advise opening or charging the sealed refrigerant system (compressor, refrigerant, freon).",
    "Never advise handling water that is leaking onto live electrical components.",
]

# ~3-5 targeted corrections: nuances the model commonly gets wrong. Used in the persona/prompt.
CORRECTIONS = [
    {"id": "F2_coils_vs_seal", "when": "both compartments warm and the compressor is running",
     "correct": "Start with the CONDENSER coils/fan (heat rejection), not the door seal; a seal leak rarely warms the whole box."},
    {"id": "F8_evap_vs_condenser", "when": "fridge warm with buzzing/rattling from the back of the freezer",
     "correct": "Suspect the EVAPORATOR fan hitting ice (defrost fault), not the condenser fan."},
    {"id": "samsung_of_of_demo", "when": "a Samsung fridge shows 'OF OF' or 'OFF' and will not cool",
     "correct": "This is Demo/Showroom mode, not a hardware fault; exit demo mode before any other step."},
    {"id": "out_of_table_code", "when": "an error code is not in the curated table",
     "correct": "Do NOT guess its meaning; tell the user to check that exact code in their manual."},
]

# Clarifying-question hints when intake info is missing.
CLARIFYING_HINTS = {
    "appliance": "Is it a refrigerator, and is it a top-freezer, bottom-freezer, side-by-side, or French-door?",
    "brand": "What brand is on the door or the spec plate?",
    "model_number": "Can you read the model number off the spec plate (often inside on a side wall)?",
    "symptom": "What exactly is it doing, and is the freezer side also affected?",
    "error_code": "Is any code or light showing on the display?",
}

# Per-appliance inspection-shot hints for the escalation video guide (B7).
# fault_class -> ordered shot hints. 'default' is the generic fallback list.
INSPECTION_SHOTS = {
    "default": [
        {"what_to_film": "The spec / model plate", "where": "Inside the fridge on a side wall", "narration": "Read out the model number."},
        {"what_to_film": "The temperature display / control panel", "where": "Front control panel or door", "narration": "Show any code or the set temperatures."},
        {"what_to_film": "The symptom area", "where": "Fresh-food or freezer compartment", "narration": "Show what is wrong (warm food, frost, water)."},
        {"what_to_film": "Narrate the problem and steps tried", "where": "Standing at the fridge", "narration": "Say the symptom and what you already tried."},
    ],
    "airflow_defrost": [
        {"what_to_film": "The spec / model plate", "where": "Inside the fridge on a side wall", "narration": "Read out the model number."},
        {"what_to_film": "The freezer back panel / evaporator area", "where": "Freezer compartment, back panel", "narration": "Show frost buildup on the back panel."},
        {"what_to_film": "The temperature display", "where": "Front control panel", "narration": "Show the fridge and freezer temperatures."},
        {"what_to_film": "Narrate the problem and steps tried", "where": "Standing at the fridge", "narration": "Say the symptom and what you already tried."},
    ],
    "sealed_system": [
        {"what_to_film": "The spec / model plate", "where": "Inside the fridge on a side wall", "narration": "Read out the model number."},
        {"what_to_film": "The compressor and start relay", "where": "Lower rear access panel", "narration": "Capture any clicking sound near the compressor."},
        {"what_to_film": "The condenser coils", "where": "Underneath or behind the unit", "narration": "Show the coils and condenser fan."},
        {"what_to_film": "Narrate the problem and steps tried", "where": "Standing at the fridge", "narration": "Say the symptom and what you already tried."},
    ],
}

# Manual reference records: a citation + distilled page map (NOT the PDF text). Back get_manual()
# and the out-of-table cited fallback. Verified 2026-06-25 (see docs/MANUAL_GROUNDING_DESIGN.md).
MANUALS = {
    "SAMSUNG": {
        "RF28T5001SR": {
            "product_line": "36-inch French-Door Refrigerator (28 cu. ft.)",
            "manual_url": "https://www.manualslib.com/manual/2671356/Samsung-Rf28t5001.html",
            "manual_url_variant": "https://www.manualslib.com/manual/2725689/Samsung-Rf28t5001sr-Aa.html",
            "revision": "User Manual (ManualsLib doc 2671356), verified 2026-06-25",
            "retrieved_at": "2026-06-25",
            "warranty_note": "1 yr parts/labor; 10 yr digital inverter compressor (verify per unit).",
            "recalls": [],
            # Consumer manual is symptom-based (p.57 troubleshooting, p.61 abnormal sounds); the
            # numeric C-code TABLE is in the separate service manual (p.63 self-diagnostic, p.65 codes).
            "pages": {"user_troubleshooting": 57, "user_abnormal_sounds": 61,
                      "service_self_diagnostic": 63, "service_error_codes": 65},
        },
    },
}

# Brand-specific escalation-prep steps the customer completes before a technician handoff. Brands not
# listed here fall back to projections.DEFAULT_ESCALATION_STEPS. `kind`: check | action | wait | call.
ESCALATION_STEPS = {
    "SAMSUNG": [
        {"order": 1, "instruction": "Check the interior light - confirm it turns on when you open the door.", "kind": "check"},
        {"order": 2, "instruction": "Check the door - make sure it closes and seals completely.", "kind": "check"},
        {"order": 3, "instruction": "Reset the fridge: turn it off (unplug it or switch off its breaker), wait a moment, then turn it back on.", "kind": "action"},
        {"order": 4, "instruction": "Wait 2 hours for the fridge to recover. If it still is not working, call support.", "kind": "wait", "wait_hours": 2},
    ],
}
