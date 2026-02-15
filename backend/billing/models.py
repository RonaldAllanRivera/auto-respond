from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


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
