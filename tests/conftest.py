"""Shared pytest fixtures for the test suite.

- Provides a clean SQLite DB per test session (avoids using ./app.db).
- Resets the in-memory analyzer cache between tests so test order does not matter.
"""
from __future__ import annotations

import os

# Ensure ANTHROPIC_API_KEY is set before any backend module is imported.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-fake-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_app.db")
os.environ.setdefault("DB_PATH", "./test_app.db")

import pytest


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_database():
    """Create all tables once per test session in the configured DB."""
    from backend.db import init_db
    init_db()
    yield
    # Teardown: remove the test DB file
    db_file = os.environ.get("DB_PATH", "./test_app.db")
    if db_file and os.path.exists(db_file):
        try:
            os.remove(db_file)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _reset_cache():
    """Clear the global analyzer cache before each test."""
    from backend.services.cache import get_cache
    cache = get_cache()
    cache.clear()
    cache._hits = 0
    cache._misses = 0
    yield
