from django.urls import path
from .views import *

urlpatterns = [
    path("active_jobs/", ActiveJobAPIView.as_view(), name="active_jobs"),
    path("active_jobs/<int:job_id>/", ActiveJobAPIView.as_view(), name="single_active_jobs"),
    path("draft_jobs/", DraftJobAPIView.as_view(), name="draft_jobs"),
    path("draft_jobs/<int:draft_id>/", DraftJobAPIView.as_view(), name="single_draft_jobs"),
    
    path("jobs/<int:job_id>/ai_result/", JobAIResultAPIView.as_view(), name="job_ai_result"),

    path("jobs/<int:job_id>/meetings/", MeetingVideoRecord.as_view(), name="job_meetings"),
    
    # path("talent-requests/<int:request_id>/", TalentRequestStatusUpdateAPIView.as_view(), name="talent-request-update"),
]