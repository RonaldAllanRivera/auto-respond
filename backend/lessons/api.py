"""
API views for caption ingestion and question submission.

All endpoints require device token authentication via X-Device-Token header.
Used by the desktop app (screenshot OCR capture tool).
"""

import hashlib
import json
import time
from datetime import date

from django.conf import settings
from django.db import IntegrityError
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import SubscriberProfile
from billing.entitlements import user_has_active_subscription
from devices.auth import require_device_token

from .ai import answer_question, answer_question_streaming
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

    Called by the desktop app after OCR + question detection.

    Request body (JSON):
        {
            "question": "What is photosynthesis?",
            "context": "The teacher was explaining how plants make food...",
            "meeting_id": "abc-defg-hij",
            "meeting_title": "Biology Class",
            "lesson_id": 123               // optional, overrides auto-create
        }

    Response:
        {"question_id": 789, "lesson_id": 123, "answer": "...", "latency_ms": 1234}
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
        lesson = _get_or_create_lesson(request.user, "", meeting_title)

    # Store the context as a transcript chunk if provided
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

    # Get user preferences for AI prompt
    profile = SubscriberProfile.get_for_user(request.user)

    if not user_has_active_subscription(request.user):
        return JsonResponse({"error": "Subscription required"}, status=403)

    # Gather recent transcript context from the lesson
    full_context = context
    if lesson:
        recent_chunks = lesson.transcript_chunks.order_by("-created_at")[:10]
        chunk_texts = [c.text for c in reversed(recent_chunks)]
        full_context = "\n".join(chunk_texts)

    # Call OpenAI synchronously
    ai_result = answer_question(
        question=question_text,
        context=full_context,
        grade_level=profile.grade_level,
        max_sentences=profile.max_sentences,
    )

    # Store the question + answer
    qa = QuestionAnswer.objects.create(
        user=request.user,
        lesson=lesson,
        question=question_text,
        answer=ai_result["answer"],
        model=ai_result["model"],
        latency_ms=ai_result["latency_ms"],
    )

    return JsonResponse({
        "question_id": qa.id,
        "lesson_id": lesson.id if lesson else None,
        "answer": ai_result["answer"],
        "latency_ms": ai_result["latency_ms"],
    })


# ---------------------------------------------------------------------------
# GET /api/questions/<id>/stream/ — SSE streaming for dashboard
# ---------------------------------------------------------------------------


@csrf_exempt
def api_question_stream(request: HttpRequest, question_id: int) -> StreamingHttpResponse:
    """
    SSE endpoint that streams the AI answer for a question.

    Used by the Django dashboard to display live-streaming answers.
    Requires the user to be logged in (session auth).
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        qa = QuestionAnswer.objects.get(id=question_id, user=request.user)
    except QuestionAnswer.DoesNotExist:
        return JsonResponse({"error": "Question not found"}, status=404)

    # If already answered, return the stored answer as a single SSE event
    if qa.answer:
        def already_answered():
            yield f"data: {json.dumps({'token': qa.answer, 'done': True})}\n\n"
        return StreamingHttpResponse(
            already_answered(),
            content_type="text/event-stream",
        )

    if not user_has_active_subscription(request.user):
        def not_subscribed():
            yield f"data: {json.dumps({'error': 'subscription_required', 'done': True})}\n\n"
        return StreamingHttpResponse(
            not_subscribed(),
            content_type="text/event-stream",
        )

    # Stream from OpenAI
    profile = SubscriberProfile.get_for_user(request.user)

    full_context = ""
    if qa.lesson:
        recent_chunks = qa.lesson.transcript_chunks.order_by("-created_at")[:10]
        chunk_texts = [c.text for c in reversed(recent_chunks)]
        full_context = "\n".join(chunk_texts)

    def stream_tokens():
        full_answer = []
        start = time.time()
        for token in answer_question_streaming(
            question=qa.question,
            context=full_context,
            grade_level=profile.grade_level,
            max_sentences=profile.max_sentences,
        ):
            full_answer.append(token)
            yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"

        # Persist the complete answer
        answer_text = "".join(full_answer)
        latency_ms = int((time.time() - start) * 1000)
        qa.answer = answer_text
        qa.model = settings.OPENAI_MODEL
        qa.latency_ms = latency_ms
        qa.save(update_fields=["answer", "model", "latency_ms"])

        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"

    response = StreamingHttpResponse(stream_tokens(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
