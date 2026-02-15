from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("billing/", include("billing.urls")),
    path("", include("lessons.urls")),
    path("", include("accounts.urls")),
    path("", include("devices.urls")),
]
