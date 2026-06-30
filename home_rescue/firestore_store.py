"""Firestore-backed case storage for HomeRescue (Cloud Run / GCP).

Mirrors the public API of ``CaseStore`` so it is a drop-in backend selected by
``make_case_store`` when ``USE_FIRESTORE`` is set. Each case is a document keyed
by ``case_id``; the variable-length case data is kept as a JSON string in a
``data`` field (exactly like the SQLite ``data TEXT`` column) so round-trips are
identical regardless of backend. On Cloud Run the Firestore client authenticates
via the attached service account (Application Default Credentials) -- no keys.
"""
from __future__ import annotations

import datetime
import json
import os

from home_rescue.case_store import build_recap


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class FirestoreCaseStore:
    """Store cases as Firestore documents (doc id == case_id)."""

    def __init__(self, project=None, collection=None, client=None):
        self.collection_name = collection or os.environ.get("FIRESTORE_COLLECTION", "cases")
        if client is not None:
            self._db = client
        else:
            from google.cloud import firestore

            self._db = firestore.Client(project=project) if project else firestore.Client()
        # Parity attribute: the SQL store exposes db_path; nothing reads it for Firestore.
        self.db_path = None

    def _col(self):
        return self._db.collection(self.collection_name)

    @staticmethod
    def _doc_to_case(doc) -> dict:
        d = doc.to_dict() or {}
        try:
            data = json.loads(d.get("data") or "{}")
            if not isinstance(data, dict):
                data = {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        return {
            "case_id": doc.id,
            "user_id": d.get("user_id"),
            "appliance": d.get("appliance"),
            "brand": d.get("brand"),
            "model_number": d.get("model_number"),
            "status": d.get("status"),
            "data": data,
            "created_at": d.get("created_at"),
            "updated_at": d.get("updated_at"),
        }

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
        self._col().document(case_id).set(
            {
                "user_id": user_id,
                "appliance": appliance,
                "brand": brand,
                "model_number": model_number,
                "status": status,
                "data": json.dumps(data),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        return self.load_case(case_id)

    def load_case(self, case_id) -> dict | None:
        doc = self._col().document(case_id).get()
        if not doc.exists:
            return None
        return self._doc_to_case(doc)

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

        self._col().document(case_id).set(
            {
                "user_id": case["user_id"],
                "appliance": next_appliance,
                "brand": next_brand,
                "model_number": next_model_number,
                "status": next_status,
                "data": json.dumps(data),
                "created_at": case["created_at"],
                "updated_at": _now(),
            }
        )
        return True

    def delete_case(self, case_id) -> bool:
        ref = self._col().document(case_id)
        existed = ref.get().exists
        ref.delete()
        return existed

    def recap(self, case_id) -> str:
        case = self.load_case(case_id)
        if case is None:
            return "Case not found."
        return build_recap(case)

    def list_cases(self, user_id=None, include_resolved=True) -> list[dict]:
        query = self._col()
        if user_id is not None:
            from google.cloud.firestore_v1.base_query import FieldFilter

            query = query.where(filter=FieldFilter("user_id", "==", user_id))
        cases = [self._doc_to_case(doc) for doc in query.stream()]
        if not include_resolved:
            cases = [c for c in cases if c["status"] != "resolved"]
        # Sort in Python (avoids a Firestore composite index for user_id + updated_at).
        cases.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
        return cases
