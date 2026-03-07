from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import SubscriberProfile
from billing.entitlements import billing_is_configured, user_has_active_subscription

from .models import Lesson


@login_required
def index(request: HttpRequest) -> HttpResponse:
    # Get source_type filter from query params
    source_type = request.GET.get('source_type', '').strip()
    
    lessons_query = Lesson.objects.filter(user=request.user)
    
    if source_type in [Lesson.SOURCE_RECITATION, Lesson.SOURCE_LESSON]:
        lessons_query = lessons_query.filter(source_type=source_type)
    
    lessons = lessons_query.order_by("-created_at")[:50]
    
    # Count by type for tabs
    recitation_count = Lesson.objects.filter(
        user=request.user, 
        source_type=Lesson.SOURCE_RECITATION
    ).count()
    lesson_count = Lesson.objects.filter(
        user=request.user, 
        source_type=Lesson.SOURCE_LESSON
    ).count()
    
    billing_enabled = billing_is_configured()
    subscribed = user_has_active_subscription(request.user)
    
    return render(
        request,
        "lessons/dashboard.html",
        {
            "lessons": lessons,
            "billing_enabled": billing_enabled,
            "subscribed": subscribed,
            "source_type": source_type,
            "recitation_count": recitation_count,
            "lesson_count": lesson_count,
        },
    )


@login_required
def upload_page(request: HttpRequest) -> HttpResponse:
    """Document upload page for creating lessons from images/PDFs."""
    billing_enabled = billing_is_configured()
    subscribed = user_has_active_subscription(request.user)
    
    return render(request, "lessons/upload.html", {
        "billing_enabled": billing_enabled,
        "subscribed": subscribed,
    })


@login_required
def lesson_detail(request: HttpRequest, lesson_id: int) -> HttpResponse:
    lesson = get_object_or_404(Lesson, id=lesson_id, user=request.user)
    chunks = lesson.transcript_chunks.order_by("page_number", "created_at")
    qas = lesson.qas.order_by("-created_at")
    
    return render(request, "lessons/lesson_detail.html", {
        "lesson": lesson,
        "chunks": chunks,
        "qas": qas,
    })


@login_required
def settings(request: HttpRequest) -> HttpResponse:
    """User settings page for AI persona and description customization."""
    profile = SubscriberProfile.get_for_user(request.user)
    
    if request.method == "POST":
        # Update settings
        profile.grade_level = int(request.POST.get("grade_level", 3))
        profile.max_sentences = int(request.POST.get("max_sentences", 2))
        profile.ai_persona = request.POST.get("ai_persona", "").strip()
        profile.ai_description = request.POST.get("ai_description", "").strip()
        profile.save()
        
        messages.success(request, "Settings saved successfully!")
        return redirect("lessons:settings")
    
    billing_enabled = billing_is_configured()
    subscribed = user_has_active_subscription(request.user)
    
    return render(request, "lessons/settings.html", {
        "profile": profile,
        "billing_enabled": billing_enabled,
        "subscribed": subscribed,
    })
