from django.contrib import admin

from .models import BillingPlan, CouponCode


@admin.register(BillingPlan)
class BillingPlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "currency",
        "monthly_price_cents",
        "monthly_discount_percent",
        "stripe_monthly_price_id",
        "active",
        "updated_at",
    )
    list_filter = ("active", "currency")


@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "active", "stripe_promotion_code_id", "created_at")
    list_filter = ("active",)
    search_fields = ("code",)
