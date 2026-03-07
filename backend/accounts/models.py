from django.conf import settings
from django.db import models


class SubscriberProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriber_profile")
    grade_level = models.PositiveIntegerField(default=3)
    max_sentences = models.PositiveIntegerField(default=2)
    
    # AI customization fields
    ai_persona = models.TextField(
        blank=True,
        default="You are a helpful tutor",
        help_text="AI persona/role (e.g., 'You are a grade 3 student')"
    )
    ai_description = models.TextField(
        blank=True,
        default="",
        help_text="Additional AI instructions (e.g., 'Help me impress my teacher and get high grades')"
    )

    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_for_user(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj
