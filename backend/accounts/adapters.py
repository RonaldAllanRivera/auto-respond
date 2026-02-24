from django.contrib.auth import REDIRECT_FIELD_NAME
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from billing.entitlements import billing_is_configured, user_has_active_subscription


def _has_explicit_next(request) -> bool:
    if request is None:
        return False

    return bool(request.GET.get(REDIRECT_FIELD_NAME) or request.POST.get(REDIRECT_FIELD_NAME))


def _should_go_to_subscribe(request) -> bool:
    if request is None:
        return False

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False

    if _has_explicit_next(request):
        return False

    if not billing_is_configured():
        return False

    return not user_has_active_subscription(user)


def _should_go_to_subscribe_after_signup(request) -> bool:
    if request is None:
        return False

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False

    if _has_explicit_next(request):
        return False

    return True


class MeetLessonsAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        url = super().get_login_redirect_url(request)
        if _should_go_to_subscribe(request):
            return "/billing/subscribe/"
        return url

    def get_signup_redirect_url(self, request):
        url = super().get_signup_redirect_url(request)
        if _should_go_to_subscribe_after_signup(request):
            return "/billing/subscribe/"
        return url


class MeetLessonsSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_login_redirect_url(self, request):
        url = super().get_login_redirect_url(request)
        if _should_go_to_subscribe(request):
            return "/billing/subscribe/"
        return url

    def get_signup_redirect_url(self, request):
        url = super().get_signup_redirect_url(request)
        if _should_go_to_subscribe_after_signup(request):
            return "/billing/subscribe/"
        return url
