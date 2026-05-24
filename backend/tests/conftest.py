"""Pytest config: ensure the backend package is importable and DATABASE_URL
is set to something innocuous when the test process doesn't have one.

These tests are unit-level — they don't touch a real database — but the
top-level `db.py` reads `DATABASE_URL` at import time, so we provide a
benign default before any module-under-test is loaded.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault(
    "DATABASE_URL", "postgresql://lily:lily@localhost:5432/lily_test_unused"
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
