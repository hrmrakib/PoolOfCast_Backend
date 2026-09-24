from django.urls import path
from .views import *

urlpatterns = [
    path("session/create/", CreateSessionAPIView.as_view()),
    path("session/<uuid:session_id>/invite/", InviteUsersAPIView.as_view()),
    path("session/join/<str:room_id>/", JoinSessionAPIView.as_view()),
    path("session/leave/<str:room_id>/", LeaveSessionAPIView.as_view()),
    path("session/<str:room_id>/", SessionDetailAPIView.as_view()),
]