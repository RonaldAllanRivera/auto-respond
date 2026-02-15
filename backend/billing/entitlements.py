from datetime import datetime, timedelta, timezone as dt_timezone

import stripe
from django.conf import settings
from django.utils import timezone

from .models import BillingPlan, StripeSubscription


_ACTIVE_STATUSES = {"active", "trialing"}
_STRIPE_REFRESH_TTL = timedelta(minutes=1)


def _stripe_init() -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _sync_latest_subscription_from_stripe(user, current_sub: StripeSubscription | None) -> StripeSubscription | None:
    customer = getattr(user, "stripe_customer", None)
    if not customer or not customer.stripe_customer_id:
        return current_sub

    if current_sub and timezone.now() - current_sub.updated_at < _STRIPE_REFRESH_TTL:
        return current_sub

    _stripe_init()
    try:
        result = stripe.Subscription.list(customer=customer.stripe_customer_id, status="all", limit=5)
    except Exception:
        return current_sub

    subs = result.get("data", []) if isinstance(result, dict) else []
    if not subs:
        return current_sub

    latest = max(subs, key=lambda s: s.get("created", 0))

    obj, _ = StripeSubscription.objects.get_or_create(user=user)
    obj.stripe_subscription_id = latest.get("id") or obj.stripe_subscription_id
    obj.status = latest.get("status", "") or obj.status
    obj.cancel_at_period_end = bool(latest.get("cancel_at_period_end", False))

    items = latest.get("items", {}).get("data", []) if isinstance(latest.get("items"), dict) else []
    if items:
        price = items[0].get("price") or {}
        obj.stripe_price_id = price.get("id", "") or obj.stripe_price_id

    period_end = latest.get("current_period_end")
    if isinstance(period_end, int):
        obj.current_period_end = datetime.fromtimestamp(period_end, tz=dt_timezone.utc)

    obj.save(
        update_fields=[
            "stripe_subscription_id",
            "stripe_price_id",
            "status",
            "cancel_at_period_end",
            "current_period_end",
            "updated_at",
        ]
    )
    return obj


def billing_is_configured() -> bool:
    plan = BillingPlan.get_solo()
    return bool(
        settings.STRIPE_SECRET_KEY
        and plan.active
        and plan.stripe_monthly_price_id
    )


def user_has_active_subscription(user) -> bool:
    if not billing_is_configured():
        return True

    sub = getattr(user, "stripe_subscription", None)
    if sub and sub.status in _ACTIVE_STATUSES:
        return True

    sub = _sync_latest_subscription_from_stripe(user, sub)
    if not sub:
        return False

    return sub.status in _ACTIVE_STATUSES
