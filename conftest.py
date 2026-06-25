"""Pytest bootstrap: redirect the temp root into the repo.

On this Windows machine the default %TEMP%\\pytest-of-<user> directory is
access-denied, which breaks the tmp_path fixture. We point Python's temp root at a
repo-local, gitignored directory BEFORE pytest's tmp_path_factory initializes. This
avoids the destructive --basetemp wipe (which fails when a prior run's dir is locked).
"""
from __future__ import annotations

import os
import pathlib
import tempfile

_TMP_ROOT = pathlib.Path(__file__).resolve().parent / ".tmp_pytest"
_TMP_ROOT.mkdir(exist_ok=True)

# Override both the env vars and tempfile's cached default so every temp consumer
# (including pytest's tmp_path_factory) lands inside the repo.
os.environ["TMP"] = str(_TMP_ROOT)
os.environ["TEMP"] = str(_TMP_ROOT)
os.environ["TMPDIR"] = str(_TMP_ROOT)
tempfile.tempdir = str(_TMP_ROOT)
