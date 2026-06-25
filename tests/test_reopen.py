import sqlite3
import tempfile
from pathlib import Path

import pytest

from appliance_fixer.case_store import CaseStore
from appliance_fixer.reopen import (
    CaseNotFoundError,
    CorruptCaseError,
    main,
    make_reopen_message,
    reopen_and_continue,
    reopen_case,
)


@pytest.fixture
def tmp_path():
    base = Path.cwd() / ".pytest_reopen_tmp"
    base.mkdir(exist_ok=True)
    yield Path(tempfile.mkdtemp(prefix="test-reopen-", dir=base))


def test_reopen_round_trip(tmp_path):
    db_path = tmp_path / "t.db"
    store = CaseStore(db_path)
    case = store.new_case(
        "case-1",
        "user-1",
        brand="Samsung",
        model_number="RF28R7201",
        appliance="refrigerator",
        symptom_text="Fresh-food warm; freezer cold.",
        status="diagnosing",
    )
    steps = [
        {
            "step_id": "s1",
            "instruction": "Check the evaporator fan for airflow.",
            "asked_at": "t1",
            "user_result": "Fan is spinning.",
            "outcome": "resolved",
        }
    ]
    assert store.save_case(case["case_id"], steps=steps)

    case_id = case["case_id"]
    del store
    store2 = CaseStore(db_path)
    result = reopen_and_continue(case_id, store2)

    assert "RF28R7201" in result["recap"]
    assert "Fresh-food warm; freezer cold." in result["recap"]
    assert "Check the evaporator fan for airflow." in result["recap"]
    assert result["message"].startswith("Resuming")
    assert case_id in result["message"]
    assert result["recap"] in result["message"]
    assert result["status"] == "diagnosing"


def test_reopen_missing_id_raises(tmp_path):
    store = CaseStore(tmp_path / "t.db")

    with pytest.raises(CaseNotFoundError, match="Could not find that repair"):
        reopen_case("case-does-not-exist", store)


def test_reopen_corrupt_data_raises(tmp_path):
    db_path = tmp_path / "t.db"
    store = CaseStore(db_path)
    case = store.new_case("case-1", "user-1")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE cases SET data = ? WHERE case_id = ?",
            ('{"foo": 1}', case["case_id"]),
        )

    with pytest.raises(CorruptCaseError, match="corrupt or missing data"):
        reopen_case(case["case_id"], store)


def test_make_reopen_message_no_model():
    case = {
        "case_id": "case-1",
        "brand": None,
        "model_number": None,
        "appliance": "refrigerator",
    }

    message = make_reopen_message(case, "Recap text.")

    assert message.startswith("Resuming refrigerator (refrigerator) - case case-1.")
    assert "refrigerator" in message
    assert "Recap text." in message


def test_cli_missing_db_returns_1(tmp_path):
    assert main(["case-x", "--db", str(tmp_path / "none.db")]) == 1
