from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = ("conversation_id", "user1", "user2", "updated_at", "created_at")
    search_fields = ("user1__email", "user2__email", "user1__full_name", "user2__full_name")


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ("message_id", "conversation", "sender", "receiver", "message_type", "is_seen", "created_at")
    list_filter = ("message_type", "is_seen", "created_at")
    search_fields = ("text", "sender__email", "receiver__email")