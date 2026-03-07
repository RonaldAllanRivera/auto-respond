from django.urls import path

from .api import (
    api_captions,
    api_lesson_delete,
    api_lessons_bulk_delete,
    api_lessons_list,
    api_lessons_upload,
    api_question_stream,
    api_questions,
)
from .views import index, lesson_detail, settings, upload_page

urlpatterns = [
    path("", index, name="index"),
    path("upload/", upload_page, name="upload_page"),
    path("settings/", settings, name="settings"),
    path("lessons/<int:lesson_id>/", lesson_detail, name="lesson_detail"),
    path("api/captions/", api_captions, name="api_captions"),
    path("api/questions/", api_questions, name="api_questions"),
    path("api/questions/<int:question_id>/stream/", api_question_stream, name="api_question_stream"),
    path("api/lessons/upload/", api_lessons_upload, name="api_lessons_upload"),
    path("api/lessons/list/", api_lessons_list, name="api_lessons_list"),
    path("api/lessons/<int:lesson_id>/delete/", api_lesson_delete, name="api_lesson_delete"),
    path("api/lessons/bulk-delete/", api_lessons_bulk_delete, name="api_lessons_bulk_delete"),
]
