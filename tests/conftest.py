from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "etl" / "src"
TMP_DIR = ROOT_DIR / ".test_tmp"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture
def local_tmp_path():
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    path = TMP_DIR / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
