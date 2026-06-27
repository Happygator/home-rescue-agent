"""Option-2 symptom router: an LLM extracts a structured feature schema from the free-text symptom,
then a PURE deterministic table maps those features to a curated SYMPTOM_FIXES bucket key.

This replaces the brittle keyword matcher (grounding._match_symptom_key) for the live agent's fix
lookup, WITHOUT touching the curated, safety-reviewed fix lists themselves -- only the router
changes. Fully reversible: set env SYMPTOM_ROUTER=keyword to fall back to the keyword matcher.

Responsibility split (the point of option 2):
  * extract_features() -- the ONLY non-deterministic part: Gemini structured-output NLU,
    prose -> a small enum schema. Returns {} on any error (caller then falls back to keyword).
  * route_features()   -- PURE, unit-testable decision table: features -> bucket key or None.
  * classify_symptom() -- orchestration + env toggle + graceful keyword fallback + caching.
"""
from __future__ import annotations

import os
from enum import Enum

from pydantic import BaseModel

from home_rescue.grounding import _match_symptom_key
from home_rescue.tools import GEMINI_MODEL, _extract_json, load_key

# Canonical curated buckets (must match fridge.SYMPTOM_FIXES keys).
SYMPTOM_KEYS = (
    "fresh_food_warm_freezer_fine",
    "both_warm_compressor_running",
    "runs_constantly",
    "water_pooling_crisper",
    "ice_maker_stopped",
    "freezer_frosting",
    "warm_with_buzzing",
)


def active_mode() -> str:
    """Which router is live: 'schema' (option 2, default) or 'keyword' (legacy revert)."""
    mode = (os.environ.get("SYMPTOM_ROUTER") or "schema").strip().lower()
    return mode if mode in ("schema", "keyword") else "schema"


# ---------- structured feature schema (Gemini response_schema) ----------

class WarmCompartment(str, Enum):
    fridge_only = "fridge_only"
    freezer_only = "freezer_only"
    both = "both"
    none = "none"
    unknown = "unknown"


class Noise(str, Enum):
    none = "none"
    buzzing = "buzzing"
    rattling = "rattling"
    clicking = "clicking"
    unknown = "unknown"


class Tri(str, Enum):
    yes = "yes"
    no = "no"
    unknown = "unknown"


class SymptomFeatures(BaseModel):
    """Structured reading of the user's refrigerator complaint. Each field defaults to its
    'unknown'/'none' member so a partial extraction still routes."""
    warm_compartment: WarmCompartment = WarmCompartment.unknown
    abnormal_noise: Noise = Noise.unknown
    compressor_running: Tri = Tri.unknown
    runs_constantly: Tri = Tri.unknown
    water_pooling: Tri = Tri.unknown
    ice_maker_problem: Tri = Tri.unknown
    frost_buildup: Tri = Tri.unknown


EXTRACT_PROMPT = (
    "You classify a household REFRIGERATOR complaint into structured features. "
    "Read the symptom (and any error code) and fill EVERY field. Use 'unknown' (or 'none') when "
    "the text does not say -- never guess. Definitions: warm_compartment = which sections are too "
    "warm; abnormal_noise = any buzzing/rattling/clicking the user mentions; compressor_running = "
    "whether the user says the compressor/unit is running; runs_constantly = it never cycles off; "
    "water_pooling = water/puddle inside (e.g. under the crisper); ice_maker_problem = ice maker "
    "not making ice; frost_buildup = visible frost/ice in the freezer.\n\n"
    "Symptom: {symptom}\nError code: {error_code}"
)


# ---------- pure deterministic router ----------

def route_features(features) -> str | None:
    """Map a feature dict (string values; missing -> treated as 'unknown') to a SYMPTOM_FIXES key,
    or None when nothing fits (caller falls back to keyword/clarify). PURE -- no model, no I/O.

    Priority mirrors the curated corrections: leak/ice/frost first (specific & unambiguous), then
    the warm-with-buzzing defrost case, then runs-constantly, then the warm-compartment split
    (both -> condenser-first; fridge-only -> evaporator/airflow)."""
    f = features or {}

    def is_yes(key):
        return str(f.get(key, "unknown")).lower() == "yes"

    warm = str(f.get("warm_compartment", "unknown")).lower()
    noise = str(f.get("abnormal_noise", "unknown")).lower()

    if is_yes("water_pooling"):
        return "water_pooling_crisper"
    if is_yes("ice_maker_problem"):
        return "ice_maker_stopped"
    if is_yes("frost_buildup"):
        return "freezer_frosting"
    if noise in ("buzzing", "rattling") and warm in ("fridge_only", "both"):
        return "warm_with_buzzing"
    if is_yes("runs_constantly"):
        return "runs_constantly"
    if warm == "both":
        return "both_warm_compressor_running"
    if warm == "fridge_only":
        return "fresh_food_warm_freezer_fine"
    if warm == "unknown" and is_yes("compressor_running"):
        return "both_warm_compressor_running"
    return None


# ---------- non-deterministic extraction (Gemini structured output) ----------

def extract_features(symptom, error_code=None, *, client=None, model=None) -> dict:
    """Gemini structured-output NLU: prose -> SymptomFeatures dict. Returns {} on empty input or
    ANY error (network/quota/parse), so the caller can fall back to keyword matching. `client` is
    injectable for tests (must expose client.models.generate_content(model=, contents=, config=))."""
    text = (symptom or "").strip()
    if not text:
        return {}
    try:
        from google import genai
        from google.genai import types

        client = client or genai.Client(api_key=load_key())
        resp = client.models.generate_content(
            model=model or GEMINI_MODEL,
            contents=EXTRACT_PROMPT.format(symptom=text, error_code=error_code or "none"),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SymptomFeatures,
                temperature=0,
            ),
        )
        parsed = getattr(resp, "parsed", None)
        if parsed is not None:
            return parsed.model_dump(mode="json") if hasattr(parsed, "model_dump") else dict(parsed)
        return _extract_json(getattr(resp, "text", "") or "") or {}
    except Exception:
        return {}


# ---------- orchestration: toggle + extract + route + keyword fallback ----------

_classify_cache: dict = {}


def clear_cache() -> None:
    """Drop the in-process classification cache (used by tests)."""
    _classify_cache.clear()


def classify_symptom(symptom, error_code=None, *, client=None, model=None) -> str | None:
    """Resolve a SYMPTOM_FIXES bucket key for the symptom, honoring SYMPTOM_ROUTER.

    keyword mode -> the legacy keyword matcher.
    schema mode  -> extract features (Gemini) + route via the pure table; if that yields nothing
                    (no match, or extraction failed/empty), fall back to the keyword matcher so the
                    schema router is never WORSE than keyword on coverage.
    Returns a bucket key or None. Caches by (symptom, error_code) on the production path
    (client is None) to avoid repeat LLM calls within a case."""
    if active_mode() == "keyword":
        return _match_symptom_key(symptom)

    cache_key = ((symptom or "").strip().lower(), (error_code or "").strip().lower())
    if client is None and cache_key in _classify_cache:
        return _classify_cache[cache_key]

    features = extract_features(symptom, error_code, client=client, model=model)
    key = route_features(features)
    if key is None:
        key = _match_symptom_key(symptom)

    if client is None:
        _classify_cache[cache_key] = key
    return key
