from django.contrib import admin

from .models import Request


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_id",
        "source",
        "type",
        "status",
        "workflow_id",
        "created_at",
    )
    list_filter = ("status", "type", "source")
    search_fields = ("ticket_id", "requester")
    readonly_fields = ("created_at", "updated_at")
