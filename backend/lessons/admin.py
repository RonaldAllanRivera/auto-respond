from django.contrib import admin

from .models import Lesson, QuestionAnswer, TranscriptChunk


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "created_at")
    search_fields = ("title", "user__email", "user__username")


@admin.register(TranscriptChunk)
class TranscriptChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "lesson", "speaker", "created_at")
    search_fields = ("lesson__title", "speaker")


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "lesson", "created_at")
    search_fields = ("user__email", "user__username", "question")
