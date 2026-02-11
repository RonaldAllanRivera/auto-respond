import uuid

from django.db import models
from django.utils import timezone


class Lesson(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        MEET_AUTO = "meet_auto", "Google Meet (Auto)"

    title = models.CharField(max_length=255)
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.MANUAL)

    meeting_code = models.CharField(max_length=64, blank=True, default="")
    meeting_started_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class TranscriptChunk(models.Model):
    class Source(models.TextChoices):
        MEET_CAPTION = "meet_caption", "Google Meet Caption"
        OCR_IMAGE = "ocr_image", "OCR Image"
        MANUAL = "manual", "Manual"

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="transcript_chunks")
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.MANUAL)

    speaker = models.CharField(max_length=255, blank=True, default="")
    text = models.TextField()

    captured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.lesson_id}: {self.text[:60]}"


class QuestionAnswer(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True, related_name="qas")

    question = models.TextField()
    answer = models.TextField()

    model = models.CharField(max_length=128, blank=True, default="")
    latency_ms = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


class AppSettings(models.Model):
    grade_level = models.IntegerField(default=3)
    max_sentences = models.IntegerField(default=2)

    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls) -> "AppSettings":
        obj, _ = cls.objects.get_or_create(id=1, defaults={"grade_level": 3, "max_sentences": 2})
        return obj


class Install(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def mark_seen(self) -> None:
        self.last_seen_at = timezone.now()
        self.save(update_fields=["last_seen_at"])
