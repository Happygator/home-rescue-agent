"""Grounding: matches symptoms and error codes against curated fixes."""
from __future__ import annotations

from appliance_fixer.appliances.fridge import SYMPTOM_FIXES, ERROR_CODES


def get_fixes(
    appliance_type: str,
    brand: str,
    model_number: str,
    symptom: str,
    error_code: str | None = None,
) -> list[str]:
    """Look up troubleshooting steps based on symptoms, brand, and error codes.

    Checks the curated database first, with fallback options.
    """
    fixes = []
    brand_upper = brand.upper() if brand else ""
    symptom_lower = symptom.lower() if symptom else ""

    # 1. Check brand-specific error codes first
    if error_code and brand_upper in ERROR_CODES:
        ec_upper = error_code.upper()
        if ec_upper in ERROR_CODES[brand_upper]:
            fixes.extend(ERROR_CODES[brand_upper][ec_upper]["fixes"])
            return fixes

    # 2. Fuzzy match symptom text against curated fixes
    matched_key = None
    if "warm" in symptom_lower and ("freezer fine" in symptom_lower or "freezer is still" in symptom_lower or "freezer ok" in symptom_lower or "freezer works" in symptom_lower):
        matched_key = "fresh-food warm, freezer fine"
    elif "warm" in symptom_lower and "compressor" in symptom_lower:
        matched_key = "both compartments warm, compressor running"
    elif "constantly" in symptom_lower or "24/7" in symptom_lower or "never shut off" in symptom_lower:
        matched_key = "runs constantly, never cycles off"
    elif "water pooling" in symptom_lower or "puddle" in symptom_lower or "crisper" in symptom_lower:
        matched_key = "water pooling under the crisper drawers"
    elif "ice maker" in symptom_lower or "making ice" in symptom_lower:
        matched_key = "ice maker stopped"
    elif "frost" in symptom_lower and "freezer" in symptom_lower:
        matched_key = "frost building up in the freezer"
    elif "buzzing" in symptom_lower or "rattling" in symptom_lower or "fan hitting ice" in symptom_lower:
        matched_key = "fridge warm after a frost-up, fan buzzing"

    if matched_key and matched_key in SYMPTOM_FIXES:
        fixes.extend(SYMPTOM_FIXES[matched_key])
        return fixes

    # 3. Fallback: general diagnostic recommendations
    if "drain" in symptom_lower or "water" in symptom_lower or "leak" in symptom_lower:
        return [
            "Check for clogged drain hose or filter.",
            "Verify all water connections and gaskets are secure."
        ]
    
    return [
        "Unplug the appliance for 5 minutes to reset the control board.",
        "Check that the power outlet has voltage and the circuit breaker is not tripped.",
        "Verify that vents are clear and doors/lids are sealing properly."
    ]
