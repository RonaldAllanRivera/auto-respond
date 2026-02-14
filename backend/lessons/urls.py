from django.urls import path

from .api import api_captions, api_question_stream, api_questions
from .views import index, lesson_detail

urlpatterns = [
    path("", index, name="index"),
    path("lessons/<int:lesson_id>/", lesson_detail, name="lesson_detail"),
    path("api/captions/", api_captions, name="api_captions"),
    path("api/questions/", api_questions, name="api_questions"),
    path("api/questions/<int:question_id>/stream/", api_question_stream, name="api_question_stream"),
]
