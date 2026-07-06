"""
Tiny local config file for API keys.

We keep this separate from the SQLite DB since it's read once at startup
before anything else needs the database. Keys are written to a plain JSON
file in the user's home directory and mirrored into os.environ so
app.ai_engine / app.food_apis (which read from the environment) pick them up
immediately without any extra plumbing.
"""

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".macro_tracker" / "config.json"

_ENV_KEYS = ("GEMINI_API_KEY", "USDA_API_KEY")


def load_into_environment() -> None:
    """Load saved keys from disk into os.environ (called once at app startup)."""
    if not CONFIG_PATH.exists():
        return
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return
    for key in _ENV_KEYS:
        value = data.get(key)
        if value and not os.environ.get(key):
            os.environ[key] = value


def get_saved_key(key: str) -> Optional[str]:
    return os.environ.get(key, "")


def save_key(key: str, value: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    data[key] = value
    CONFIG_PATH.write_text(json.dumps(data, indent=2))
    os.environ[key] = value
