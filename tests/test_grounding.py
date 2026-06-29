from home_rescue.appliances import (
    REGISTRY,
    infer_appliance,
    module_for,
    normalize_appliance,
)
from home_rescue.case_store import CaseStore
from home_rescue.grounding import (
    error_code_meaning,
    get_fixes,
    get_inspection_shots,
    get_manual,
)
from home_rescue.tools import validate_model


def test_known_error_code_meaning():
    assert "Power Failure" in error_code_meaning("Whirlpool", "PF")

    fixes = get_fixes(
        "refrigerator",
        "Whirlpool",
        "WRS555",
        "display shows a code",
        error_code="PF",
    )

    assert all(fix["source"] == "error_code" for fix in fixes)
    assert "dismiss" in fixes[0]["instruction"]
    assert "PF" in fixes[0]["instruction"]


def test_out_of_table_code_not_guessed():
    fixes = get_fixes(
        "refrigerator",
        "Whirlpool",
        "WRS555",
        "display shows a code",
        error_code="E99",
    )

    assert len(fixes) == 1
    assert fixes[0]["source"] == "manual"
    assert "manual" in fixes[0]["instruction"]
    assert error_code_meaning("Whirlpool", "E99") is None


def test_samsung_demo_mode():
    fixes = get_fixes(
        "refrigerator",
        "Samsung",
        "RF28T5001SR",
        "will not cool",
        error_code="OF OF",
    )

    assert "Demo" in fixes[0]["instruction"] or "Power Freeze" in fixes[0]["instruction"]


def test_symptom_ranked_curated():
    fixes = get_fixes(
        "refrigerator",
        "Samsung",
        "RF28T5001SR",
        "fresh food warm but freezer still cold",
        error_code=None,
    )

    assert len(fixes) >= 2
    assert all(fix["source"] == "curated" for fix in fixes)
    assert "evaporator fan" in fixes[0]["instruction"]


def test_fallback_when_no_match():
    fixes = get_fixes(
        "refrigerator",
        "GE",
        "GSS25",
        "weird noise",
        error_code=None,
    )

    assert fixes
    assert all(fix["source"] == "fallback" for fix in fixes)


def test_cache_hit_second_call(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    cid = "case-1"
    store.new_case(
        cid,
        "user-1",
        appliance="refrigerator",
        brand="Samsung",
        model_number="RF28T5001SR",
        symptom_text="fresh food warm but freezer still cold",
    )

    first = get_fixes(
        "refrigerator",
        "Samsung",
        "RF28T5001SR",
        "fresh food warm but freezer still cold",
        store=store,
        case_id=cid,
    )
    second = get_fixes(
        "refrigerator",
        "Samsung",
        "RF28T5001SR",
        "fresh food warm but freezer still cold",
        store=store,
        case_id=cid,
    )

    assert second == first
    case = store.load_case(cid)
    assert case["data"]["cache"]["grounded_fixes"] == first

    sentinel = [{"instruction": "SENTINEL", "safe": True, "source": "curated"}]
    store.save_case(cid, cache={"grounded_fixes": sentinel})

    cached = get_fixes(
        "refrigerator",
        "Samsung",
        "RF28T5001SR",
        "weird noise",
        store=store,
        case_id=cid,
    )

    assert cached == sentinel


def test_inspection_shots_shape():
    for shots in (get_inspection_shots(), get_inspection_shots("sealed_system")):
        assert shots
        for item in shots:
            assert set(item) == {"what_to_film", "where", "narration"}
            assert isinstance(item["what_to_film"], str)
            assert isinstance(item["where"], str)
            assert isinstance(item["narration"], str)


# --- dishwasher registry regression tests ---


def test_registry_normalization_and_default():
    assert set(REGISTRY) == {"refrigerator", "dishwasher"}
    assert normalize_appliance("dish washer") == "dishwasher"
    assert normalize_appliance("fridge") == "refrigerator"
    assert module_for(None).APPLIANCE == "refrigerator"
    assert module_for("dishwasher").APPLIANCE == "dishwasher"


def test_infer_appliance_from_symptom_text():
    assert infer_appliance("Dishwasher won't drain, water sits in the bottom") == "dishwasher"
    assert infer_appliance("dishes come out dirty") == "dishwasher"
    assert infer_appliance("Fridge is warm but freezer is cold") == "refrigerator"
    assert infer_appliance("the refrigerator ice maker stopped") == "refrigerator"
    # Washers are not a supported appliance: inference must degrade to None rather than
    # mislabel the case (which would serve the wrong appliance's curated fixes).
    assert infer_appliance("Washer won't spin, clothes are soaking wet") is None
    assert infer_appliance("the washing machine is leaking") is None
    # "washer" must NOT fire inside "dishwasher" (word-boundary guard still holds).
    assert infer_appliance("Dishwasher won't drain") == "dishwasher"
    # No clear hint -> None (so the case is NOT mislabeled as a refrigerator).
    assert infer_appliance("it is making a weird noise") is None
    assert infer_appliance("") is None
    assert infer_appliance(None) is None


def test_error_code_meaning_routes_by_appliance():
    # Same brand+code resolves to a different curated meaning per appliance.
    assert "not draining" in error_code_meaning("LG", "OE", "dishwasher")
    assert error_code_meaning("LG", "OE", "refrigerator") == "Drain Error"
    assert error_code_meaning("LG", "OE") == "Drain Error"  # default = fridge


def test_dishwasher_oe_happy_path():
    fixes = get_fixes("dishwasher", "LG", "LDFC2423V", "it will not drain", error_code="OE")
    assert all(fix["source"] == "error_code" for fix in fixes)
    assert fixes[0]["safe"] is True
    assert "filter" in fixes[0]["instruction"].lower()


def test_dishwasher_mixed_case_error_code_lookup_is_case_insensitive():
    assert error_code_meaning("LG", "bE", "dishwasher") == error_code_meaning("LG", "BE", "dishwasher")
    assert error_code_meaning("LG", "be", "dishwasher") == error_code_meaning("LG", "bE", "dishwasher")

    fixes = get_fixes("dishwasher", "LG", "LDFC2423V", "", error_code="BE")
    assert all(fix["source"] == "error_code" for fix in fixes)
    assert "manual" not in fixes[0]["instruction"].lower()


def test_dishwasher_heater_error_escalates():
    fixes = get_fixes("dishwasher", "LG", "LDFC2423V", "", error_code="HE")
    assert fixes[0]["safe"] is False
    assert any("service" in fix["instruction"].lower() for fix in fixes)


def test_dishwasher_symptom_keyword_path():
    fixes = get_fixes("dishwasher", "LG", "LDFC2423V", "my dishwasher is not draining", error_code=None)
    assert all(fix["source"] == "curated" for fix in fixes)
    assert "filter" in fixes[0]["instruction"].lower()


def test_dishwasher_inspection_shots_appliance_aware():
    shots = get_inspection_shots("drain", "dishwasher")
    assert shots
    assert any("filter" in s["what_to_film"].lower() for s in shots)
    for item in shots:
        assert set(item) == {"what_to_film", "where", "narration"}


def test_validate_model_across_registry():
    assert validate_model("LDFC2423V", "LG") == "LDFC2423V"
    assert validate_model("LDFC2423V", "LG", "dishwasher") == "LDFC2423V"
    assert validate_model("RF28T5001SR", "SAMSUNG") == "RF28T5001SR"
    assert validate_model("LFXS26973S", "LG") == "LFXS26973S"  # LG fridge model still resolves
    assert validate_model("totally-bogus") is None


# --- manual reference + cited out-of-table fallback ---


def test_get_manual_records():
    dw = get_manual("dishwasher", "LG", "LDFC2423V")
    assert dw and dw["manual_url"].startswith("https://")
    assert dw["error_code_url"].endswith("20150933422943")

    fr = get_manual("refrigerator", "Samsung", "RF28T5001SR")
    assert fr and fr["pages"]["service_error_codes"] == 65

    assert get_manual("dishwasher", "LG", "NOPE") is None
    assert get_manual("refrigerator", "Whirlpool", "WRS555") is None  # not curated


def test_dishwasher_out_of_table_cites_manual_url():
    fixes = get_fixes("dishwasher", "LG", "LDFC2423V", "", error_code="XX1")
    assert len(fixes) == 1
    assert fixes[0]["source"] == "manual"
    assert "XX1" in fixes[0]["instruction"]
    assert "manual" in fixes[0]["instruction"]
    assert "lg.com" in fixes[0]["instruction"]
    assert error_code_meaning("LG", "XX1", "dishwasher") is None


def test_samsung_out_of_table_cites_service_page():
    fixes = get_fixes("refrigerator", "Samsung", "RF28T5001SR", "", error_code="21C")
    assert fixes[0]["source"] == "manual"
    assert "65" in fixes[0]["instruction"]  # service_error_codes page number
    assert "manual" in fixes[0]["instruction"]


# --- per-fix provenance (citation carried through) ---


def test_error_code_fix_carries_citation_url():
    fixes = get_fixes("dishwasher", "LG", "LDFC2423V", "", error_code="OE")
    assert all(f["source"] == "error_code" for f in fixes)
    assert all(f["citation"] and "lg.com" in f["citation"] for f in fixes)


def test_symptom_fix_cites_repair_guide():
    fixes = get_fixes("dishwasher", "LG", "LDFC2423V", "my dishwasher is not draining", error_code=None)
    assert all(f["source"] == "curated" for f in fixes)
    assert all(f["citation"] == "https://www.ifixit.com/Device/Dishwasher" for f in fixes)


def test_out_of_table_fix_citation_is_manual_url():
    fixes = get_fixes("dishwasher", "LG", "LDFC2423V", "", error_code="ZZ9")
    assert fixes[0]["source"] == "manual"
    assert fixes[0]["citation"] and "lg.com" in fixes[0]["citation"]


def test_cross_appliance_symptom_key_override_degrades_not_crashes():
    # The fridge-only schema router can yield a fridge bucket for a non-fridge appliance; passing
    # such a key must degrade to the safe fallback, never KeyError on the dishwasher's SYMPTOM_FIXES.
    fixes = get_fixes("dishwasher", "LG", "LDFC2423V", "standing water in the tub",
                      symptom_key="water_pooling_crisper")
    assert fixes
    assert all(f["source"] == "fallback" for f in fixes)
