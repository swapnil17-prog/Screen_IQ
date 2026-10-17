"""
Test configuration.

Unit tests need nothing external. API/integration tests (test_api.py) need a
Postgres with pgvector: set TEST_DATABASE_URL, e.g.

    TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/screeniq_test

They are skipped when it isn't set. Settings are read at import time, so the
environment is configured here before any `app` import.
"""

import os
from pathlib import Path

os.environ["ENVIRONMENT"] = "test"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["RATE_LIMIT_AUTH_PER_MINUTE"] = "0"
os.environ["RATE_LIMIT_PUBLIC_PER_MINUTE"] = "0"
os.environ["RATE_LIMIT_APPLY_PER_MINUTE"] = "0"
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

import pytest

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture
def samples() -> Path:
    return SAMPLES


def read_sample(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")
