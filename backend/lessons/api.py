"""
API views for caption ingestion and question submission.

All endpoints require device token authentication via X-Device-Token header.
"""

import hashlib
import json
from datetime import date

from django.db import IntegrityError
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from devices.auth import require_device_token

from .models import Lesson, QuestionAnswer, TranscriptChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_caption(speaker: str, text: str) -> str:
    """SHA-256 hash of speaker + text for server-side dedupe."""
    raw = f"{speaker.strip().lower()}|{text.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_or_create_lesson(user, meeting_id: str, meeting_title: str, meeting_date: date | None = None) -> Lesson:
    """
    Get or create a lesson for the given meeting.

    If meeting_id is provided, dedup by (user, meeting_id, meeting_date).
    If meeting_id is empty, always create a new lesson.
    """
    today = meeting_date or timezone.now().date()

    if meeting_id:
        lesson, _ = Lesson.objects.get_or_create(
            user=user,
            meeting_id=meeting_id,
            meeting_date=today,
            defaults={"title": meeting_title or f"Meeting {today.isoformat()}"},
        )
        return lesson

    return Lesson.objects.create(
        user=user,
        title=meeting_title or f"Meeting {today.isoformat()}",
        meeting_date=today,
    )


# ---------------------------------------------------------------------------
# POST /api/captions/
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
@require_device_token
def api_captions(request: HttpRequest) -> JsonResponse:
    """
    Ingest a caption event from the extension.

    Request body (JSON):
        {
            "meeting_id": "abc-defg-hij",       // from Meet URL
            "meeting_title": "Math Class",       // from Meet page title
            "speaker": "Teacher",
            "text": "What is 2 + 2?",
            "captured_at": "2026-02-13T12:30:00Z"  // optional ISO timestamp
        }

    Optional:
        "lesson_id": 123  // manual lesson selection (overrides auto-create)

    Response:
        {"lesson_id": 123, "chunk_id": 456, "created": true}
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    text = body.get("text", "").strip()
    if not text:
        return JsonResponse({"error": "Missing caption text"}, status=400)

    speaker = body.get("speaker", "").strip()[:255]
    meeting_id = body.get("meeting_id", "").strip()
    meeting_title = body.get("meeting_title", "").strip()
    lesson_id = body.get("lesson_id")

    # Parse optional captured_at
    captured_at = None
    if body.get("captured_at"):
        captured_at = parse_datetime(body["captured_at"])

    # Resolve lesson: manual selection or auto-create
    if lesson_id:
        try:
            lesson = Lesson.objects.get(id=lesson_id, user=request.user)
        except Lesson.DoesNotExist:
            return JsonResponse({"error": "Lesson not found"}, status=404)
    else:
        lesson = _get_or_create_lesson(request.user, meeting_id, meeting_title)

    # Server-side dedupe via content_hash
    content_hash = _hash_caption(speaker, text)

    try:
        chunk = TranscriptChunk.objects.create(
            lesson=lesson,
            speaker=speaker,
            text=text,
            content_hash=content_hash,
            captured_at=captured_at,
        )
        created = True
    except IntegrityError:
        # Duplicate caption — already stored
        chunk = TranscriptChunk.objects.filter(lesson=lesson, content_hash=content_hash).first()
        created = False

    return JsonResponse({
        "lesson_id": lesson.id,
        "chunk_id": chunk.id if chunk else None,
        "created": created,
    })


# ---------------------------------------------------------------------------
# POST /api/questions/
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
@require_device_token
def api_questions(request: HttpRequest) -> JsonResponse:
    """
    Submit a detected question for AI answering.

    Request body (JSON):
        {
            "question": "What is photosynthesis?",
            "context": "The teacher was explaining how plants make food...",
            "meeting_id": "abc-defg-hij",
            "meeting_title": "Biology Class",
            "lesson_id": 123               // optional, overrides auto-create
        }

    Response:
        {"question_id": 789, "lesson_id": 123}

    The answer will be generated asynchronously in Phase 4 (AI answering).
    For now, this endpoint stores the question and returns its ID.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    question_text = body.get("question", "").strip()
    if not question_text:
        return JsonResponse({"error": "Missing question text"}, status=400)

    context = body.get("context", "").strip()
    meeting_id = body.get("meeting_id", "").strip()
    meeting_title = body.get("meeting_title", "").strip()
    lesson_id = body.get("lesson_id")

    # Resolve lesson
    if lesson_id:
        try:
            lesson = Lesson.objects.get(id=lesson_id, user=request.user)
        except Lesson.DoesNotExist:
            return JsonResponse({"error": "Lesson not found"}, status=404)
    elif meeting_id:
        lesson = _get_or_create_lesson(request.user, meeting_id, meeting_title)
    else:
        lesson = None

    # Store the question (answer will be filled by Phase 4 AI answering)
    qa = QuestionAnswer.objects.create(
        user=request.user,
        lesson=lesson,
        question=question_text,
        answer="",  # placeholder until AI answering is implemented
    )

    # Also store the context as a transcript chunk if provided
    if context and lesson:
        content_hash = _hash_caption("", context)
        try:
            TranscriptChunk.objects.create(
                lesson=lesson,
                speaker="",
                text=context,
                content_hash=content_hash,
            )
        except IntegrityError:
            pass  # already stored

    return JsonResponse({
        "question_id": qa.id,
        "lesson_id": lesson.id if lesson else None,
    })
