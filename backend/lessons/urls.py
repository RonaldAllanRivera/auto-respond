from django.urls import path

from . import views

urlpatterns = [
    path("", views.lesson_list, name="lesson_list"),
    path("lessons/new/", views.lesson_create, name="lesson_create"),
    path("lessons/<int:lesson_id>/", views.lesson_detail, name="lesson_detail"),
    path("ask/", views.ask, name="ask"),
    path("settings/", views.settings_view, name="settings"),
    path("api/install", views.api_install, name="api_install"),
    path("api/captions/ingest", views.api_captions_ingest, name="api_captions_ingest"),
    path("api/answer", views.api_answer, name="api_answer"),
]
