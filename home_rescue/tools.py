"""Perception + model-number tools for HomeRescue.

read_spec_plate uses Gemini multimodal vision; validate_model canonicalizes and checks the
model number against the curated per-brand sets (handling O<->0 / I<->1 OCR confusions).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from home_rescue.appliances import REGISTRY, module_for

# Default model for plate reads. Standardized on Gemini 2.5 Flash (multimodal vision + reasoning;
# best price-performance of the capable Flash tier). Override with the GEMINI_MODEL env var.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

PLATE_PROMPT = (
    "You are reading the data/spec plate of a household appliance from a photo. "
    "Identify the BRAND and the MODEL number (the manufacturer model code, NOT the serial "
    "number and NOT the part number). Also report any visible error/fault code shown on a "
    "display in the photo. Respond with ONLY compact JSON, no markdown, no prose: "
    '{"brand": <string or null>, "model_number": <string or null>, "error_code": <string or null>}.'
)


def load_key() -> str:
    """Load the Gemini API key from GEMINI_KEY.txt (repo root) or the environment."""
    root = Path(__file__).resolve().parent.parent
    f = root / "GEMINI_KEY.txt"
    raw = ""
    if f.exists():
        raw = f.read_text(encoding="utf-8").strip()
    if not raw:
        raw = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not raw:
        raise RuntimeError(
            "No Gemini API key. Put it in a file named exactly ./GEMINI_KEY.txt "
            "(repo root, not any other filename) or set GOOGLE_API_KEY."
        )
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY"):
        if raw.upper().startswith(name + "="):
            raw = raw.split("=", 1)[1].strip()
    return raw.strip().strip('"').strip("'").strip()


def normalize_model(s):
    """Uppercase, strip whitespace, drop a region suffix after '/', drop a trailing '00'
    revision, and keep only model-legal characters."""
    if not s:
        return ""
    s = str(s).upper()
    s = "".join(ch for ch in s if not ch.isspace())
    if "/" in s:
        s = s.split("/", 1)[0]
    if len(s) > 4 and s.endswith("00"):
        s = s[:-2]
    keep = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-()")
    return "".join(ch for ch in s if ch in keep)


def canonicalize_symbols(s):
    """Map OCR-confused glyphs to digits for robust membership checks: O->0, I->1, L->1."""
    if not s:
        return ""
    return s.replace("O", "0").replace("I", "1").replace("L", "1")


def validate_model(model_number, brand=None, appliance=None):
    """Return the exact supported model string if the input matches a curated model for the
    brand (or any brand when brand is None), else None.

    Searches the given appliance's data module when `appliance` is provided, otherwise every
    registered appliance module. Applies normalize_model + canonicalize_symbols to both sides and
    accepts a containment match (handles trailing revision letters). For each module, when a
    MODEL_PATTERNS regex exists for the brand, a totally malformed input (failing the loose regex)
    skips that module before its membership check.
    """
    norm = normalize_model(model_number)
    canon = canonicalize_symbols(norm)
    if not canon:
        return None

    brand_u = brand.upper() if brand else None
    modules = [module_for(appliance)] if appliance else list(dict.fromkeys(REGISTRY.values()))

    for mod in modules:
        patterns = getattr(mod, "MODEL_PATTERNS", {})
        if brand_u and brand_u in patterns and not re.match(patterns[brand_u], norm):
            continue
        for b, models in mod.SUPPORTED_MODELS.items():
            if brand_u and brand_u != b:
                continue
            for m in models:
                cm = canonicalize_symbols(normalize_model(m))
                if canon == cm or canon in cm or cm in canon:
                    return m
    return None


def _extract_json(text):
    """Pull the first JSON object out of a model response (tolerating markdown fences)."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def _default_client():
    from google import genai
    return genai.Client(api_key=load_key())


def read_spec_plate(photo_path, *, client=None, model=None):
    """Read brand/model_number/error_code from a spec-plate photo via Gemini multimodal.

    `client` is injectable for tests: it must expose `client.models.generate_content(model=...,
    contents=[...]) -> obj with a .text` attribute. Returns a dict
    {brand, model_number, error_code} (values may be None). Never raises on a bad/empty response;
    returns all-None instead. Raises FileNotFoundError if the photo is missing.
    """
    photo_path = Path(photo_path)
    if not photo_path.exists():
        raise FileNotFoundError(f"Photo not found: {photo_path}")
    from google.genai import types
    client = client or _default_client()
    part = types.Part.from_bytes(data=photo_path.read_bytes(), mime_type="image/jpeg")
    resp = client.models.generate_content(model=model or GEMINI_MODEL, contents=[part, PLATE_PROMPT])
    parsed = _extract_json(getattr(resp, "text", "") or "")
    if not parsed:
        return {"brand": None, "model_number": None, "error_code": None}
    return {
        "brand": parsed.get("brand"),
        "model_number": parsed.get("model_number"),
        "error_code": parsed.get("error_code"),
    }


def read_and_cache_plate(case_id, photo_path, store, *, client=None, model=None):
    """Cached plate read (decision #6). Returns the cached dict if present; else reads, stores it
    into case.data.cache.plate_read, and returns it. Also validates the model number and includes
    `matched_model` (the canonical supported model, or None)."""
    case = store.load_case(case_id)
    if case is not None:
        cached = (case.get("data") or {}).get("cache", {}).get("plate_read")
        if cached:
            return cached
    result = read_spec_plate(photo_path, client=client, model=model)
    result["matched_model"] = validate_model(result.get("model_number"), result.get("brand"))
    if case is not None:
        cache = dict((case.get("data") or {}).get("cache", {}))
        cache["plate_read"] = result
        store.save_case(case_id, cache=cache)
    return result
