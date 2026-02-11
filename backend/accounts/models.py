from django.conf import settings
from django.db import models


class SubscriberProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriber_profile")
    grade_level = models.PositiveIntegerField(default=3)
    max_sentences = models.PositiveIntegerField(default=2)

    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_for_user(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj
