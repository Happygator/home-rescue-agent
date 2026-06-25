from appliance_fixer.agent import core_initialize_new_case, core_record_step_result
from appliance_fixer.case_store import CaseStore


def make_store(tmp_path):
    return CaseStore(tmp_path / "cases.db")


def test_initialize_new_case_diagnosing(tmp_path):
    store = make_store(tmp_path)

    case_id = core_initialize_new_case(
        store,
        "refrigerator",
        "Samsung",
        "RF28R7201",
        "fresh food warm",
        "",
    )

    case = store.load_case(case_id)
    assert case["status"] == "diagnosing"
    assert case["brand"] == "Samsung"
    assert case["model_number"] == "RF28R7201"
    assert case["data"]["symptom_text"] == "fresh food warm"


def test_record_resolved_sets_resolved(tmp_path):
    store = make_store(tmp_path)
    case_id = core_initialize_new_case(
        store, "refrigerator", "Samsung", "RF28R7201", "fresh food warm", ""
    )

    result = core_record_step_result(
        store, case_id, 1, "Clean condenser coils.", "It is fixed.", "resolved"
    )

    case = store.load_case(case_id)
    assert result["status"] == "resolved"
    assert case["status"] == "resolved"
    assert case["data"]["steps"][-1]["outcome"] == "resolved"


def test_record_unsure_sets_awaiting_user(tmp_path):
    store = make_store(tmp_path)
    case_id = core_initialize_new_case(
        store, "refrigerator", "Samsung", "RF28R7201", "fresh food warm", ""
    )

    result = core_record_step_result(
        store, case_id, 1, "Check door gasket seal.", "I am not sure.", "unsure"
    )

    assert result["status"] == "awaiting_user"
    assert store.load_case(case_id)["status"] == "awaiting_user"


def test_record_not_resolved_stays_diagnosing(tmp_path):
    store = make_store(tmp_path)
    case_id = core_initialize_new_case(
        store, "refrigerator", "Samsung", "RF28R7201", "fresh food warm", ""
    )

    result = core_record_step_result(
        store, case_id, 1, "Clean condenser coils.", "Still warm.", "not_resolved"
    )
    assert result["status"] == "diagnosing"
    assert store.load_case(case_id)["status"] == "diagnosing"

    result = core_record_step_result(
        store, case_id, 2, "Check door gasket seal.", "I am not sure.", "unsure"
    )
    assert result["status"] == "awaiting_user"

    result = core_record_step_result(
        store, case_id, 3, "Recheck airflow.", "Still warm.", "not_resolved"
    )
    assert result["status"] == "diagnosing"
    assert store.load_case(case_id)["status"] == "diagnosing"


def test_unknown_outcome_defaults_unsure(tmp_path):
    store = make_store(tmp_path)
    case_id = core_initialize_new_case(
        store, "refrigerator", "Samsung", "RF28R7201", "fresh food warm", ""
    )

    result = core_record_step_result(
        store, case_id, 1, "Check door gasket seal.", "Maybe.", "banana"
    )

    case = store.load_case(case_id)
    assert result["outcome"] == "unsure"
    assert result["status"] == "awaiting_user"
    assert case["data"]["steps"][-1]["outcome"] == "unsure"


def test_record_missing_case(tmp_path):
    store = make_store(tmp_path)

    result = core_record_step_result(
        store, "nope", 1, "Clean condenser coils.", "Still warm.", "not_resolved"
    )

    assert result["success"] is False


def test_no_next_step_field_written(tmp_path):
    store = make_store(tmp_path)
    case_id = core_initialize_new_case(
        store, "refrigerator", "Samsung", "RF28R7201", "fresh food warm", ""
    )

    core_record_step_result(
        store, case_id, 1, "Clean condenser coils.", "Still warm.", "not_resolved"
    )

    case = store.load_case(case_id)
    assert "next_step" not in case["data"]
