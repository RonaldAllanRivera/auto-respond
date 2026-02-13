"""
Device token authentication decorator for API views.

Usage:
    @require_device_token
    def my_api_view(request):
        # request.device and request.user are set
        ...
"""

import functools

from django.http import JsonResponse

from .tokens import verify_token


def require_device_token(view_func):
    """Decorator that authenticates via X-Device-Token header."""

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        raw_token = request.headers.get("X-Device-Token", "")
        if not raw_token:
            return JsonResponse({"error": "Missing X-Device-Token header"}, status=401)

        device = verify_token(raw_token)
        if device is None:
            return JsonResponse({"error": "Invalid or revoked device token"}, status=401)

        request.device = device
        request.user = device.user
        return view_func(request, *args, **kwargs)

    return wrapper
