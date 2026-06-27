"""Unit tests for the option-2 schema symptom router (home_rescue.symptom_router) and the
get_fixes symptom_key override. The pure decision table and the toggle/fallback are covered without
any live LLM call (a fake client is injected); only extract_features would hit Gemini."""
import pytest

from home_rescue import symptom_router as sr
from home_rescue.grounding import get_fixes


class _FakeResp:
    def __init__(self, parsed=None, text=""):
        self.parsed = parsed
        self.text = text


class _FakeModels:
    def __init__(self, payload):
        self._payload = payload

    def generate_content(self, *, model, contents, config):
        return _FakeResp(text=self._payload)


class _FakeClient:
    """Injectable stand-in: returns a fixed JSON string as resp.text (no resp.parsed)."""
    def __init__(self, payload):
        self.models = _FakeModels(payload)


def test_route_features_table():
    assert sr.route_features({"water_pooling": "yes"}) == "water_pooling_crisper"
    assert sr.route_features({"ice_maker_problem": "yes"}) == "ice_maker_stopped"
    assert sr.route_features({"frost_buildup": "yes"}) == "freezer_frosting"
    assert sr.route_features({"warm_compartment": "both", "abnormal_noise": "buzzing"}) == "warm_with_buzzing"
    assert sr.route_features({"runs_constantly": "yes"}) == "runs_constantly"
    assert sr.route_features({"warm_compartment": "both"}) == "both_warm_compressor_running"
    assert sr.route_features({"warm_compartment": "fridge_only"}) == "fresh_food_warm_freezer_fine"
    assert sr.route_features({"warm_compartment": "unknown", "compressor_running": "yes"}) == "both_warm_compressor_running"
    assert sr.route_features({}) is None
    assert sr.route_features({"warm_compartment": "unknown"}) is None


def test_route_features_only_returns_known_keys():
    samples = [
        {"water_pooling": "yes"}, {"ice_maker_problem": "yes"}, {"frost_buildup": "yes"},
        {"warm_compartment": "both", "abnormal_noise": "rattling"}, {"runs_constantly": "yes"},
        {"warm_compartment": "both"}, {"warm_compartment": "fridge_only"},
    ]
    for s in samples:
        assert sr.route_features(s) in sr.SYMPTOM_KEYS


def test_active_mode_default_and_revert(monkeypatch):
    monkeypatch.delenv("SYMPTOM_ROUTER", raising=False)
    assert sr.active_mode() == "schema"
    monkeypatch.setenv("SYMPTOM_ROUTER", "KEYWORD")
    assert sr.active_mode() == "keyword"
    monkeypatch.setenv("SYMPTOM_ROUTER", "bogus")
    assert sr.active_mode() == "schema"


def test_classify_schema_with_fake_client(monkeypatch):
    monkeypatch.setenv("SYMPTOM_ROUTER", "schema")
    sr.clear_cache()
    client = _FakeClient('{"warm_compartment": "both", "abnormal_noise": "none"}')
    # "50F" has no keyword, but the schema route maps both-warm -> condenser-first bucket.
    assert sr.classify_symptom("my fridge is sitting at 50F", None, client=client) == "both_warm_compressor_running"


def test_classify_falls_back_to_keyword_on_bad_extraction(monkeypatch):
    monkeypatch.setenv("SYMPTOM_ROUTER", "schema")
    sr.clear_cache()
    client = _FakeClient("not json at all")  # extract_features -> {} -> route None -> keyword
    assert sr.classify_symptom("fresh food warm but freezer still cold", None, client=client) == "fresh_food_warm_freezer_fine"


def test_keyword_mode_ignores_client(monkeypatch):
    monkeypatch.setenv("SYMPTOM_ROUTER", "keyword")
    sr.clear_cache()
    client = _FakeClient('{"water_pooling": "yes"}')  # would say water in schema mode; ignored here
    assert sr.classify_symptom("the ice maker stopped making ice", None, client=client) == "ice_maker_stopped"


def test_get_fixes_honors_symptom_key_override():
    # Symptom text has NO keyword match, but an explicit key forces the curated bucket.
    fixes = get_fixes("refrigerator", "Samsung", "RF28T5001SR", "it is at 50 degrees", None,
                      symptom_key="both_warm_compressor_running")
    assert fixes and all(f["source"] == "curated" for f in fixes)
    assert "condenser coils" in fixes[0]["instruction"]
    # Explicit None -> no bucket -> safe generic fallback.
    fixes_none = get_fixes("refrigerator", "Samsung", "RF28T5001SR", "it is at 50 degrees", None,
                           symptom_key=None)
    assert fixes_none and all(f["source"] == "fallback" for f in fixes_none)
    # Default (sentinel) -> keyword path, unchanged behavior.
    fixes_kw = get_fixes("refrigerator", "GE", "GSS25", "weird noise", None)
    assert all(f["source"] == "fallback" for f in fixes_kw)
