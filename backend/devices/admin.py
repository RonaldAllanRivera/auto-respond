from django.contrib import admin

from .models import Device, DevicePairingCode


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "label", "created_at", "last_seen_at", "revoked_at")
    list_filter = ("revoked_at",)
    search_fields = ("user__email", "user__username", "label")


@admin.register(DevicePairingCode)
class DevicePairingCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "user", "created_at", "expires_at", "used_at")
    search_fields = ("code", "user__email", "user__username")
