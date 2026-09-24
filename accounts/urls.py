from django.urls import path
from accounts import views
from django.urls import path
from accounts.views import *

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify_otp/', VerifyOTPView.as_view(), name='verify_otp'),
    path('send_otp/', SendOTPView.as_view(), name='send_otp'),
    path('login/', LoginView.as_view(), name='login'),
    path('admin_login/', AdminLoginView.as_view(), name='admin_login'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('change_password/', ChangePasswordView.as_view(), name='change_password'),




    path("user/profile/", UserProfileAPIView.as_view(), name="user-profile"),

    path("user/user_list", UserListAPIView.as_view(), name="user-list"),
    path("user/<int:user_id>/", UserDetailAPIView.as_view(), name="user-detail"),
    path("user/<int:user_id>/status/", UserStatusUpdateAPIView.as_view(), name="user-status-update"),


    path("dashboard/", DashboardAPIView.as_view(), name="dashboard"),
    path("client/dashboard/", ClientDashboardAPIView.as_view(), name="client-dashboard"),
    path("agent/dashboard/", AgentDashboardAPIView.as_view(), name="agent-dashboard"),

    path("admin/agents/action/", AgentApprovalAPIView.as_view()),
]