"""get_fixes: curated-first fix lookup with optional grounding and case caching."""
from __future__ import annotations

from home_rescue.appliances import module_for


# Sentinel: get_fixes(..., symptom_key=_UNSET) means "no override -> use the keyword matcher".
_UNSET = object()


def error_code_meaning(brand, error_code, appliance=None):
    """Return the curated meaning string for a brand error code, or None if out-of-table."""
    if not brand or not error_code:
        return None
    table = module_for(appliance).ERROR_CODES.get(brand.upper(), {})
    entry = _lookup_error_code(table, error_code)
    return entry["meaning"] if entry else None


def _lookup_error_code(table, error_code):
    """Return an ERROR_CODES entry using a case-insensitive code match."""
    code = (error_code or "").strip()
    entry = table.get(code)
    if entry is not None:
        return entry
    code_u = code.upper()
    for key, value in table.items():
        if key.upper() == code_u:
            return value
    return None


def _manual_lookup_key(model_number):
    """Normalize a model number for a MANUALS lookup (uppercase, strip, drop a region suffix)."""
    s = (model_number or "").upper().strip()
    if "/" in s:
        s = s.split("/", 1)[0].strip()
    return s


def get_manual(appliance, brand, model_number):
    """Return the curated manual-reference record for a model, or None if not curated.

    Backs the out-of-table cited fallback (and, later, the MCP get_manual tool). Tries an exact
    brand+model match, then a loose containment match for trailing revision letters.
    """
    if not brand:
        return None
    manuals = getattr(module_for(appliance), "MANUALS", {})
    by_brand = manuals.get(brand.upper(), {})
    if not by_brand:
        return None
    key = _manual_lookup_key(model_number)
    if key and key in by_brand:
        return by_brand[key]
    for m, rec in by_brand.items():
        mk = _manual_lookup_key(m)
        if key and (key == mk or key in mk or mk in key):
            return rec
    return None


def has_error_code_data(appliance, brand, model_number=None):
    """Return True when a known error/fault code would meaningfully change the fix for this
    brand/model -- i.e. there is curated error-code data to act on.

    True when the brand has any curated ERROR_CODES entries, OR the model's curated manual
    carries an error-code reference (a service/error-code page or a manufacturer code URL).
    Used to decide whether the agent should ask the user to read a code off the display before
    falling back to symptom-only fixes.
    """
    if not brand:
        return False
    mod = module_for(appliance)
    if getattr(mod, "ERROR_CODES", {}).get(brand.upper()):
        return True
    manual = get_manual(appliance, brand, model_number)
    if manual:
        pages = manual.get("pages") or {}
        if manual.get("error_code_url") or pages.get("service_error_codes") or pages.get("error_codes"):
            return True
    return False


def _manual_reference_step(error_code, brand, manual):
    """Build ONE 'look it up' fix step that CITES the manual, never guessing the code's meaning.

    Always mentions the owner's/service manual so the out-of-table path stays clearly a manual
    reference. Uses a service-manual page number when curated, else the manufacturer code URL.
    """
    pages = (manual or {}).get("pages") or {}
    page = pages.get("service_error_codes") or pages.get("error_codes")
    url = (manual or {}).get("error_code_url") or (manual or {}).get("manual_url")
    if manual and page and url:
        where = f"on p.{page} of the service manual ({url})"
    elif manual and page:
        where = f"on p.{page} of the service manual"
    elif manual and url:
        where = f"in your manual / the manufacturer code reference: {url}"
    else:
        where = f"for your {brand or 'appliance'} in the owner's manual"
    return {
        "instruction": f"Look up error code '{error_code}' {where} and follow that exact step; do not assume its meaning.",
        "safe": True,
        "source": "manual",
        "citation": url,
    }


def _match_fridge_symptom_key(symptom: str):
    """Map a free-text fridge symptom to a SYMPTOM_FIXES key, or None. Pure keyword heuristics."""
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


def _match_symptom_key(symptom: str, appliance=None):
    """Map free-text symptom to the appliance module's SYMPTOM_FIXES key, or None.

    Delegates to the module's own keyword matcher when it defines one (e.g. dishwasher);
    the fridge module uses the built-in heuristics below for backward compatibility.
    """
    matcher = getattr(module_for(appliance), "match_symptom_key", None)
    if matcher is not None:
        return matcher(symptom)
    return _match_fridge_symptom_key(symptom)


def get_fixes(appliance, brand, model_number, symptom, error_code=None, *, use_grounding=False, store=None, case_id=None, symptom_key=_UNSET):
    """Return an ordered list of fix dicts: {instruction, safe, source, citation}.

    `source` is the provenance CATEGORY ('error_code' | 'manual' | 'curated' | 'fallback');
    `citation` is the authoritative URL the row was distilled from, or None when the row carries
    no per-step citation (the model's overall manual is returned separately by lookup_fixes).

    Order of resolution:
      1. If a store+case_id are given and case.data.cache.grounded_fixes exists, return it (cache hit).
      2. If error_code is in the curated table -> its ranked fixes (source 'error_code').
      3. Else if error_code is given but NOT in the table -> a single cited 'look it up in the manual'
         step (source 'manual'); never guess the meaning.
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

    mod = module_for(appliance)
    brand_u = (brand or "").upper()
    fixes = []

    # 2/3. error-code path
    if error_code:
        table = mod.ERROR_CODES.get(brand_u, {})
        entry = _lookup_error_code(table, error_code)
        if entry:
            citation = entry.get("source")
            fixes = [{"instruction": f, "safe": entry["safe"], "source": "error_code", "citation": citation} for f in entry["fixes"]]
        else:
            fixes = [_manual_reference_step(error_code, brand, get_manual(appliance, brand, model_number))]
    else:
        # 4. symptom path. The live agent's lookup_fixes may pass an explicit symptom_key resolved
        # by the schema router (symptom_router.classify_symptom). When it does NOT (the default, and
        # every pure/test caller), fall back to the keyword matcher -- keeping this function pure and
        # existing behavior unchanged.
        key = _match_symptom_key(symptom, appliance) if symptom_key is _UNSET else symptom_key
        # Guard `key in SYMPTOM_FIXES`: an explicit symptom_key override may be a bucket from a
        # different appliance (the schema router is fridge-only), which would KeyError here. An
        # unknown key degrades to the safe fallback rather than crashing.
        if key and key in mod.SYMPTOM_FIXES:
            # Symptom fixes are distilled from the module's SYMPTOM_SOURCE (iFixit/RepairClinic
            # repair guides); the model's overall manual is also returned alongside by lookup_fixes.
            symptom_citation = getattr(mod, "SYMPTOM_SOURCE", None)
            fixes = [{"instruction": f, "safe": True, "source": "curated", "citation": symptom_citation} for f in mod.SYMPTOM_FIXES[key]]
        else:
            # 5. fallback
            fixes = [
                {"instruction": "Unplug the appliance for 5 minutes to reset the control board.", "safe": True, "source": "fallback", "citation": None},
                {"instruction": "Confirm the outlet has power and the breaker is not tripped.", "safe": True, "source": "fallback", "citation": None},
                {"instruction": "Check that vents are clear and the doors seal fully.", "safe": True, "source": "fallback", "citation": None},
            ]

    # cache write
    if store is not None and case_id is not None:
        case = store.load_case(case_id)
        if case is not None:
            cache = dict((case.get("data") or {}).get("cache", {}))
            cache["grounded_fixes"] = fixes
            store.save_case(case_id, cache=cache)

    return fixes


def get_inspection_shots(fault_class=None, appliance=None):
    """Return the ordered inspection-shot hint list for a fault class, defaulting to 'default'."""
    shots = module_for(appliance).INSPECTION_SHOTS
    return shots.get(fault_class or "default", shots["default"])


# Generic, appliance-agnostic escalation-prep steps. Single source of truth shared by the app
# escalation flow (escalation.py) and the mock OEM MCP server (mcp_server/projections.py) so they
# can never drift. `kind` is one of: check, action, wait, call.
DEFAULT_ESCALATION_STEPS = [
    {"order": 1, "instruction": "Check that the appliance is plugged in and the outlet has power.", "kind": "check"},
    {"order": 2, "instruction": "Find the model and serial number on the spec plate and have them ready.", "kind": "check"},
    {"order": 3, "instruction": "Note the symptom and any error code shown on the display.", "kind": "action"},
    {"order": 4, "instruction": "Call support to schedule a technician if the issue still is not resolved.", "kind": "call"},
]


def get_escalation_steps(appliance=None, brand=None):
    """Return the ordered escalation-prep step list for an (appliance, brand).

    An appliance module may publish brand-specific steps in ESCALATION_STEPS (keyed by uppercase
    brand); otherwise the appliance-agnostic DEFAULT_ESCALATION_STEPS apply. Steps are copied so
    callers cannot mutate the curated data.
    """
    by_brand = getattr(module_for(appliance), "ESCALATION_STEPS", {}) or {}
    steps = by_brand.get(brand.upper()) if brand else None
    return [dict(s) for s in (steps or DEFAULT_ESCALATION_STEPS)]
