from django import forms

from .models import SubscriberProfile


class SubscriberProfileForm(forms.ModelForm):
    class Meta:
        model = SubscriberProfile
        fields = ["grade_level", "max_sentences"]
