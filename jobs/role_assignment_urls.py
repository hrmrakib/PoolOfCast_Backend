from django.urls import path

from .role_assignment_views import AssignRoleAPIView, AvailableRolesAPIView, UnassignRoleAPIView

urlpatterns = [
    path("available-roles", AvailableRolesAPIView.as_view(), name="available_roles"),
    path("assign-role", AssignRoleAPIView.as_view(), name="assign_role"),
    path("unassign-role", UnassignRoleAPIView.as_view(), name="unassign_role"),
]
