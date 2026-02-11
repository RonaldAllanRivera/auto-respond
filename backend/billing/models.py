from django.core.validators import MaxValueValidator, MinValueValidator
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


class CouponCode(models.Model):
    code = models.CharField(max_length=64, unique=True)
    stripe_promotion_code_id = models.CharField(max_length=255, blank=True, default="")
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
