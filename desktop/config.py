"""
Persistent configuration for the Meet Lessons desktop app.

Stores device token, backend URL, and app preferences in a JSON file
located in the user's home directory.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

# Load desktop/.env if it exists (for local dev and production config).
# When running as a packaged .exe without .env, this is silently skipped.
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

# Hardcoded production fallback — used when no .env is present (e.g. packaged .exe for end users).
_PRODUCTION_URL = "https://meetlessons.onrender.com"

# Backend URL priority:
#   1. MEET_LESSONS_URL in desktop/.env (local dev or custom deployment)
#   2. MEET_LESSONS_PRODUCTION_URL in desktop/.env (explicit override)
#   3. MEET_LESSONS_LOCAL_URL in desktop/.env (local dev shorthand)
#   4. _PRODUCTION_URL hardcoded fallback (packaged .exe — no .env needed)
BACKEND_URL = (
    os.environ.get("MEET_LESSONS_URL", "").strip()
    or os.environ.get("MEET_LESSONS_PRODUCTION_URL", "").strip()
    or os.environ.get("MEET_LESSONS_LOCAL_URL", "").strip()
    or _PRODUCTION_URL
)

CONFIG_DIR = Path.home() / ".meet_lessons"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "backend_url": BACKEND_URL,
    "device_token": "",
    "device_id": "",
    "hotkey": "print_screen",
}


def _ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    """Load config from disk, merging with defaults."""
    _ensure_dir()
    data = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return data


def save(data: dict):
    """Persist config to disk."""
    _ensure_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get(key: str, default=None):
    return load().get(key, default)


def set_key(key: str, value):
    data = load()
    data[key] = value
    save(data)


def clear_device():
    """Remove device pairing info."""
    data = load()
    data["device_token"] = ""
    data["device_id"] = ""
    save(data)


def is_paired() -> bool:
    data = load()
    return bool(data.get("device_token"))
