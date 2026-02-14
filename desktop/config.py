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

# Backend URL priority (all env-driven):
#   1. MEET_LESSONS_URL (active target URL)
#   2. MEET_LESSONS_PRODUCTION_URL (fallback if MEET_LESSONS_URL is empty)
#   3. MEET_LESSONS_LOCAL_URL (fallback for local development)
BACKEND_URL = (
    os.environ.get("MEET_LESSONS_URL", "").strip()
    or os.environ.get("MEET_LESSONS_PRODUCTION_URL", "").strip()
    or os.environ.get("MEET_LESSONS_LOCAL_URL", "").strip()
)

if not BACKEND_URL:
    raise RuntimeError(
        "Backend URL is not configured. Set MEET_LESSONS_URL (or MEET_LESSONS_PRODUCTION_URL / "
        "MEET_LESSONS_LOCAL_URL) in desktop/.env.",
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
