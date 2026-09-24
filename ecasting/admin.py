from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import EcastingSession, EcastingParticipant


@admin.register(EcastingSession)
class EcastingSessionAdmin(ModelAdmin):
    list_display = ("session_id", "room_id", "title", "created_by", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("room_id", "title")


@admin.register(EcastingParticipant)
class EcastingParticipantAdmin(ModelAdmin):
    list_display = ("id", "session", "user", "is_host", "joined_at", "left_at")
    list_filter = ("is_host",)
