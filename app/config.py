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

# ---------------------------------------------------------------- HARDCODED KEYS
# Put your real API keys inside the strings below
HARDCODED_GEMINI_KEY = "AQ.Ab8RN6IBEWaFTLtSEHdQbyvvageUDUCLbNQlt4eiwFNGKePPqQ"
HARDCODED_USDA_KEY = "DEMO_KEY"


def load_into_environment() -> None:
    """Load saved keys from disk into os.environ (called once at app startup)."""
    # 1. First inject your hardcoded keys so they work right out of the box
    if HARDCODED_GEMINI_KEY:
        os.environ["GEMINI_API_KEY"] = HARDCODED_GEMINI_KEY
    if HARDCODED_USDA_KEY:
        os.environ["USDA_API_KEY"] = HARDCODED_USDA_KEY

    # 2. Fallback: Read from disk if the user overrides them or has a config file
    if not CONFIG_PATH.exists():
        return
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return
        
    for key in ("GEMINI_API_KEY", "USDA_API_KEY"):
        value = data.get(key)
        if value and value.strip():
            os.environ[key] = value


def get_saved_key(key: str) -> Optional[str]:
    """Retrieves the active key from the system environment."""
    return os.environ.get(key, "")


def save_key(key: str, value: str) -> None:
    """Saves a modified key to local storage and mirrors it into the session."""
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