from django.urls import path

from .job_management_views import DeleteJobAPIView, EditJobAPIView

urlpatterns = [
    path("edit-job/<int:job_id>", EditJobAPIView.as_view(), name="edit_job"),
    path("delete-job-id/", DeleteJobAPIView.as_view(), name="delete_job"),
]
