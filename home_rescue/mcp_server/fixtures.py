"""Generate / load mock-OEM fixtures by projecting every curated model (section 16, design section 4.3).

Fixtures are a thin projection of the appliance modules so curated data and the mock server cannot
drift; a test asserts the on-disk JSON equals a fresh projection. Run scripts/build_mcp_fixtures.py
to (re)write them after changing the curated data.
"""
from __future__ import annotations

import json
from pathlib import Path

from home_rescue.appliances import REGISTRY
from home_rescue.mcp_server import projections as p

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "mcp"


def build():
    """Return {model: {"manual": ..., "workflows": {code: ...}, "escalation": ...}} for every model with a MANUALS record."""
    fixtures = {}
    for appliance, mod in REGISTRY.items():
        manuals = getattr(mod, "MANUALS", {})
        codes_by_brand = getattr(mod, "ERROR_CODES", {})
        for brand, models in manuals.items():
            for model in models:
                workflows = {
                    code: p.get_pre_service_workflow(model, "", code)
                    for code in codes_by_brand.get(brand, {})
                }
                fixtures[model] = {
                    "manual": p.get_manual(model),
                    "workflows": workflows,
                    "escalation": p.get_escalation_steps(model),
                }
    return fixtures


def write(fixture_dir=FIXTURE_DIR):
    """Write one <model>.json per curated model. Returns the sorted list of model names written."""
    fixture_dir = Path(fixture_dir)
    fixture_dir.mkdir(parents=True, exist_ok=True)
    data = build()
    for model, payload in data.items():
        (fixture_dir / f"{model}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
    return sorted(data)
