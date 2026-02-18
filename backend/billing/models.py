from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

import stripe


class BillingPlan(models.Model):
    name = models.CharField(max_length=64, default="Monthly")
    currency = models.CharField(max_length=8, default="usd")

    monthly_price_cents = models.PositiveIntegerField(default=0)
    monthly_discount_percent = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(90)],
    )

    stripe_monthly_price_id = models.CharField(max_length=255, blank=True, default="")
    active = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls) -> "BillingPlan":
        obj, _ = cls.objects.get_or_create(
            id=1,
            defaults={
                "name": "Monthly",
                "currency": "usd",
                "monthly_price_cents": 0,
                "monthly_discount_percent": 20,
                "stripe_monthly_price_id": "",
                "active": True,
            },
        )
        return obj

    @property
    def weekly_equivalent_cents(self) -> int:
        return int(round(self.monthly_price_cents / 4.0))

    @property
    def daily_equivalent_cents(self) -> int:
        return int(round(self.monthly_price_cents / 30.0))

    @property
    def undiscounted_monthly_price_cents(self) -> int:
        if self.monthly_discount_percent <= 0:
            return self.monthly_price_cents
        frac = 1.0 - (self.monthly_discount_percent / 100.0)
        if frac <= 0:
            return self.monthly_price_cents
        return int(round(self.monthly_price_cents / frac))

    def clean(self) -> None:
        super().clean()
        value = (self.stripe_monthly_price_id or "").strip()
        if value and not value.startswith("price_"):
            raise ValidationError(
                {
                    "stripe_monthly_price_id": (
                        "Must be a Stripe Price ID (price_...), not a Product ID (prod_...) or numeric amount."
                    )
                }
            )


class CouponCode(models.Model):
    code = models.CharField(max_length=64, unique=True)
    stripe_promotion_code_id = models.CharField(max_length=255, blank=True, default="")
    active = models.BooleanField(default=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    redeemed_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        if self.stripe_promotion_code_id:
            self.stripe_promotion_code_id = self.stripe_promotion_code_id.strip()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()

        code = (self.code or "").strip()
        if not code:
            raise ValidationError({"code": "Coupon code cannot be empty."})

        promo_id = (self.stripe_promotion_code_id or "").strip()
        if promo_id:
            if promo_id.startswith("promo_") or promo_id.startswith("coupon_"):
                pass
            elif settings.STRIPE_SECRET_KEY:
                stripe.api_key = settings.STRIPE_SECRET_KEY

                is_valid = False
                try:
                    stripe.PromotionCode.retrieve(promo_id)
                    is_valid = True
                except Exception:
                    pass

                if not is_valid:
                    try:
                        stripe.Coupon.retrieve(promo_id)
                        is_valid = True
                    except Exception:
                        pass

                if not is_valid:
                    raise ValidationError(
                        {
                            "stripe_promotion_code_id": (
                                "Enter a valid Stripe Promotion Code ID or Coupon ID. "
                                "In Stripe: create a Promotion Code under the Coupon (Promotion codes → +), "
                                "or paste the Coupon ID directly."
                            )
                        }
                    )

        if self.max_redemptions is not None and self.max_redemptions <= 0:
            raise ValidationError({"max_redemptions": "Must be a positive integer."})

    def is_redeemable(self) -> tuple[bool, str]:
        if not self.active:
            return False, "Coupon is inactive."

        now = timezone.now()
        if self.expires_at and now >= self.expires_at:
            return False, "Coupon is expired."

        if self.max_redemptions is not None and self.redeemed_count >= self.max_redemptions:
            return False, "Coupon has reached its redemption limit."

        if not (self.stripe_promotion_code_id or "").strip():
            return False, "Coupon is misconfigured."

        return True, ""


class StripeCustomer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stripe_customer")
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StripeSubscription(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stripe_subscription")

    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    stripe_price_id = models.CharField(max_length=255, blank=True, default="")

    status = models.CharField(max_length=32, blank=True, default="")
    cancel_at_period_end = models.BooleanField(default=False)
    current_period_end = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StripeEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
