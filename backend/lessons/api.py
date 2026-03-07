"""
API views for caption ingestion, question submission, and document upload.

Device token endpoints (X-Device-Token header):
- POST /api/captions/
- POST /api/questions/
- GET /api/lessons/list/

Session auth endpoints (login required):
- POST /api/lessons/upload/
- GET /api/questions/<id>/stream/
"""

import hashlib
import json
import time
from datetime import date

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import IntegrityError
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import SubscriberProfile
from billing.entitlements import user_has_active_subscription
from devices.auth import require_device_token

from .ai import answer_question, answer_question_streaming
from .document_processor import (
    MAX_FILES_PER_UPLOAD,
    MAX_TOTAL_SIZE_MB,
    create_lesson_from_uploads,
)
from .models import Lesson, QuestionAnswer, TranscriptChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_caption(speaker: str, text: str) -> str:
    """SHA-256 hash of speaker + text for server-side dedupe."""
    raw = f"{speaker.strip().lower()}|{text.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_or_create_lesson(user, meeting_id: str, meeting_title: str, meeting_date: date | None = None, first_text: str = "") -> Lesson:
    """
    Get or create a lesson for the given meeting.

    If meeting_id is provided, dedup by (user, meeting_id, meeting_date).
    If meeting_id is empty, always create a new lesson.
    
    If meeting_title is empty and first_text is provided, generate a title from the text.
    """
    from .document_processor import generate_lesson_name
    
    today = meeting_date or timezone.now().date()
    
    # Generate title from first_text if no meeting_title provided
    if not meeting_title and first_text:
        meeting_title = generate_lesson_name(first_text[:500])  # Use first 500 chars for title generation

    if meeting_id:
        lesson, _ = Lesson.objects.get_or_create(
            user=user,
            meeting_id=meeting_id,
            meeting_date=today,
            defaults={"title": meeting_title or f"Capture {today.isoformat()}"},
        )
        return lesson

    return Lesson.objects.create(
        user=user,
        title=meeting_title or f"Capture {today.isoformat()}",
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
        lesson = _get_or_create_lesson(request.user, meeting_id, meeting_title, first_text=text)

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
            "lesson_id": 123,              // optional, overrides auto-create
            "persona": "You are a grade 3 student",  // optional, overrides user settings
            "description": "Help me impress my teacher"  // optional, overrides user settings
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
    
    # AI customization (optional, overrides user settings)
    persona = body.get("persona", "").strip()
    description = body.get("description", "").strip()

    # Resolve lesson
    if lesson_id:
        try:
            lesson = Lesson.objects.get(id=lesson_id, user=request.user)
        except Lesson.DoesNotExist:
            return JsonResponse({"error": "Lesson not found"}, status=404)
    elif meeting_id:
        lesson = _get_or_create_lesson(request.user, meeting_id, meeting_title, first_text=question_text)
    else:
        lesson = _get_or_create_lesson(request.user, "", meeting_title, first_text=question_text)

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

    # Use persona/description from request, fallback to user settings
    final_persona = persona or profile.ai_persona
    final_description = description or profile.ai_description

    # Call OpenAI synchronously
    ai_result = answer_question(
        question=question_text,
        context=full_context,
        grade_level=profile.grade_level,
        max_sentences=profile.max_sentences,
        persona=final_persona,
        description=final_description,
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
            persona=profile.ai_persona,
            description=profile.ai_description,
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


# ---------------------------------------------------------------------------
# POST /api/lessons/upload/ — Document upload (web dashboard only)
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
@login_required
def api_lessons_upload(request: HttpRequest) -> JsonResponse:
    """
    Upload images/PDFs for OCR transcription and lesson creation.
    
    Web dashboard only (session auth required).
    
    Request:
        multipart/form-data with files
    
    Response:
        {
            "lesson_id": 123,
            "lesson_name": "Introduction to Photosynthesis",
            "pages_processed": 15,
            "processing_time_ms": 12340,
            "errors": ["file1.pdf: corrupted", ...]
        }
    """
    # Check subscription
    if not user_has_active_subscription(request.user):
        return JsonResponse({"error": "Subscription required"}, status=403)
    
    # Rate limiting: 50 uploads per day
    cache_key = f"upload_rate_limit:{request.user.id}"
    upload_count = cache.get(cache_key, 0)
    
    if upload_count >= 50:
        return JsonResponse({
            "error": "Rate limit exceeded. Max 50 uploads per day."
        }, status=429)
    
    # Get uploaded files
    files = request.FILES.getlist('files')
    
    if not files:
        return JsonResponse({"error": "No files uploaded"}, status=400)
    
    if len(files) > MAX_FILES_PER_UPLOAD:
        return JsonResponse({
            "error": f"Too many files. Max {MAX_FILES_PER_UPLOAD} files per upload."
        }, status=400)
    
    # Check total size
    total_size = sum(f.size for f in files)
    max_size_bytes = MAX_TOTAL_SIZE_MB * 1024 * 1024
    
    if total_size > max_size_bytes:
        return JsonResponse({
            "error": f"Total file size too large: {total_size / 1024 / 1024:.1f}MB > {MAX_TOTAL_SIZE_MB}MB"
        }, status=400)
    
    # Process files
    try:
        filenames = [f.name for f in files]
        result = create_lesson_from_uploads(request.user, files, filenames)
        
        # Increment rate limit counter (expires in 24 hours)
        cache.set(cache_key, upload_count + 1, 86400)
        
        return JsonResponse({
            "lesson_id": result['lesson_id'],
            "lesson_name": result['lesson_name'],
            "pages_processed": result['pages_processed'],
            "processing_time_ms": result['total_processing_time_ms'],
            "errors": result['errors'],
        })
    
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    
    except Exception as e:
        return JsonResponse({"error": f"Processing failed: {str(e)}"}, status=500)


# ---------------------------------------------------------------------------
# GET /api/lessons/list/ — List lessons for desktop app selection
# ---------------------------------------------------------------------------


@csrf_exempt
@require_device_token
def api_lessons_list(request: HttpRequest) -> JsonResponse:
    """
    List lessons for desktop app lesson selection.
    
    Query params:
        ?source_type=recitation|lesson  (optional, default: all)
    
    Response:
        {
            "lessons": [
                {
                    "id": 123,
                    "title": "Introduction to Photosynthesis",
                    "source_type": "lesson",
                    "created_at": "2026-03-07T10:30:00Z",
                    "page_count": 15
                }
            ]
        }
    """
    source_type = request.GET.get('source_type', '').strip()
    
    # Build query
    lessons_query = Lesson.objects.filter(user=request.user)
    
    if source_type in [Lesson.SOURCE_RECITATION, Lesson.SOURCE_LESSON]:
        lessons_query = lessons_query.filter(source_type=source_type)
    
    # Order by most recent first
    lessons = lessons_query.order_by('-created_at')[:100]
    
    # Serialize
    lessons_data = []
    for lesson in lessons:
        page_count = lesson.transcript_chunks.count()
        
        lessons_data.append({
            'id': lesson.id,
            'title': lesson.title,
            'source_type': lesson.source_type,
            'created_at': lesson.created_at.isoformat(),
            'page_count': page_count,
        })
    
    return JsonResponse({'lessons': lessons_data})


# ---------------------------------------------------------------------------
# DELETE /api/lessons/<id>/ — Delete single lesson
# ---------------------------------------------------------------------------


@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
def api_lesson_delete(request: HttpRequest, lesson_id: int) -> JsonResponse:
    """
    Delete a single lesson and all associated data.
    
    Deletes:
    - Lesson record
    - All TranscriptChunks (cascade)
    - All QuestionAnswers (cascade)
    
    Response:
        {"success": true, "deleted_id": 123}
    """
    lesson = get_object_or_404(Lesson, id=lesson_id, user=request.user)
    
    lesson_title = lesson.title
    lesson.delete()
    
    return JsonResponse({
        'success': True,
        'deleted_id': lesson_id,
        'message': f'Lesson "{lesson_title}" deleted successfully'
    })


# ---------------------------------------------------------------------------
# POST /api/lessons/bulk-delete/ — Delete multiple lessons
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
@login_required
def api_lessons_bulk_delete(request: HttpRequest) -> JsonResponse:
    """
    Delete multiple lessons in bulk.
    
    Request body (JSON):
        {
            "lesson_ids": [123, 456, 789]
        }
    
    Response:
        {
            "success": true,
            "deleted_count": 3,
            "deleted_ids": [123, 456, 789]
        }
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    lesson_ids = body.get('lesson_ids', [])
    
    if not lesson_ids:
        return JsonResponse({"error": "No lesson IDs provided"}, status=400)
    
    if not isinstance(lesson_ids, list):
        return JsonResponse({"error": "lesson_ids must be an array"}, status=400)
    
    # Verify all lessons belong to the user before deleting
    lessons = Lesson.objects.filter(id__in=lesson_ids, user=request.user)
    
    if lessons.count() != len(lesson_ids):
        return JsonResponse({
            "error": "Some lessons not found or do not belong to you"
        }, status=404)
    
    deleted_count = lessons.count()
    deleted_ids = list(lessons.values_list('id', flat=True))
    
    # Delete all lessons (cascades to chunks and Q&As)
    lessons.delete()
    
    return JsonResponse({
        'success': True,
        'deleted_count': deleted_count,
        'deleted_ids': deleted_ids,
        'message': f'{deleted_count} lesson(s) deleted successfully'
    })
