from django.urls import path

from .role_assignment_views import AssignRoleAPIView, AvailableRolesAPIView, UnassignRoleAPIView

urlpatterns = [
    path("available-roles", AvailableRolesAPIView.as_view(), name="getAvailableRoles"),
    path("assign-role", AssignRoleAPIView.as_view(), name="assignRole"),
    path("unassign-role", UnassignRoleAPIView.as_view(), name="unassignRole"),
]
