"""
HTTP client for communicating with the Meet Lessons Django backend.

Handles device pairing, caption submission, and question submission.
All requests use the X-Device-Token header for authentication.
"""

import requests

import config


TIMEOUT = 10  # seconds


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
                  meeting_title: str = "") -> dict:
    """
    Send a detected question to the backend for AI answering.

    Returns {"question_id": ..., "lesson_id": ..., "answer": ...}.
    """
    url = f"{_base_url()}/api/questions/"
    resp = requests.post(
        url,
        json={
            "question": question,
            "context": context,
            "meeting_id": meeting_id,
            "meeting_title": meeting_title,
        },
        headers=_headers(),
        timeout=30,  # longer timeout for AI answering
    )
    if not resp.ok:
        raise _response_error(resp)
    return resp.json()


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
