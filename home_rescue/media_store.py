"""Local-filesystem / Cloudflare R2 media storage.

Uploaded photos/videos are written to a local ``media/`` directory in dev/test.
On Cloudflare the container disk is ephemeral, so media must live in Cloudflare
**R2** (S3-compatible). This module abstracts media access behind a small store
with two backends, chosen from environment variables by ``get_media_store()``.

The agent vision path needs a LOCAL file path (``read_spec_plate`` reads a path,
and the message/start handlers pass ``image_path`` ending with the media ref), so
the R2 backend materializes objects to a local temp file rather than exposing bytes.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


class _LocalMediaStore:
    """Store media under a local directory (dev/test default)."""

    def __init__(self, root):
        self.root = Path(root)

    def save(self, case_id, ref, data, content_type=None):
        target_dir = self.root / case_id
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / ref).write_bytes(data)

    def get_bytes(self, case_id, ref):
        path = self.root / case_id / ref
        return path.read_bytes() if path.is_file() else None

    def exists(self, case_id, ref):
        return (self.root / case_id / ref).is_file()

    def local_path(self, case_id, ref):
        path = self.root / case_id / ref
        return str(path) if path.is_file() else None


class _R2MediaStore:
    """Store media in a Cloudflare R2 bucket over the S3-compatible API."""

    def __init__(self, account_id, access_key, secret_key, bucket):
        self.account_id = account_id
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket

    def _client(self):
        import boto3  # imported lazily so the local path never needs boto3

        return boto3.client(
            "s3",
            endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="auto",
        )

    @staticmethod
    def _key(case_id, ref):
        return f"{case_id}/{ref}"

    def save(self, case_id, ref, data, content_type=None):
        self._client().put_object(
            Bucket=self.bucket,
            Key=self._key(case_id, ref),
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )

    def get_bytes(self, case_id, ref):
        try:
            obj = self._client().get_object(Bucket=self.bucket, Key=self._key(case_id, ref))
            return obj["Body"].read()
        except Exception:
            return None

    def exists(self, case_id, ref):
        return self.get_bytes(case_id, ref) is not None

    def local_path(self, case_id, ref):
        # Materialize the object to a local temp file so the agent vision path
        # (which needs a real file path ending with the ref) keeps working.
        target = Path(tempfile.gettempdir()) / "home_rescue_media" / case_id / ref
        if target.is_file():
            return str(target)
        data = self.get_bytes(case_id, ref)
        if data is None:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)


class _GCSMediaStore:
    """Store media in a Google Cloud Storage bucket (Cloud Run / GCP).

    On Cloud Run the storage client authenticates via the attached service account
    (Application Default Credentials), so no access keys are passed in.
    """

    def __init__(self, bucket, project=None, client=None):
        self.bucket_name = bucket
        self.project = project
        self._injected_client = client

    def _client(self):
        if self._injected_client is not None:
            return self._injected_client
        from google.cloud import storage  # imported lazily so other paths never need it

        return storage.Client(project=self.project) if self.project else storage.Client()

    def _blob(self, case_id, ref):
        return self._client().bucket(self.bucket_name).blob(f"{case_id}/{ref}")

    def save(self, case_id, ref, data, content_type=None):
        self._blob(case_id, ref).upload_from_string(
            data, content_type=content_type or "application/octet-stream"
        )

    def get_bytes(self, case_id, ref):
        try:
            return self._blob(case_id, ref).download_as_bytes()
        except Exception:
            return None

    def exists(self, case_id, ref):
        try:
            return self._blob(case_id, ref).exists()
        except Exception:
            return False

    def local_path(self, case_id, ref):
        # Materialize the object to a local temp file so the agent vision path
        # (which needs a real file path ending with the ref) keeps working.
        target = Path(tempfile.gettempdir()) / "home_rescue_media" / case_id / ref
        if target.is_file():
            return str(target)
        data = self.get_bytes(case_id, ref)
        if data is None:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)


def get_media_store():
    """Pick the media backend from the environment: GCS, then R2, else local filesystem."""
    gcs_bucket = os.environ.get("GCS_BUCKET")
    if gcs_bucket:
        return _GCSMediaStore(
            gcs_bucket,
            project=os.environ.get("GCS_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"),
        )
    bucket = os.environ.get("R2_BUCKET")
    account_id = os.environ.get("R2_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    if bucket and account_id and access_key and secret_key:
        return _R2MediaStore(account_id, access_key, secret_key, bucket)
    return _LocalMediaStore(os.environ.get("MEDIA_ROOT", "media"))
