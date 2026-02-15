from django.urls import path

from .views import (
    billing_cancel,
    billing_success,
    create_billing_portal_session,
    create_checkout_session,
    stripe_webhook,
    subscribe_view,
)

urlpatterns = [
    path("subscribe/", subscribe_view, name="billing_subscribe"),
    path("checkout/", create_checkout_session, name="billing_checkout"),
    path("portal/", create_billing_portal_session, name="billing_portal"),
    path("webhook/", stripe_webhook, name="stripe_webhook"),
    path("success/", billing_success, name="billing_success"),
    path("cancel/", billing_cancel, name="billing_cancel"),
]
