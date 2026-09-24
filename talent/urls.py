from django.urls import path
from .views import *

urlpatterns = [
    # Agent APIs
    path("agent/talents/create/", AgentTalentCreateAPIView.as_view(), name="agent-talent-create"),
    path("agent/talents/", AgentTalentListAPIView.as_view(), name="agent-talent-list"),
    path("agent/talents/<int:talent_id>/", AgentTalentDetailAPIView.as_view(), name="agent-talent-detail"),

    # Admin APIs
    path("admin/talents/", AdminTalentListAPIView.as_view(), name="admin-talent-list"),
    path("admin/talents/<int:talent_id>/", AdminTalentDetailAPIView.as_view(), name="admin-talent-detail"),
    path("admin/talents/<int:talent_id>/approval/", AdminTalentApprovalAPIView.as_view(), name="admin-talent-approval"),

    path("admin/talents/action/", TalentApprovalAPIView.as_view()),


    path("client/talents/shortlisted/", ShortListedTalentAPIView.as_view()),
    path("client/talents/shortlisted/<int:job_id>/", ActiveJobDetailView.as_view()),

    path("client/talents/public_shortlisted/", PublicShortListedTalentAPIView.as_view()),
    
    # Web Images API
    path("admin/web-images/", WebImagesAPIView.as_view(), name="web-images"),
    path("public-web-images/", PublicWebImagesAPIView.as_view(), name="public-web-images"),

    # Team API
    path("admin/teams/", TeamListCreateAPIView.as_view(), name="team-list-create"),
    path("public-teams/", PublicTeamListAPIView.as_view(), name="public-team-list"),
    path("admin/teams/<int:pk>/", TeamDetailAPIView.as_view(), name="team-detail"),
]