from django.contrib import admin

from .models import AppSettings, BillingPlan, Install, Lesson, QuestionAnswer, TranscriptChunk


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "source", "meeting_code", "meeting_started_at", "created_at")
    search_fields = ("title", "meeting_code")
    list_filter = ("source",)


@admin.register(TranscriptChunk)
class TranscriptChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "lesson", "source", "speaker", "captured_at", "created_at")
    search_fields = ("text", "speaker")
    list_filter = ("source",)


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "lesson", "model", "latency_ms", "created_at")
    search_fields = ("question", "answer")


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "grade_level", "max_sentences", "updated_at")


@admin.register(Install)
class InstallAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "created_at", "last_seen_at")
    search_fields = ("label",)


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
