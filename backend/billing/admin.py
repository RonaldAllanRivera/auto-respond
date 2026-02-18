from django.contrib import admin

from .models import BillingPlan, CouponCode, StripeCustomer, StripeEvent, StripeSubscription


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
    list_display = (
        "id",
        "code",
        "active",
        "stripe_promotion_code_id",
        "expires_at",
        "max_redemptions",
        "redeemed_count",
        "created_at",
    )
    list_filter = ("active",)
    search_fields = ("code",)


@admin.register(StripeCustomer)
class StripeCustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "stripe_customer_id", "created_at", "updated_at")
    search_fields = ("user__username", "user__email", "stripe_customer_id")


@admin.register(StripeSubscription)
class StripeSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "stripe_subscription_id",
        "stripe_price_id",
        "status",
        "cancel_at_period_end",
        "current_period_end",
        "updated_at",
    )
    search_fields = ("user__username", "user__email", "stripe_subscription_id", "stripe_price_id")
    list_filter = ("status", "cancel_at_period_end")


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_id", "event_type", "created_at")
    search_fields = ("event_id", "event_type")
