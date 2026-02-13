from django.urls import path

from .views import api_pair_device, devices_view, generate_pairing_code, revoke_device

urlpatterns = [
    path("devices/", devices_view, name="devices"),
    path("devices/pair/", generate_pairing_code, name="generate_pairing_code"),
    path("devices/<str:device_id>/revoke/", revoke_device, name="revoke_device"),
    path("api/devices/pair/", api_pair_device, name="api_pair_device"),
]
