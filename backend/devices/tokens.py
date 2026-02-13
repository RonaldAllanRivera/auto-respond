"""
Device token utilities.

Tokens are opaque strings: `<device_id>:<random_secret>`.
The random secret is SHA-256 hashed and stored on the Device row.
Verification: look up device by ID, hash the incoming secret, compare.
"""

import secrets

from .models import Device


def issue_token(device: Device) -> str:
    """Generate a new token for a device and persist its hash. Returns the raw token."""
    raw_secret = secrets.token_urlsafe(32)
    device.token_hash = Device.hash_token(raw_secret)
    device.save(update_fields=["token_hash"])
    return f"{device.id}:{raw_secret}"


def verify_token(raw_token: str) -> Device | None:
    """Verify a raw token string. Returns the Device if valid, else None."""
    if ":" not in raw_token:
        return None

    device_id, raw_secret = raw_token.split(":", 1)

    try:
        device = Device.objects.select_related("user").get(id=device_id)
    except (Device.DoesNotExist, ValueError):
        return None

    if not device.is_active:
        return None

    expected_hash = Device.hash_token(raw_secret)
    if device.token_hash != expected_hash:
        return None

    device.mark_seen()
    return device
