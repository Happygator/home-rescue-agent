"""Fake-client tests for the Firestore + GCS backends (no real GCP needed).

These exercise the adapter logic (field mapping, JSON round-trip, the save_case
merge semantics, list filter/sort, delete-existence, recap parity) by injecting
in-memory fakes via the stores' `client=` hooks. Real Firestore/GCS validation
happens at deploy time.
"""
from __future__ import annotations

from home_rescue.firestore_store import FirestoreCaseStore
from home_rescue.media_store import _GCSMediaStore


# --------------------------- fake Firestore ---------------------------

class _FakeSnap:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _FakeDocRef:
    def __init__(self, store, doc_id):
        self._store = store
        self.id = doc_id

    def set(self, data):
        self._store[self.id] = dict(data)

    def get(self):
        return _FakeSnap(self.id, self._store.get(self.id))

    def delete(self):
        self._store.pop(self.id, None)


class _FakeQuery:
    def __init__(self, store, predicates=None):
        self._store = store
        self._predicates = predicates or []

    def where(self, filter=None):
        field, value = filter.field_path, filter.value
        preds = self._predicates + [lambda d, f=field, v=value: d.get(f) == v]
        return _FakeQuery(self._store, preds)

    def stream(self):
        for doc_id, data in self._store.items():
            if all(p(data) for p in self._predicates):
                yield _FakeSnap(doc_id, data)


class _FakeCollection(_FakeQuery):
    def document(self, doc_id):
        return _FakeDocRef(self._store, doc_id)


class _FakeFirestore:
    def __init__(self):
        self._cols = {}

    def collection(self, name):
        return _FakeCollection(self._cols.setdefault(name, {}))


def _fs_store():
    return FirestoreCaseStore(collection="cases", client=_FakeFirestore())


def test_firestore_new_load_roundtrip():
    s = _fs_store()
    s.new_case("case-1", "u-1", appliance="refrigerator", brand="Samsung",
               model_number="RF28", status="intake", symptom_text="warm", error_code="E5")
    c = s.load_case("case-1")
    assert c["case_id"] == "case-1"
    assert c["user_id"] == "u-1"
    assert c["brand"] == "Samsung"
    assert c["status"] == "intake"
    assert c["data"]["symptom_text"] == "warm"
    assert c["data"]["error_code"] == "E5"
    assert c["data"]["messages"] == []


def test_firestore_load_missing_returns_none():
    assert _fs_store().load_case("nope") is None


def test_firestore_save_merges_and_preserves():
    s = _fs_store()
    s.new_case("case-1", "u-1", appliance="refrigerator", symptom_text="warm")
    created = s.load_case("case-1")
    s.save_case("case-1", brand="LG", messages=[{"role": "user", "text": "hi"}])
    c = s.load_case("case-1")
    assert c["brand"] == "LG"                       # updated
    assert c["data"]["symptom_text"] == "warm"      # preserved (not overwritten)
    assert c["user_id"] == "u-1"                    # preserved
    assert c["created_at"] == created["created_at"]  # preserved
    assert c["data"]["messages"][0]["text"] == "hi"


def test_firestore_delete_returns_existed():
    s = _fs_store()
    s.new_case("case-1", "u-1")
    assert s.delete_case("case-1") is True
    assert s.delete_case("case-1") is False
    assert s.load_case("case-1") is None


def test_firestore_list_filters_and_recap():
    s = _fs_store()
    s.new_case("case-a", "u-1", symptom_text="a")
    s.new_case("case-b", "u-1", symptom_text="b")
    s.new_case("case-c", "u-2", symptom_text="c")
    ids = {c["case_id"] for c in s.list_cases(user_id="u-1")}
    assert ids == {"case-a", "case-b"}
    s.save_case("case-a", status="resolved")
    open_ids = [c["case_id"] for c in s.list_cases(user_id="u-1", include_resolved=False)]
    assert open_ids == ["case-b"]
    assert s.recap("case-b").startswith("Case case-b")
    assert s.recap("missing") == "Case not found."


# --------------------------- fake GCS ---------------------------

class _FakeBlob:
    def __init__(self, store, key):
        self._store = store
        self._key = key

    def upload_from_string(self, data, content_type=None):
        self._store[self._key] = data if isinstance(data, bytes) else data.encode()

    def download_as_bytes(self):
        if self._key not in self._store:
            raise KeyError(self._key)
        return self._store[self._key]

    def exists(self):
        return self._key in self._store


class _FakeBucket:
    def __init__(self, store):
        self._store = store

    def blob(self, key):
        return _FakeBlob(self._store, key)


class _FakeStorage:
    def __init__(self):
        self._buckets = {}

    def bucket(self, name):
        return _FakeBucket(self._buckets.setdefault(name, {}))


def test_gcs_media_roundtrip_and_local_path():
    store = _GCSMediaStore("bkt", client=_FakeStorage())
    store.save("gcs-case", "p.jpg", b"IMG", "image/jpeg")
    assert store.get_bytes("gcs-case", "p.jpg") == b"IMG"
    assert store.exists("gcs-case", "p.jpg") is True
    assert store.get_bytes("gcs-case", "missing.jpg") is None
    assert store.exists("gcs-case", "missing.jpg") is False
    # local_path materializes to a temp file path ending with the ref.
    path = store.local_path("gcs-case", "p.jpg")
    assert path is not None and path.endswith("p.jpg")
    with open(path, "rb") as fh:
        assert fh.read() == b"IMG"
    assert store.local_path("gcs-case", "missing.jpg") is None
