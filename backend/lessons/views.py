from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import Lesson


@login_required
def index(request: HttpRequest) -> HttpResponse:
    lessons = Lesson.objects.filter(user=request.user).order_by("-created_at")[:50]
    return render(request, "lessons/dashboard.html", {"lessons": lessons})
