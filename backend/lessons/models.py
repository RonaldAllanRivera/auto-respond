from django.conf import settings
from django.db import models


class Lesson(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)


class TranscriptChunk(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="transcript_chunks")
    speaker = models.CharField(max_length=255, blank=True, default="")
    text = models.TextField()

    captured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class QuestionAnswer(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="qas", null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="qas")

    question = models.TextField()
    answer = models.TextField()

    model = models.CharField(max_length=128, blank=True, default="")
    latency_ms = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
