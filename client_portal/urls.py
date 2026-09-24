from django.urls import path

from .views import (
    AgentChatInboxAPIView,
    AgentChatUploadAPIView,
    AgentGuestChatMessagesAPIView,
    AgentGuestClientDetailAPIView,
    AgentJobGuestClientsAPIView,
    GuestChatMessagesAPIView,
    GuestChatUploadAPIView,
    GuestFavoriteDeleteAPIView,
    GuestFavoriteListCreateAPIView,
    GuestIdentifyAPIView,
    GuestSessionAPIView,
    GuestTalentCommentAPIView,
    GuestVerifyOTPAPIView,
)

urlpatterns = [
    # Guest-facing (public shortlist link)
    path("client/talents/shortlisted/<int:job_id>/identify/", GuestIdentifyAPIView.as_view(), name="guest-identify"),
    path("client/talents/shortlisted/<int:job_id>/verify/", GuestVerifyOTPAPIView.as_view(), name="guest-verify-otp"),
    path("client/talents/shortlisted/<int:job_id>/session/", GuestSessionAPIView.as_view(), name="guest-session"),
    path("client/talents/shortlisted/<int:job_id>/favorites/", GuestFavoriteListCreateAPIView.as_view(), name="guest-favorites"),
    path("client/talents/shortlisted/<int:job_id>/favorites/<int:talent_id>/", GuestFavoriteDeleteAPIView.as_view(), name="guest-favorite-delete"),
    path("client/talents/shortlisted/<int:job_id>/talents/<int:talent_id>/comments/", GuestTalentCommentAPIView.as_view(), name="guest-talent-comments"),
    path("client/talents/shortlisted/<int:job_id>/chat/messages/", GuestChatMessagesAPIView.as_view(), name="guest-chat-messages"),
    path("client/talents/shortlisted/<int:job_id>/chat/upload/", GuestChatUploadAPIView.as_view(), name="guest-chat-upload"),

    # Agent-facing
    path("agent/jobs/<int:job_id>/clients/", AgentJobGuestClientsAPIView.as_view(), name="agent-job-clients"),
    path("agent/jobs/<int:job_id>/clients/<int:guest_client_id>/", AgentGuestClientDetailAPIView.as_view(), name="agent-guest-client-detail"),
    path("agent/jobs/<int:job_id>/clients/<int:guest_client_id>/chat/messages/", AgentGuestChatMessagesAPIView.as_view(), name="agent-guest-chat-messages"),
    path("agent/jobs/<int:job_id>/clients/<int:guest_client_id>/chat/upload/", AgentChatUploadAPIView.as_view(), name="agent-chat-upload"),
    path("agent/chat/inbox/", AgentChatInboxAPIView.as_view(), name="agent-chat-inbox"),
]
