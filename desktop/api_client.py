"""
HTTP client for communicating with the Meet Lessons Django backend.

Handles device pairing, caption submission, and question submission.
All requests use the X-Device-Token header for authentication.
"""

import time
from functools import wraps

import requests

import config


TIMEOUT = 10  # seconds


# Phase 16.7: Retry logic decorator
def with_retry(max_attempts=3, backoff_base=1.5):
    """
    Decorator for API calls with exponential backoff retry.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        backoff_base: Base multiplier for exponential backoff (default: 1.5)
    
    Returns:
        Decorated function that retries on RequestException
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except requests.RequestException as e:
                    if attempt == max_attempts - 1:
                        # Last attempt failed, re-raise
                        raise
                    # Calculate wait time with exponential backoff
                    wait_time = backoff_base ** attempt
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator


class BackendAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _response_error(resp: requests.Response) -> BackendAPIError:
    message = f"HTTP {resp.status_code}"
    try:
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            message = str(data["error"])
    except ValueError:
        if resp.text:
            message = resp.text.strip()
    return BackendAPIError(message, status_code=resp.status_code)


def _base_url() -> str:
    return config.get("backend_url", "http://localhost:8000").rstrip("/")


def _headers() -> dict:
    token = config.get("device_token", "")
    h = {"Content-Type": "application/json"}
    if token:
        h["X-Device-Token"] = token
    return h


def pair_device(code: str, label: str = "Desktop App") -> dict:
    """
    Exchange a pairing code for a device token.

    Returns {"device_id": "...", "token": "..."} on success.
    Raises on network or API error.
    """
    url = f"{_base_url()}/api/devices/pair/"
    resp = requests.post(
        url,
        json={"code": code.strip().upper(), "label": label},
        timeout=TIMEOUT,
    )
    if not resp.ok:
        raise _response_error(resp)
    data = resp.json()

    # Persist credentials
    config.set_key("device_token", data["token"])
    config.set_key("device_id", data["device_id"])
    return data


def send_caption(text: str, speaker: str = "", meeting_id: str = "",
                 meeting_title: str = "") -> dict:
    """
    Send a caption (OCR text) to the backend.

    Returns {"lesson_id": ..., "chunk_id": ..., "created": ...}.
    """
    url = f"{_base_url()}/api/captions/"
    resp = requests.post(
        url,
        json={
            "text": text,
            "speaker": speaker,
            "meeting_id": meeting_id,
            "meeting_title": meeting_title,
        },
        headers=_headers(),
        timeout=TIMEOUT,
    )
    if not resp.ok:
        raise _response_error(resp)
    return resp.json()


def send_question(question: str, context: str = "", meeting_id: str = "",
                  meeting_title: str = "", lesson_id: int = None,
                  initial_text: str = "") -> dict:
    """
    Send a detected question to the backend for AI answering.

    Args:
        question: The question text
        context: Session context (for recitation mode) or empty (for lesson mode)
        meeting_id: Daily meeting ID for recitation mode grouping
        meeting_title: Meeting title (optional)
        lesson_id: Selected lesson ID for lesson mode (None for recitation mode)
        initial_text: Initial text for AI title generation

    Returns {"question_id": ..., "lesson_id": ..., "answer": ...}.
    """
    url = f"{_base_url()}/api/questions/"
    payload = {
        "question": question,
        "context": context,
        "meeting_id": meeting_id,
        "meeting_title": meeting_title,
        "initial_text": initial_text,
    }
    
    # Add lesson_id only if provided (lesson mode)
    if lesson_id is not None:
        payload["lesson_id"] = lesson_id
    
    resp = requests.post(
        url,
        json=payload,
        headers=_headers(),
        timeout=30,  # longer timeout for AI answering
    )
    if not resp.ok:
        raise _response_error(resp)
    return resp.json()


@with_retry(max_attempts=3)
def fetch_lessons() -> list[dict]:
    """
    Fetch list of lessons with source_type='lesson' from backend.
    
    Returns list of {"id": ..., "title": ..., "created_at": ...}.
    """
    url = f"{_base_url()}/api/lessons/list/?source_type=lesson"
    resp = requests.get(
        url,
        headers=_headers(),
        timeout=TIMEOUT,
    )
    if not resp.ok:
        raise _response_error(resp)
    data = resp.json()
    return data.get('lessons', [])


def check_connection() -> bool:
    """Ping the backend to verify connectivity and token validity."""
    try:
        url = f"{_base_url()}/api/captions/"
        # A GET to a POST-only endpoint returns 405 — that's fine, means server is up.
        # We just need to know the server is reachable.
        resp = requests.get(url, headers=_headers(), timeout=5)
        return resp.status_code in (200, 405)
    except requests.RequestException:
        return False


@with_retry(max_attempts=3)
def validate_device_token() -> tuple[bool, str]:
    """Return (is_valid, reason). Uses /api/captions/ auth path without creating data."""
    token = config.get("device_token", "")
    if not token:
        return False, "No device token configured"

    url = f"{_base_url()}/api/captions/"
    try:
        resp = requests.post(
            url,
            json={"text": ""},  # valid auth path; backend returns 400 for missing caption text when token is valid
            headers=_headers(),
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        return False, str(exc)

    if resp.status_code in (401, 403):
        return False, _response_error(resp).args[0]

    if resp.status_code == 400:
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if isinstance(data, dict) and data.get("error") == "Missing caption text":
            return True, ""

    return resp.ok, ""
