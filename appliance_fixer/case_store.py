"""CaseStore: SQLite-backed storage for Appliance Fixer case files.

Manages case creation, loading, saving, and generating summaries (recaps).
"""
from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path


class CaseStore:
    def __init__(self, db_path: str | Path = "appliance_fixer.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Create the cases table if it does not exist."""
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
            conn.commit()

    def new_case(
        self,
        case_id: str,
        user_id: str,
        appliance: str | None = None,
        brand: str | None = None,
        model_number: str | None = None,
        status: str = "intake",
        symptom_text: str = "",
    ) -> dict:
        """Create a new case in the database with initialized CaseFile schema."""
        now = datetime.datetime.utcnow().isoformat() + "Z"
        case_file = {
            "symptom_text": symptom_text,
            "error_code": None,
            "photos": [],
            "steps": [],
            "cache": {},
            "diagnosis": None,
            "escalation": None,
        }

        data_str = json.dumps(case_file)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cases (case_id, user_id, appliance, brand, model_number, status, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (case_id, user_id, appliance, brand, model_number, status, data_str, now, now),
            )
            conn.commit()

        return self.load_case(case_id)

    def load_case(self, case_id: str) -> dict | None:
        """Load a case by case_id, parsing the JSON data column."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT case_id, user_id, appliance, brand, model_number, status, data, created_at, updated_at FROM cases WHERE case_id = ?",
                (case_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        case_dict = dict(row)
        try:
            case_dict["data"] = json.loads(case_dict["data"])
        except (json.JSONDecodeError, TypeError):
            case_dict["data"] = {}

        return case_dict

    def save_case(
        self,
        case_id: str,
        brand: str | None = None,
        model_number: str | None = None,
        status: str | None = None,
        symptom_text: str | None = None,
        error_code: str | None = None,
        photos: list | None = None,
        steps: list | None = None,
        cache: dict | None = None,
        diagnosis: dict | None = None,
        escalation: dict | None = None,
    ) -> bool:
        """Update case metadata and/or specific fields inside the JSON data blob."""
        existing = self.load_case(case_id)
        if not existing:
            return False

        # Build update values for main columns
        up_brand = brand if brand is not None else existing["brand"]
        up_model = model_number if model_number is not None else existing["model_number"]
        up_status = status if status is not None else existing["status"]

        # Update JSON payload (CaseFile)
        data = existing["data"]
        if symptom_text is not None:
            data["symptom_text"] = symptom_text
        if error_code is not None:
            data["error_code"] = error_code
        if photos is not None:
            data["photos"] = photos
        if steps is not None:
            data["steps"] = steps
        if cache is not None:
            data["cache"] = cache
        if diagnosis is not None:
            data["diagnosis"] = diagnosis
        if escalation is not None:
            data["escalation"] = escalation

        now = datetime.datetime.utcnow().isoformat() + "Z"
        data_str = json.dumps(data)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE cases
                SET brand = ?, model_number = ?, status = ?, data = ?, updated_at = ?
                WHERE case_id = ?
                """,
                (up_brand, up_model, up_status, data_str, now, case_id),
            )
            conn.commit()

        return True

    def recap(self, case_id: str) -> str:
        """Generate a user-readable summary text of the case history."""
        case = self.load_case(case_id)
        if not case:
            return "Case not found."

        data = case["data"]
        lines = []
        lines.append(f"=== Case Recap: {case_id} ===")
        lines.append(f"Status: {case['status'].upper()}")
        
        appliance_info = case['appliance'] or "unknown appliance"
        if case['brand'] or case['model_number']:
            brand = case['brand'] or "Unknown"
            model = case['model_number'] or "Unknown"
            lines.append(f"Appliance: {brand} {model} ({appliance_info})")
        else:
            lines.append(f"Appliance: {appliance_info}")

        if data.get("symptom_text"):
            lines.append(f"Symptom: {data['symptom_text']}")
        if data.get("error_code"):
            lines.append(f"Error Code: {data['error_code']}")

        steps = data.get("steps", [])
        if steps:
            lines.append("\nSteps taken:")
            for idx, s in enumerate(steps, 1):
                instr = s.get("instruction", "")
                result = s.get("user_result", "no response")
                outcome = s.get("outcome", "unknown")
                lines.append(f"  {idx}. [Outcome: {outcome.upper()}] {instr} -> Result: {result}")
        else:
            lines.append("\nNo troubleshooting steps taken yet.")

        if data.get("diagnosis"):
            diag = data["diagnosis"]
            lines.append(f"\nDiagnosis: {diag.get('hypothesis', 'None')} (Confidence: {diag.get('confidence', 'N/A')})")

        if data.get("escalation"):
            esc = data["escalation"]
            lines.append(f"\nEscalation: Drafted email to {esc.get('recipient', 'unknown')}")

        return "\n".join(lines)
