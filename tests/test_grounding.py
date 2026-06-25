from appliance_fixer.case_store import CaseStore
from appliance_fixer.grounding import error_code_meaning, get_fixes, get_inspection_shots


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
