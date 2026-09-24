from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ClientChatMessage, ClientChatThread, GuestClient, TalentComment, TalentFavorite


@admin.register(GuestClient)
class GuestClientAdmin(ModelAdmin):
    list_display = ("id", "name", "email", "job_id", "is_verified", "created_at", "last_seen_at")
    search_fields = ("name", "email")
    list_filter = ("is_verified", "created_at")


@admin.register(TalentFavorite)
class TalentFavoriteAdmin(ModelAdmin):
    list_display = ("id", "guest_client", "talent", "job_id", "created_at")


@admin.register(TalentComment)
class TalentCommentAdmin(ModelAdmin):
    list_display = ("id", "guest_client", "talent", "job_id", "created_at")
    search_fields = ("comment",)


@admin.register(ClientChatThread)
class ClientChatThreadAdmin(ModelAdmin):
    list_display = ("id", "guest_client", "agent", "job_id", "updated_at", "created_at")


@admin.register(ClientChatMessage)
class ClientChatMessageAdmin(ModelAdmin):
    list_display = ("id", "thread", "sender_type", "message_type", "is_seen_by_agent", "is_seen_by_client", "created_at")
    list_filter = ("sender_type", "message_type")
