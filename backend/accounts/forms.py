from django import forms

from .models import SubscriberProfile


class SubscriberProfileForm(forms.ModelForm):
    class Meta:
        model = SubscriberProfile
        fields = ["max_sentences", "ai_persona", "ai_description"]
