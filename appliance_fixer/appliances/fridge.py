"""Curated database of troubleshooting steps and error codes for refrigerators."""
from __future__ import annotations

# Map of common refrigerator symptoms to ranked, safety-approved fixes
SYMPTOM_FIXES = {
    "fresh-food warm, freezer fine": [
        "Check if the evaporator fan in the freezer is spinning (listen for it or check for cold airflow).",
        "Inspect the evaporator coils behind the freezer back panel for heavy frost buildup (indicates a defrost system failure).",
        "Verify that vents between the freezer and fridge compartments are not blocked by food items."
    ],
    "both compartments warm, compressor running": [
        "Unplug the refrigerator and vacuum dust/debris from the condenser coils (typically located underneath or behind the unit).",
        "Check if the condenser fan motor next to the compressor is spinning freely.",
        "Inspect the start relay attached to the side of the compressor."
    ],
    "runs constantly, never cycles off": [
        "Unplug the refrigerator and clean the condenser coils.",
        "Perform a dollar-bill test on the door gaskets to check for seal leaks.",
        "Ensure there is at least 2 inches of clearance around the refrigerator vents and it is not overpacked."
    ],
    "water pooling under the crisper drawers": [
        "Locate the defrost drain hole (usually under the evaporator coils in the freezer) and flush it with warm water and a turkey baster to clear clogs.",
        "Inspect the water filter housing and water lines for slow leaks."
    ],
    "ice maker stopped": [
        "Check the ice maker fill tube for ice blockage (use a hair dryer on low to thaw if frozen) and verify water supply is on.",
        "Test the water inlet valve at the bottom rear of the refrigerator.",
        "Check if the ice maker arm is in the down (active) position."
    ],
    "frost building up in the freezer": [
        "Inspect the door gasket for tears or gaps, and verify the door closes completely.",
        "Test the defrost heater and defrost thermostat for continuity."
    ],
    "fridge warm after a frost-up, fan buzzing": [
        "Unplug the refrigerator and allow it to manual-defrost (24-48 hours with doors open) to clear ice blocking the evaporator fan.",
        "Inspect the evaporator fan blades for physical damage."
    ]
}

# Map of brand-specific error codes to meaning and troubleshooting advice
ERROR_CODES = {
    "WHIRLPOOL": {
        "PF": {
            "meaning": "Power Failure",
            "fixes": [
                "Dismiss the PF code by pressing any button on the display panel.",
                "Verify the refrigerator temperature is recovering."
            ]
        }
    },
    "LG": {
        "OE": {
            "meaning": "Drain Error (typically washer, but matches diagnostic scope)",
            "fixes": [
                "Check the drain hose for kinks or blockages.",
                "Clean the drain pump filter / coin trap at the bottom of the unit."
            ]
        }
    },
    "SAMSUNG": {
        "OF OF": {
            "meaning": "Demo/Showroom Mode",
            "fixes": [
                "Press and hold the Power Freeze and Freezer buttons simultaneously for 3-5 seconds to exit Demo mode."
            ]
        }
    }
}
