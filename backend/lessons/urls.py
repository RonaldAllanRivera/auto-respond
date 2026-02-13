from django.urls import path

from .api import api_captions, api_questions
from .views import index

urlpatterns = [
    path("", index, name="index"),
    path("api/captions/", api_captions, name="api_captions"),
    path("api/questions/", api_questions, name="api_questions"),
]
