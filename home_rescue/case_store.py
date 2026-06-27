"""SQLite-backed case storage for HomeRescue."""
from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class CaseStore:
    """Store case rows with variable-length case data in a JSON blob."""

    def __init__(self, db_path="home_rescue.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
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
            )

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
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
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
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
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
            ).fetchone()

        if row is None:
            return None
        return self._row_to_case(row)

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
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM cases WHERE case_id = ?",
                (case_id,),
            )
        return cursor.rowcount > 0

    def recap(self, case_id) -> str:
        case = self.load_case(case_id)
        if case is None:
            return "Case not found."

        data = case["data"]
        lines = [
            f"Case {case['case_id']}",
            f"Status: {case['status'].upper()}",
            f"Appliance: {self._appliance_label(case)}",
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

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
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

    @staticmethod
    def _appliance_label(case) -> str:
        appliance = case["appliance"] or ""
        brand = case["brand"]
        model_number = case["model_number"]
        if brand or model_number:
            name = " ".join(part for part in (brand, model_number) if part)
            return f"{name} ({appliance})"
        return appliance
