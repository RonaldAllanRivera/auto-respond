from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import Lesson


@login_required
def index(request: HttpRequest) -> HttpResponse:
    lessons = Lesson.objects.filter(user=request.user).order_by("-created_at")[:50]
    return render(request, "lessons/dashboard.html", {"lessons": lessons})


@login_required
def lesson_detail(request: HttpRequest, lesson_id: int) -> HttpResponse:
    lesson = get_object_or_404(Lesson, id=lesson_id, user=request.user)
    chunks = lesson.transcript_chunks.order_by("created_at")
    qas = lesson.qas.order_by("-created_at")
    return render(request, "lessons/lesson_detail.html", {
        "lesson": lesson,
        "chunks": chunks,
        "qas": qas,
    })
