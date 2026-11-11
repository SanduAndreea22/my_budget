from django.contrib import admin

from .models import FeedbackMessage


@admin.register(FeedbackMessage)
class FeedbackMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "name", "email", "short_message", "handled")
    list_filter = ("handled", "created_at")
    search_fields = ("name", "email", "message")
    readonly_fields = ("created_at", "name", "email", "message", "user")
    list_editable = ("handled",)

    @admin.display(description="Message")
    def short_message(self, obj):
        return obj.message[:80]
