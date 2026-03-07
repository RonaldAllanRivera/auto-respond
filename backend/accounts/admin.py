from django.contrib import admin

from .models import SubscriberProfile


@admin.register(SubscriberProfile)
class SubscriberProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "ai_persona", "max_sentences", "updated_at")
    search_fields = ("user__email", "user__username")
