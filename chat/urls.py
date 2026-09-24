from django.urls import path
from .views import (
    GetOrCreateConversationAPIView,
    ConversationListAPIView,
    ConversationMessagesAPIView,
    UploadAttachmentMessageAPIView,
    MarkConversationSeenAPIView,
)

urlpatterns = [
    path("conversation/", GetOrCreateConversationAPIView.as_view(), name="chat-get-or-create-conversation"),
    path("conversations/", ConversationListAPIView.as_view(), name="chat-conversation-list"),
    path("conversations/<int:conversation_id>/messages/", ConversationMessagesAPIView.as_view(), name="chat-conversation-messages"),
    path("conversations/<int:conversation_id>/upload/", UploadAttachmentMessageAPIView.as_view(), name="chat-upload-message"),
    path("conversations/<int:conversation_id>/seen/", MarkConversationSeenAPIView.as_view(), name="chat-mark-seen"),
]