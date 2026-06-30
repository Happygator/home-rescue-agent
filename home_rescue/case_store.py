"""SQLite/D1-backed case storage for HomeRescue.

The same store works against a local SQLite file (dev/test) or Cloudflare D1
(production). D1 *is* SQLite, so the SQL statements are identical; only the
execution transport differs (local ``sqlite3`` vs D1's HTTP query API). The
backend is chosen inside ``CaseStore.__init__`` from environment variables, so
both the FastAPI app and the agent pick it up automatically.
"""
from __future__ import annotations

import datetime
import json
import os
import sqlite3
from pathlib import Path


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    appliance TEXT,
    brand TEXT,
    model_number TEXT,
    status TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


class _SqliteExecutor:
    """Run SQL against a local SQLite file (dev/test default)."""

    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def query(self, sql, params=()):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def execute(self, sql, params=()):
        # The connection context manager commits on success.
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(sql, params)
            return cur.rowcount

    def ensure_schema(self, create_sql):
        self.execute(create_sql)


class _D1Executor:
    """Run SQL against a Cloudflare D1 database over its HTTP query API."""

    def __init__(self, account_id, database_id, api_token):
        self._url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
            f"/d1/database/{database_id}/query"
        )
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _run(self, sql, params):
        import httpx  # imported lazily so the local SQLite path never needs it

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                self._url,
                headers=self._headers,
                json={"sql": sql, "params": list(params)},
            )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success"):
            raise RuntimeError(f"D1 query failed: {body.get('errors')}")
        return body["result"][0]

    def query(self, sql, params=()):
        return self._run(sql, params).get("results", [])

    def execute(self, sql, params=()):
        return self._run(sql, params).get("meta", {}).get("changes", 0)

    def ensure_schema(self, create_sql):
        # No-op: the D1 schema is provisioned out-of-band via a wrangler migration.
        return None


def _default_executor(db_path):
    """Pick D1 when its env vars are all present, else local SQLite."""
    account_id = os.environ.get("CF_ACCOUNT_ID")
    database_id = os.environ.get("D1_DATABASE_ID")
    api_token = os.environ.get("D1_API_TOKEN")
    if account_id and database_id and api_token:
        return _D1Executor(account_id, database_id, api_token)
    return _SqliteExecutor(db_path)


def appliance_label(case) -> str:
    appliance = case["appliance"] or ""
    brand = case["brand"]
    model_number = case["model_number"]
    if brand or model_number:
        name = " ".join(part for part in (brand, model_number) if part)
        return f"{name} ({appliance})"
    return appliance


def build_recap(case) -> str:
    """Format an already-loaded case dict into the multi-line recap string.

    Shared by the SQLite/D1 CaseStore and the Firestore store so the recap text is identical
    regardless of backend.
    """
    data = case["data"]
    lines = [
        f"Case {case['case_id']}",
        f"Status: {case['status'].upper()}",
        f"Appliance: {appliance_label(case)}",
    ]

    symptom_text = data.get("symptom_text")
    if symptom_text:
        lines.append(f"Symptom: {symptom_text}")

    error_code = data.get("error_code")
    if error_code:
        lines.append(f"Error Code: {error_code}")

    steps = data.get("steps") or []
    if steps:
        lines.append("Steps taken:")
        for idx, step in enumerate(steps, start=1):
            outcome = step.get("outcome") or "unknown"
            instruction = step.get("instruction") or ""
            user_result = step.get("user_result") or "no response"
            lines.append(
                f"  {idx}. [Outcome: {outcome.upper()}] "
                f"{instruction} -> Result: {user_result}"
            )
    else:
        lines.append("No troubleshooting steps taken yet.")

    diagnosis = data.get("diagnosis")
    if diagnosis:
        lines.append(
            "Diagnosis: "
            f"{diagnosis.get('hypothesis')} "
            f"(Confidence: {diagnosis.get('confidence')})"
        )

    escalation = data.get("escalation")
    if escalation:
        lines.append(f"Escalation: Drafted email to {escalation.get('recipient')}")

    return "\n".join(lines)


class CaseStore:
    """Store case rows with variable-length case data in a JSON blob."""

    def __init__(self, db_path="home_rescue.db", executor=None):
        self.db_path = Path(db_path)
        self._exec = executor or _default_executor(db_path)
        self._exec.ensure_schema(_CREATE_TABLE_SQL)

    def new_case(
        self,
        case_id,
        user_id,
        appliance=None,
        brand=None,
        model_number=None,
        status="intake",
        symptom_text="",
        error_code=None,
    ) -> dict:
        timestamp = _now()
        data = {
            "symptom_text": symptom_text,
            "error_code": error_code,
            "media": [],
            "steps": [],
            "messages": [],
            "cache": {},
            "diagnosis": None,
            "escalation": None,
        }
        self._exec.execute(
            """
            INSERT INTO cases (
                case_id,
                user_id,
                appliance,
                brand,
                model_number,
                status,
                data,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                user_id,
                appliance,
                brand,
                model_number,
                status,
                json.dumps(data),
                timestamp,
                timestamp,
            ),
        )
        return self.load_case(case_id)

    def load_case(self, case_id) -> dict | None:
        rows = self._exec.query(
            """
            SELECT
                case_id,
                user_id,
                appliance,
                brand,
                model_number,
                status,
                data,
                created_at,
                updated_at
            FROM cases
            WHERE case_id = ?
            """,
            (case_id,),
        )
        if not rows:
            return None
        return self._row_to_case(rows[0])

    def save_case(
        self,
        case_id,
        *,
        appliance=None,
        brand=None,
        model_number=None,
        status=None,
        symptom_text=None,
        error_code=None,
        media=None,
        steps=None,
        messages=None,
        cache=None,
        diagnosis=None,
        escalation=None,
    ) -> bool:
        case = self.load_case(case_id)
        if case is None:
            return False

        next_appliance = appliance if appliance is not None else case["appliance"]
        next_brand = brand if brand is not None else case["brand"]
        next_model_number = (
            model_number if model_number is not None else case["model_number"]
        )
        # status, when provided, must already be returned by transitions.transition().
        next_status = status if status is not None else case["status"]

        data = dict(case["data"])
        data_updates = {
            "symptom_text": symptom_text,
            "error_code": error_code,
            "media": media,
            "steps": steps,
            "messages": messages,
            "cache": cache,
            "diagnosis": diagnosis,
            "escalation": escalation,
        }
        for key, value in data_updates.items():
            if value is not None:
                data[key] = value

        timestamp = _now()
        self._exec.execute(
            """
            UPDATE cases
            SET appliance = ?,
                brand = ?,
                model_number = ?,
                status = ?,
                data = ?,
                updated_at = ?
            WHERE case_id = ?
            """,
            (
                next_appliance,
                next_brand,
                next_model_number,
                next_status,
                json.dumps(data),
                timestamp,
                case_id,
            ),
        )
        return True

    def delete_case(self, case_id) -> bool:
        return self._exec.execute(
            "DELETE FROM cases WHERE case_id = ?",
            (case_id,),
        ) > 0

    def recap(self, case_id) -> str:
        case = self.load_case(case_id)
        if case is None:
            return "Case not found."
        return build_recap(case)

    def list_cases(self, user_id=None, include_resolved=True) -> list[dict]:
        conditions = []
        params = []
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if not include_resolved:
            conditions.append("status != 'resolved'")

        query = """
            SELECT
                case_id,
                user_id,
                appliance,
                brand,
                model_number,
                status,
                data,
                created_at,
                updated_at
            FROM cases
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY updated_at DESC"

        rows = self._exec.query(query, params)
        return [self._row_to_case(row) for row in rows]

    @staticmethod
    def _row_to_case(row) -> dict:
        try:
            data = json.loads(row["data"])
            if not isinstance(data, dict):
                data = {}
        except (json.JSONDecodeError, TypeError):
            data = {}

        return {
            "case_id": row["case_id"],
            "user_id": row["user_id"],
            "appliance": row["appliance"],
            "brand": row["brand"],
            "model_number": row["model_number"],
            "status": row["status"],
            "data": data,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def _truthy(value) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def make_case_store(db_path="home_rescue.db"):
    """Pick the case store backend from the environment.

    USE_FIRESTORE truthy -> Firestore (Cloud Run / GCP). Otherwise the SQLite/D1 CaseStore
    (which itself picks D1 when its env vars are set, else local SQLite).
    """
    if _truthy(os.environ.get("USE_FIRESTORE")):
        from home_rescue.firestore_store import FirestoreCaseStore

        return FirestoreCaseStore(
            project=os.environ.get("FIRESTORE_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        )
    return CaseStore(db_path)
