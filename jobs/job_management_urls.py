from django.urls import path

from .job_management_views import DeleteJobAPIView, EditJobAPIView
from .shortlist_booking_views import DeleteAllShortlistsAPIView

urlpatterns = [
    path("edit-job/<int:job_id>", EditJobAPIView.as_view(), name="edit_job"),
    path("delete-job-id/", DeleteJobAPIView.as_view(), name="delete_job"),
    path("delete-all-shortlists", DeleteAllShortlistsAPIView.as_view(), name="deleteShortlist"),
]
