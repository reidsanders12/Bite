"""
Shared test fixtures.

Sets dummy credentials *before* any `app.*` module is imported, so tests
never depend on (or accidentally read) a developer's real `.env` file or
touch a real Supabase endpoint. `load_dotenv()` in app/config.py never
overrides variables already present in the environment, so these values win
even if a real `.env` also exists. (Gemini calls go through the
gemini-proxy Edge Function now -- app/config.py no longer reads a
GEMINI_API_KEY at all, so there's nothing to stub for it here.)
"""
import os

os.environ.setdefault("USDA_API_KEY", "test-usda-key")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")

import pytest
from unittest.mock import MagicMock

from app.database import Database
from app.state import AppState


@pytest.fixture
def state(monkeypatch):
    """An AppState wired to a MagicMock(spec=Database) instead of a real
    Supabase-backed Database -- so state.db.<method>.return_value / .assert_*
    work against the real method names (typos raise immediately) with zero
    network calls."""
    fake_db = MagicMock(spec=Database)
    monkeypatch.setattr("app.state.Database", lambda: fake_db)
    return AppState()
