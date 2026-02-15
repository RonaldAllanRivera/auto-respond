from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from billing.entitlements import billing_is_configured, user_has_active_subscription

from .models import Lesson


@login_required
def index(request: HttpRequest) -> HttpResponse:
    lessons = Lesson.objects.filter(user=request.user).order_by("-created_at")[:50]
    billing_enabled = billing_is_configured()
    subscribed = user_has_active_subscription(request.user)
    return render(
        request,
        "lessons/dashboard.html",
        {
            "lessons": lessons,
            "billing_enabled": billing_enabled,
            "subscribed": subscribed,
        },
    )


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
