"""Pure, deterministic projections of the curated appliance modules into the manufacturer (OEM)
tool surface: get_manual / get_pre_service_workflow / create_service_request.

No network, no model, no mcp dependency. The MCP server (server.py) and the fixture generator both
call these, so the curated KB and the mock server can never drift. 'Populating the mock MCP server'
== authoring the appliance modules; this file is the thin adapter.
"""
from __future__ import annotations

import hashlib

from home_rescue.appliances import REGISTRY
from home_rescue.grounding import (
    DEFAULT_ESCALATION_STEPS,
    get_escalation_steps as _curated_escalation_steps,
    get_fixes,
    get_manual as _curated_manual,
)
from home_rescue.tools import canonicalize_symbols, normalize_model


def _resolve(model):
    """Resolve a model number to (appliance, brand) by scanning the registry, or (None, None)."""
    if not model:
        return (None, None)
    canon = canonicalize_symbols(normalize_model(model))
    if not canon:
        return (None, None)
    for appliance, mod in REGISTRY.items():
        for brand, models in getattr(mod, "SUPPORTED_MODELS", {}).items():
            for m in models:
                cm = canonicalize_symbols(normalize_model(m))
                if canon == cm or canon in cm or cm in canon:
                    return (appliance, brand)
    return (None, None)


def get_manual(model):
    """OEM tool: product line, manual_url, warranty status, recalls for a model (section 16 shape)."""
    appliance, brand = _resolve(model)
    rec = _curated_manual(appliance, brand, model) if brand else None
    if not rec:
        return {"found": False, "model": model}
    return {
        "found": True,
        "model": model,
        "brand": brand,
        "appliance": appliance,
        "product_line": rec.get("product_line"),
        "manual_url": rec.get("manual_url"),
        "error_code_url": rec.get("error_code_url"),
        "pages": rec.get("pages") or {},
        "warranty_status": rec.get("warranty_status") or "unknown",
        "recalls": rec.get("recalls") or [],
    }


def get_pre_service_workflow(model, symptom="", error_code=""):
    """OEM tool: ordered sanctioned pre-dispatch steps + terminal dispatch_recommended (section 16).

    Projection of ERROR_CODES/SYMPTOM_FIXES via grounding.get_fixes. A step with safe=False (or the
    absence of any step) sets dispatch_recommended=True -- the manufacturer would send a technician.
    """
    appliance, brand = _resolve(model)
    ec = error_code if (error_code and str(error_code).lower() not in ("", "none")) else None
    fixes = get_fixes(appliance, brand, model, symptom or "", ec)
    steps = [
        {"order": i, "instruction": f["instruction"], "safe": f["safe"],
         "source": f["source"], "citation": f.get("citation")}
        for i, f in enumerate(fixes, start=1)
    ]
    dispatch = (len(steps) == 0) or any(not f["safe"] for f in fixes)
    return {
        "model": model,
        "brand": brand,
        "appliance": appliance,
        "error_code": ec,
        "steps": steps,
        "dispatch_recommended": dispatch,
    }


def get_escalation_steps(model, symptom="", error_code=""):
    """OEM tool: ordered escalation-prep steps the customer completes before a technician handoff.

    Sanctioned per (appliance, brand): an appliance module may publish brand-specific steps in
    ESCALATION_STEPS; otherwise the generic DEFAULT_ESCALATION_STEPS apply. `source` is "oem" when
    brand-specific steps were found, else "default". Step content is sourced from grounding so the
    mock server and the app escalation flow can never drift.
    """
    appliance, brand = _resolve(model)
    mod = REGISTRY.get(appliance) if appliance else None
    by_brand = getattr(mod, "ESCALATION_STEPS", {}) if mod else {}
    source = "oem" if (brand and by_brand.get(brand)) else "default"
    ec = error_code if (error_code and str(error_code).lower() not in ("", "none")) else None
    return {
        "model": model,
        "brand": brand,
        "appliance": appliance,
        "error_code": ec,
        "symptom": symptom or None,
        "source": source,
        "steps": _curated_escalation_steps(appliance, brand),
    }


def create_service_request(model, symptom="", error_code="", notes="", contact=None):
    """OEM tool: warranty-aware dispatch handoff; returns a deterministic ticket id (section 16).

    Mock: the ticket id is a stable hash of the request (no clock/random), so the same request maps
    to the same id. A real partner server would persist a dispatch and return its id.
    """
    appliance, brand = _resolve(model)
    manual = get_manual(model)
    seed = "|".join([str(model), str(brand), str(symptom), str(error_code or "")])
    ticket = "SR-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8].upper()
    return {
        "ticket_id": ticket,
        "status": "created",
        "model": model,
        "brand": brand,
        "appliance": appliance,
        "symptom": symptom,
        "error_code": error_code or None,
        "warranty_status": manual.get("warranty_status") if manual.get("found") else "unknown",
        "contact": contact,
        "notes": notes,
        "sent": False,
    }
