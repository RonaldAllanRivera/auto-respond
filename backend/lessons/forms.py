from django import forms

from .models import AppSettings, Lesson


class LessonCreateForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ["title"]


class AskForm(forms.Form):
    lesson = forms.ModelChoiceField(queryset=Lesson.objects.order_by("-created_at"), required=False)
    question = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))


class SettingsForm(forms.ModelForm):
    class Meta:
        model = AppSettings
        fields = ["grade_level", "max_sentences"]
