from django.contrib import admin

from .models import Lesson, QuestionAnswer, TranscriptChunk


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "meeting_id", "meeting_date", "created_at")
    list_filter = ("meeting_date",)
    search_fields = ("title", "meeting_id", "user__email", "user__username")


@admin.register(TranscriptChunk)
class TranscriptChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "lesson", "speaker", "content_hash_short", "created_at")
    search_fields = ("lesson__title", "speaker", "text")

    @admin.display(description="Hash")
    def content_hash_short(self, obj):
        return obj.content_hash[:12] + "…" if obj.content_hash else ""


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "lesson", "created_at")
    search_fields = ("user__email", "user__username", "question")
