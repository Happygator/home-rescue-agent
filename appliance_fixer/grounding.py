"""get_fixes: curated-first fix lookup with optional grounding and case caching."""
from __future__ import annotations

from appliance_fixer.appliances import fridge


def error_code_meaning(brand, error_code):
    """Return the curated meaning string for a brand error code, or None if out-of-table."""
    if not brand or not error_code:
        return None
    table = fridge.ERROR_CODES.get(brand.upper(), {})
    entry = table.get(error_code.upper().strip())
    return entry["meaning"] if entry else None


def _match_symptom_key(symptom: str):
    """Map free-text symptom to a SYMPTOM_FIXES key, or None. Pure keyword heuristics."""
    s = (symptom or "").lower()
    if "warm" in s and any(w in s for w in ("freezer fine", "freezer is still", "freezer ok", "freezer works", "freezer cold", "freezer still cold")):
        return "fresh_food_warm_freezer_fine"
    if "warm" in s and ("buzz" in s or "rattl" in s):
        return "warm_with_buzzing"
    if "warm" in s and "compressor" in s:
        return "both_warm_compressor_running"
    if any(w in s for w in ("constantly", "24/7", "never shut", "never cycles", "runs all")):
        return "runs_constantly"
    if "pool" in s or "puddle" in s or "crisper" in s:
        return "water_pooling_crisper"
    if "ice maker" in s or "making ice" in s or "no ice" in s:
        return "ice_maker_stopped"
    if "frost" in s and "freezer" in s:
        return "freezer_frosting"
    return None


def get_fixes(appliance, brand, model_number, symptom, error_code=None, *, use_grounding=False, store=None, case_id=None):
    """Return an ordered list of fix dicts: {instruction, safe, source}.

    Order of resolution:
      1. If a store+case_id are given and case.data.cache.grounded_fixes exists, return it (cache hit).
      2. If error_code is in the curated table -> its ranked fixes (source 'error_code').
      3. Else if error_code is given but NOT in the table -> a single 'check your manual' step
         (source 'manual'); never guess.
      4. Else if the symptom matches a curated key -> those ranked fixes (source 'curated').
      5. Else -> a safe generic fallback list (source 'fallback').
    `use_grounding` is accepted for forward-compat (iFixit/Search) but defaults False and is a
    no-op here. When a store+case_id are given, the computed list is cached into
    case.data.cache.grounded_fixes before returning.
    """
    # 1. cache hit
    if store is not None and case_id is not None:
        case = store.load_case(case_id)
        if case is not None:
            cached = (case.get("data") or {}).get("cache", {}).get("grounded_fixes")
            if cached:
                return cached

    brand_u = (brand or "").upper()
    fixes = []

    # 2/3. error-code path
    if error_code:
        code = error_code.upper().strip()
        table = fridge.ERROR_CODES.get(brand_u, {})
        if code in table:
            fixes = [{"instruction": f, "safe": table[code]["safe"], "source": "error_code"} for f in table[code]["fixes"]]
        else:
            fixes = [{"instruction": f"Check what error code '{error_code}' means for your {brand or 'appliance'} in the owner's manual; do not assume.", "safe": True, "source": "manual"}]
    else:
        # 4. symptom path
        key = _match_symptom_key(symptom)
        if key:
            fixes = [{"instruction": f, "safe": True, "source": "curated"} for f in fridge.SYMPTOM_FIXES[key]]
        else:
            # 5. fallback
            fixes = [
                {"instruction": "Unplug the appliance for 5 minutes to reset the control board.", "safe": True, "source": "fallback"},
                {"instruction": "Confirm the outlet has power and the breaker is not tripped.", "safe": True, "source": "fallback"},
                {"instruction": "Check that vents are clear and the doors seal fully.", "safe": True, "source": "fallback"},
            ]

    # cache write
    if store is not None and case_id is not None:
        case = store.load_case(case_id)
        if case is not None:
            cache = dict((case.get("data") or {}).get("cache", {}))
            cache["grounded_fixes"] = fixes
            store.save_case(case_id, cache=cache)

    return fixes


def get_inspection_shots(fault_class=None):
    """Return the ordered inspection-shot hint list for a fault class, defaulting to 'default'."""
    return fridge.INSPECTION_SHOTS.get(fault_class or "default", fridge.INSPECTION_SHOTS["default"])
