import json
from datetime import datetime, timezone as dt_timezone

import stripe
from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.db import transaction
from django.db.models import F
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .entitlements import billing_is_configured, user_has_active_subscription
from .models import BillingPlan, CouponCode, StripeCustomer, StripeEvent, StripeSubscription


def _format_money(*, cents: int, currency: str) -> str:
    amount = cents / 100.0
    if (currency or "").lower() == "usd":
        return f"${amount:,.2f}"
    return f"{amount:,.2f} {(currency or '').upper()}".strip()


def _stripe_init() -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _resolve_stripe_discount(discount_id: str) -> tuple[dict, str]:
    value = (discount_id or "").strip()
    if not value:
        return {}, ""

    if value.startswith("coupon_"):
        return {"coupon": value}, ""
    if value.startswith("promo_"):
        return {"promotion_code": value}, ""

    if not settings.STRIPE_SECRET_KEY:
        return {"promotion_code": value}, ""

    _stripe_init()

    try:
        stripe.PromotionCode.retrieve(value)
        return {"promotion_code": value}, ""
    except Exception:
        pass

    try:
        stripe.Coupon.retrieve(value)
        return {"coupon": value}, ""
    except Exception:
        pass

    return {}, "Invalid Stripe coupon/promotion code configuration."


def _normalize_coupon_code(value: str) -> str:
    return (value or "").strip().upper()


def _subscribe_context(*, plan: BillingPlan, billing_enabled: bool, subscribed: bool, coupon_code: str = "", coupon_error: str = "") -> dict:
    display_monthly_cents = plan.monthly_price_cents if plan.monthly_price_cents > 0 else 1500
    display_weekly_cents = int(round(display_monthly_cents / 4.0))
    display_daily_cents = int(round(display_monthly_cents / 30.0))

    return {
        "plan": plan,
        "billing_enabled": billing_enabled,
        "subscribed": subscribed,
        "display_price_monthly": _format_money(cents=display_monthly_cents, currency=plan.currency),
        "display_price_weekly": _format_money(cents=display_weekly_cents, currency=plan.currency),
        "display_price_daily": _format_money(cents=display_daily_cents, currency=plan.currency),
        "coupon_code": coupon_code,
        "coupon_error": coupon_error,
    }


def _get_or_create_customer(user) -> StripeCustomer:
    obj, _ = StripeCustomer.objects.get_or_create(user=user)
    if obj.stripe_customer_id:
        return obj

    _stripe_init()
    customer = stripe.Customer.create(
        email=user.email or None,
        metadata={"user_id": str(user.id)},
    )
    obj.stripe_customer_id = customer["id"]
    obj.save(update_fields=["stripe_customer_id", "updated_at"])
    return obj


def _sync_subscription_for_user(user, sub: dict) -> StripeSubscription:
    obj, _ = StripeSubscription.objects.get_or_create(user=user)

    obj.stripe_subscription_id = sub.get("id") or obj.stripe_subscription_id
    obj.status = sub.get("status", "") or obj.status
    obj.cancel_at_period_end = bool(sub.get("cancel_at_period_end", False))

    items = sub.get("items", {}).get("data", []) if isinstance(sub.get("items"), dict) else []
    if items:
        price = items[0].get("price") or {}
        obj.stripe_price_id = price.get("id", "") or obj.stripe_price_id

    period_end = sub.get("current_period_end")
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


@login_required
def subscribe_view(request: HttpRequest) -> HttpResponse:
    plan = BillingPlan.get_solo()
    billing_enabled = billing_is_configured()
    subscribed = user_has_active_subscription(request.user)
    return render(
        request,
        "billing/subscribe.html",
        _subscribe_context(plan=plan, billing_enabled=billing_enabled, subscribed=subscribed),
    )


@login_required
@require_POST
def create_checkout_session(request: HttpRequest) -> HttpResponse:
    plan = BillingPlan.get_solo()
    if not billing_is_configured():
        return redirect("billing_subscribe")

    if user_has_active_subscription(request.user):
        return redirect("billing_subscribe")

    price_id = plan.stripe_monthly_price_id.strip()
    if not price_id:
        return redirect("billing_subscribe")
    if not price_id.startswith("price_"):
        return HttpResponseBadRequest(
            "Billing plan misconfigured: stripe_monthly_price_id must be a Stripe Price ID (price_...)."
        )

    customer = _get_or_create_customer(request.user)

    coupon_code = _normalize_coupon_code(request.POST.get("coupon_code", ""))
    discount_id = ""
    if coupon_code:
        with transaction.atomic():
            coupon = (
                CouponCode.objects.select_for_update()
                .filter(code=coupon_code)
                .first()
            )
            if not coupon:
                return render(
                    request,
                    "billing/subscribe.html",
                    _subscribe_context(
                        plan=plan,
                        billing_enabled=True,
                        subscribed=False,
                        coupon_code=coupon_code,
                        coupon_error="Invalid coupon code.",
                    ),
                )

            ok, reason = coupon.is_redeemable()
            if not ok:
                return render(
                    request,
                    "billing/subscribe.html",
                    _subscribe_context(
                        plan=plan,
                        billing_enabled=True,
                        subscribed=False,
                        coupon_code=coupon_code,
                        coupon_error=reason,
                    ),
                )

            discount_id = coupon.stripe_promotion_code_id.strip()

    _stripe_init()
    success_url = request.build_absolute_uri(reverse("billing_success"))
    cancel_url = request.build_absolute_uri(reverse("billing_cancel"))

    session_params = {
        "mode": "subscription",
        "customer": customer.stripe_customer_id,
        "line_items": [{"price": price_id, "quantity": 1}],
        "allow_promotion_codes": False,
        "client_reference_id": str(request.user.id),
        "metadata": {"user_id": str(request.user.id)},
        "success_url": success_url,
        "cancel_url": cancel_url,
    }

    if discount_id:
        discount_param, discount_error = _resolve_stripe_discount(discount_id)
        if discount_error:
            return render(
                request,
                "billing/subscribe.html",
                _subscribe_context(
                    plan=plan,
                    billing_enabled=True,
                    subscribed=False,
                    coupon_code=coupon_code,
                    coupon_error=(
                        "Coupon is misconfigured in admin. "
                        "Use a Stripe Promotion Code ID (from Coupon → Promotion codes) or a Stripe Coupon ID."
                    ),
                ),
            )

        session_params["discounts"] = [discount_param]
        session_params["metadata"]["coupon_code"] = coupon_code

    session = stripe.checkout.Session.create(
        **session_params,
    )

    return redirect(session.url)


@login_required
@require_POST
def create_billing_portal_session(request: HttpRequest) -> HttpResponse:
    if not settings.STRIPE_SECRET_KEY:
        return redirect("billing_subscribe")

    customer = _get_or_create_customer(request.user)

    _stripe_init()
    return_url = request.build_absolute_uri("/")
    portal = stripe.billing_portal.Session.create(
        customer=customer.stripe_customer_id,
        return_url=return_url,
    )
    return redirect(portal.url)


@login_required
def billing_success(request: HttpRequest) -> HttpResponse:
    return render(request, "billing/success.html")


@login_required
def billing_cancel(request: HttpRequest) -> HttpResponse:
    return render(request, "billing/cancel.html")


@csrf_exempt
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=500)

    payload = request.body
    sig_header = request.headers.get("Stripe-Signature", "")

    _stripe_init()
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    evt, created = StripeEvent.objects.get_or_create(
        event_id=event["id"],
        defaults={"event_type": event.get("type", "")},
    )
    if not created:
        return HttpResponse(status=200)

    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        if session.get("mode") != "subscription":
            return HttpResponse(status=200)

        user_id = session.get("client_reference_id") or (session.get("metadata") or {}).get("user_id")
        if not user_id:
            return HttpResponse(status=200)

        User = get_user_model()
        try:
            user = User.objects.get(id=int(user_id))
        except (User.DoesNotExist, ValueError, TypeError):
            return HttpResponse(status=200)

        customer_id = session.get("customer")
        if customer_id:
            cust, _ = StripeCustomer.objects.get_or_create(user=user)
            if cust.stripe_customer_id != customer_id:
                cust.stripe_customer_id = customer_id
                cust.save(update_fields=["stripe_customer_id", "updated_at"])

        sub_id = session.get("subscription")
        if sub_id:
            sub = stripe.Subscription.retrieve(sub_id)
            _sync_subscription_for_user(user, sub)

        meta = session.get("metadata") or {}
        coupon_code = _normalize_coupon_code(meta.get("coupon_code", ""))
        if coupon_code:
            with transaction.atomic():
                coupon = (
                    CouponCode.objects.select_for_update()
                    .filter(code=coupon_code)
                    .first()
                )
                if coupon:
                    ok, _ = coupon.is_redeemable()
                    if ok:
                        CouponCode.objects.filter(id=coupon.id).update(
                            redeemed_count=F("redeemed_count") + 1
                        )

        return HttpResponse(status=200)

    if event_type.startswith("customer.subscription."):
        sub = event.get("data", {}).get("object", {})
        customer_id = sub.get("customer")
        if not customer_id:
            return HttpResponse(status=200)

        cust = StripeCustomer.objects.filter(stripe_customer_id=customer_id).select_related("user").first()
        if not cust:
            return HttpResponse(status=200)

        _sync_subscription_for_user(cust.user, sub)
        return HttpResponse(status=200)

    if event_type in {"invoice.paid", "invoice.payment_failed"}:
        invoice = event.get("data", {}).get("object", {})
        customer_id = invoice.get("customer")
        sub_id = invoice.get("subscription")
        if not customer_id or not sub_id:
            return HttpResponse(status=200)

        cust = StripeCustomer.objects.filter(stripe_customer_id=customer_id).select_related("user").first()
        if not cust:
            return HttpResponse(status=200)

        sub = stripe.Subscription.retrieve(sub_id)
        _sync_subscription_for_user(cust.user, sub)
        return HttpResponse(status=200)

    return HttpResponse(status=200)
