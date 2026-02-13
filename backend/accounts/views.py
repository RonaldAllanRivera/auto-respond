from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import SubscriberProfileForm
from .models import SubscriberProfile


@login_required
def settings_view(request: HttpRequest) -> HttpResponse:
    profile = SubscriberProfile.get_for_user(request.user)

    if request.method == "POST":
        form = SubscriberProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("settings")
    else:
        form = SubscriberProfileForm(instance=profile)

    return render(request, "accounts/settings.html", {"form": form})
