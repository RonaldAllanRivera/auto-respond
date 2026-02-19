import json
import secrets

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from billing.entitlements import billing_is_configured, user_has_active_subscription

from .models import Device, DevicePairingCode
from .tokens import issue_token


# ---------------------------------------------------------------------------
# Dashboard views (authenticated via session)
# ---------------------------------------------------------------------------


@login_required
def devices_view(request: HttpRequest) -> HttpResponse:
    """List paired devices and show active pairing code (if any)."""
    billing_enforced = billing_is_configured()
    subscription_active = user_has_active_subscription(request.user)
    auto_revoked_count = 0

    if billing_enforced and not subscription_active:
        now = timezone.now()
        auto_revoked_count = Device.objects.filter(user=request.user, revoked_at__isnull=True).update(revoked_at=now)
        DevicePairingCode.objects.filter(
            user=request.user,
            used_at__isnull=True,
            expires_at__gt=now,
        ).update(expires_at=now)

    devices = Device.objects.filter(user=request.user).order_by("-created_at")

    # Find an active (unused + unexpired) pairing code
    active_code = None
    if not billing_enforced or subscription_active:
        active_code = (
            DevicePairingCode.objects.filter(user=request.user, used_at__isnull=True, expires_at__gt=timezone.now())
            .order_by("-created_at")
            .first()
        )

    return render(
        request,
        "devices/devices.html",
        {
            "devices": devices,
            "active_code": active_code,
            "billing_enforced": billing_enforced,
            "subscription_active": subscription_active,
            "auto_revoked_count": auto_revoked_count,
            "desktop_download_url": settings.DESKTOP_DOWNLOAD_URL,
        },
    )


@login_required
@require_POST
def generate_pairing_code(request: HttpRequest) -> HttpResponse:
    """Generate a new pairing code for the logged-in user."""
    if billing_is_configured() and not user_has_active_subscription(request.user):
        return redirect("billing_subscribe")

    DevicePairingCode.generate(request.user)
    return redirect("devices")


@login_required
@require_POST
def revoke_device(request: HttpRequest, device_id: str) -> HttpResponse:
    """Revoke a paired device."""
    device = get_object_or_404(Device, id=device_id, user=request.user)
    device.revoke()
    return redirect("devices")


# ---------------------------------------------------------------------------
# Extension API (no session — uses pairing code to get a device token)
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def api_pair_device(request: HttpRequest) -> JsonResponse:
    """
    Exchange a pairing code for a device token.

    Request body (JSON):
        {"code": "AB12CD34", "label": "Chrome on laptop"}

    Response (JSON):
        {"device_id": "...", "token": "<device_id>:<secret>"}
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    code_str = body.get("code", "").strip().upper()
    label = body.get("label", "").strip()[:255]

    if not code_str:
        return JsonResponse({"error": "Missing pairing code"}, status=400)

    try:
        pairing_code = DevicePairingCode.objects.select_related("user").get(code=code_str)
    except DevicePairingCode.DoesNotExist:
        return JsonResponse({"error": "Invalid pairing code"}, status=404)

    if not pairing_code.is_valid():
        return JsonResponse({"error": "Pairing code expired or already used"}, status=410)

    if billing_is_configured() and not user_has_active_subscription(pairing_code.user):
        now = timezone.now()
        Device.objects.filter(user=pairing_code.user, revoked_at__isnull=True).update(revoked_at=now)
        return JsonResponse({"error": "Subscription required"}, status=403)

    # Mark code as used
    pairing_code.used_at = timezone.now()
    pairing_code.save(update_fields=["used_at"])

    # Create device and issue token
    device = Device.objects.create(
        user=pairing_code.user,
        label=label or "Desktop App",
    )
    raw_token = issue_token(device)

    return JsonResponse({"device_id": str(device.id), "token": raw_token})
