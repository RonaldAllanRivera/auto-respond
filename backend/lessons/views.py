import json
import time
from datetime import datetime, timezone

import jwt
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as dj_timezone
from django.views.decorators.csrf import csrf_exempt

from openai import OpenAI

from .forms import AskForm, LessonCreateForm, SettingsForm
from .models import AppSettings, Install, Lesson, QuestionAnswer, TranscriptChunk


def _add_cors_headers(response: JsonResponse) -> JsonResponse:
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Extension-Key, X-Family-Key"
    return response


def _get_settings() -> AppSettings:
    obj = AppSettings.get_solo()
    if obj.grade_level is None:
        obj.grade_level = settings.DEFAULT_GRADE_LEVEL
    if obj.max_sentences is None:
        obj.max_sentences = settings.DEFAULT_MAX_SENTENCES
    return obj


def lesson_list(request: HttpRequest) -> HttpResponse:
    lessons = Lesson.objects.order_by("-created_at")
    return render(request, "lessons/lesson_list.html", {"lessons": lessons})


def lesson_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = LessonCreateForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.source = Lesson.Source.MANUAL
            lesson.save()
            return redirect("lesson_detail", lesson_id=lesson.id)
    else:
        form = LessonCreateForm()

    return render(request, "lessons/lesson_create.html", {"form": form})


def lesson_detail(request: HttpRequest, lesson_id: int) -> HttpResponse:
    lesson = get_object_or_404(Lesson, id=lesson_id)
    chunks = lesson.transcript_chunks.order_by("created_at")
    qas = lesson.qas.order_by("-created_at")[:50]
    return render(
        request,
        "lessons/lesson_detail.html",
        {"lesson": lesson, "chunks": chunks, "qas": qas},
    )


def ask(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = AskForm(request.POST)
        if form.is_valid():
            lesson = form.cleaned_data.get("lesson")
            question = form.cleaned_data["question"].strip()
            answer, model_name, latency_ms = _answer_question(lesson=lesson, question=question)
            QuestionAnswer.objects.create(
                lesson=lesson,
                question=question,
                answer=answer,
                model=model_name,
                latency_ms=latency_ms,
            )
            return render(
                request,
                "lessons/ask.html",
                {"form": form, "answer": answer, "lesson": lesson},
            )
    else:
        form = AskForm()

    return render(request, "lessons/ask.html", {"form": form})


def settings_view(request: HttpRequest) -> HttpResponse:
    obj = _get_settings()

    if request.method == "POST":
        form = SettingsForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("settings")
    else:
        form = SettingsForm(instance=obj)

    return render(request, "lessons/settings.html", {"form": form})


def _require_extension_bootstrap_key(request: HttpRequest) -> bool:
    expected = getattr(settings, "EXTENSION_BOOTSTRAP_KEY", "")
    if not expected:
        return bool(getattr(settings, "DEBUG", False))
    provided = request.headers.get("X-Extension-Key") or request.headers.get("X-Family-Key", "")
    return provided == expected


def _issue_install_token(install: Install) -> str:
    secret = getattr(settings, "EXTENSION_TOKEN_SECRET", "")
    payload = {
        "install_id": str(install.id),
        "iat": int(time.time()),
        "exp": int(time.time()) + 60 * 60 * 24 * 365,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _verify_install_token(request: HttpRequest) -> Install | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.removeprefix("Bearer ").strip()

    secret = getattr(settings, "EXTENSION_TOKEN_SECRET", "")
    if not secret:
        return None

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        return None

    install_id = payload.get("install_id")
    if not install_id:
        return None

    try:
        install = Install.objects.get(id=install_id)
    except Install.DoesNotExist:
        return None

    install.mark_seen()
    return install


@csrf_exempt
def api_install(request: HttpRequest) -> JsonResponse:
    if request.method == "OPTIONS":
        return _add_cors_headers(JsonResponse({"ok": True}))

    if request.method != "POST":
        return _add_cors_headers(JsonResponse({"error": "method_not_allowed"}, status=405))

    if not _require_extension_bootstrap_key(request):
        return _add_cors_headers(JsonResponse({"error": "unauthorized"}, status=401))

    if not getattr(settings, "EXTENSION_TOKEN_SECRET", ""):
        return _add_cors_headers(JsonResponse({"error": "server_misconfigured"}, status=500))

    body = {}
    if request.body:
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            body = {}

    label = str(body.get("label", "")).strip()[:255]
    install = Install.objects.create(label=label)
    token = _issue_install_token(install)
    return _add_cors_headers(JsonResponse({"token": token}))


def _get_or_create_meeting_lesson(meeting_title: str, meeting_code: str | None) -> Lesson:
    today = dj_timezone.localdate()
    title_clean = meeting_title.strip() if meeting_title else "Google Meet Lesson"
    meeting_code_clean = (meeting_code or "").strip()

    if meeting_code_clean:
        existing = Lesson.objects.filter(meeting_code=meeting_code_clean, meeting_started_at__date=today).order_by("-meeting_started_at").first()
        if existing:
            return existing

    display_title = f"{title_clean} — {today.isoformat()}"
    lesson = Lesson.objects.create(
        title=display_title,
        source=Lesson.Source.MEET_AUTO,
        meeting_code=meeting_code_clean,
        meeting_started_at=dj_timezone.now(),
    )
    return lesson


@csrf_exempt
def api_captions_ingest(request: HttpRequest) -> JsonResponse:
    if request.method == "OPTIONS":
        return _add_cors_headers(JsonResponse({"ok": True}))

    if request.method != "POST":
        return _add_cors_headers(JsonResponse({"error": "method_not_allowed"}, status=405))

    if not _require_extension_bootstrap_key(request):
        return _add_cors_headers(JsonResponse({"error": "unauthorized"}, status=401))

    if _verify_install_token(request) is None:
        return _add_cors_headers(JsonResponse({"error": "unauthorized"}, status=401))

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return _add_cors_headers(JsonResponse({"error": "invalid_json"}, status=400))

    lesson_id = payload.get("lesson_id")
    meeting_title = str(payload.get("meeting_title", "")).strip()
    meeting_code = str(payload.get("meeting_code", "")).strip() or None

    if lesson_id:
        lesson = get_object_or_404(Lesson, id=int(lesson_id))
    else:
        lesson = _get_or_create_meeting_lesson(meeting_title=meeting_title, meeting_code=meeting_code)

    text = str(payload.get("text", "")).strip()
    if not text:
        return _add_cors_headers(JsonResponse({"error": "empty_text"}, status=400))

    speaker = str(payload.get("speaker", "")).strip()
    captured_at = payload.get("captured_at")

    captured_dt = None
    if isinstance(captured_at, str) and captured_at:
        try:
            captured_dt = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except Exception:
            captured_dt = None

    TranscriptChunk.objects.create(
        lesson=lesson,
        source=TranscriptChunk.Source.MEET_CAPTION,
        speaker=speaker,
        text=text,
        captured_at=captured_dt,
    )

    return _add_cors_headers(JsonResponse({"ok": True, "lesson_id": lesson.id}))


def _answer_question(lesson: Lesson | None, question: str) -> tuple[str, str, int | None]:
    app_settings = _get_settings()

    if lesson is not None:
        chunks = lesson.transcript_chunks.order_by("-created_at")[:120]
        context_lines = []
        for c in reversed(list(chunks)):
            if c.speaker:
                context_lines.append(f"{c.speaker}: {c.text}")
            else:
                context_lines.append(c.text)
        lesson_context = "\n".join(context_lines)
        system_prompt = (
            f"You are a fast classroom helper. Answer based only on the lesson transcript. "
            f"Use grade-appropriate language for Grade {app_settings.grade_level}. "
            f"Keep the answer to {app_settings.max_sentences} sentence(s) maximum."
        )
        user_prompt = f"Lesson transcript:\n{lesson_context}\n\nQuestion: {question}\nAnswer:" 
    else:
        system_prompt = (
            f"You are a fast classroom helper for a Grade {app_settings.grade_level} student. "
            f"Answer in {app_settings.max_sentences} sentence(s) maximum using simple words."
        )
        user_prompt = f"Question: {question}\nAnswer:" 

    if not settings.OPENAI_API_KEY:
        return ("OPENAI_API_KEY is not configured.", "", None)

    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS)

    start = time.time()
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=200,
    )
    latency_ms = int((time.time() - start) * 1000)

    answer = (resp.choices[0].message.content or "").strip()
    return (answer, settings.OPENAI_MODEL, latency_ms)


@csrf_exempt
def api_answer(request: HttpRequest) -> JsonResponse:
    if request.method == "OPTIONS":
        return _add_cors_headers(JsonResponse({"ok": True}))

    if request.method != "POST":
        return _add_cors_headers(JsonResponse({"error": "method_not_allowed"}, status=405))

    if not _require_extension_bootstrap_key(request):
        return _add_cors_headers(JsonResponse({"error": "unauthorized"}, status=401))

    if _verify_install_token(request) is None:
        return _add_cors_headers(JsonResponse({"error": "unauthorized"}, status=401))

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return _add_cors_headers(JsonResponse({"error": "invalid_json"}, status=400))

    question = str(payload.get("question", "")).strip()
    if not question:
        return _add_cors_headers(JsonResponse({"error": "empty_question"}, status=400))

    lesson_id = payload.get("lesson_id")
    lesson = None
    if lesson_id:
        lesson = get_object_or_404(Lesson, id=int(lesson_id))

    answer, model_name, latency_ms = _answer_question(lesson=lesson, question=question)
    QuestionAnswer.objects.create(lesson=lesson, question=question, answer=answer, model=model_name, latency_ms=latency_ms)

    return _add_cors_headers(JsonResponse({"answer": answer, "lesson_id": lesson.id if lesson else None}))
