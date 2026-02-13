import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Device(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    label = models.CharField(max_length=255, blank=True, default="")
    token_hash = models.CharField(max_length=64, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def mark_seen(self) -> None:
        self.last_seen_at = timezone.now()
        self.save(update_fields=["last_seen_at"])

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def revoke(self) -> None:
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def __str__(self) -> str:
        status = "active" if self.is_active else "revoked"
        return f"{self.label or 'Unnamed'} ({status})"


class DevicePairingCode(models.Model):
    EXPIRY_MINUTES = 10

    code = models.CharField(max_length=16, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pairing_codes")

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def is_valid(self) -> bool:
        if self.used_at is not None:
            return False
        return timezone.now() < self.expires_at

    @classmethod
    def generate(cls, user) -> "DevicePairingCode":
        code = secrets.token_hex(4).upper()  # 8-char hex code
        expires_at = timezone.now() + timedelta(minutes=cls.EXPIRY_MINUTES)
        return cls.objects.create(user=user, code=code, expires_at=expires_at)

    def __str__(self) -> str:
        return f"{self.code} ({'valid' if self.is_valid() else 'expired/used'})"
