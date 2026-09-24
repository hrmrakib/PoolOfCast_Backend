
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from .send_otp import generate_and_send_otp
from .serializers import *
from django.utils import timezone
from django.contrib.auth import authenticate
from datetime import timedelta
from rest_framework import status, permissions
from django.db.models import Q
from .models import User
from utils.permissions import IsAdminRole
from core.pagination import CustomPagination
from talent.models import Talent
from jobs.models import *
from chat.models import *
from django.shortcuts import get_object_or_404

import logging

logger = logging.getLogger(__name__)

# Create your views here.
class RegisterView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = SignupSerializer(data=request.data)

        # custom validation handling
        if not serializer.is_valid():
            # extract first error message
            errors = serializer.errors
            first_field = next(iter(errors))
            error_message = errors[first_field][0]

            return Response(
                {
                    "status": False,
                    "status_code": 400,
                    "message": error_message
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = serializer.save()
        except Exception as e:
            return Response(
                {
                    "status": False,
                    "status_code": 400,
                    "message": f"Registration failed: {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            generate_and_send_otp(user)
        except Exception as e:
            return Response(
                {
                    "status": False,
                    "status_code": 400,
                    "message": f"OTP generation failed: {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "status": True,
                "status_code": 201,
                "message": "Account created successfully. OTP sent to email.",
            },
            status=status.HTTP_201_CREATED,
        )

class SendOTPView(APIView):

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data.get('email')

        # --- Validate ---
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"status":False,"status_code": 404,"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)


        # --- Generate new OTP ---
        generate_and_send_otp(user)

        return Response(
            {"status":True,"status_code": 200,"message": "A new OTP has been sent to your email."},
            status=status.HTTP_200_OK
        )

class VerifyOTPView(APIView):
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            first_field = next(iter(errors))
            error_message = errors[first_field][0]
            return Response(
                {
                    "status": False,
                    "status_code": 400,
                    "message": error_message
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data.get('email')
        otp = serializer.validated_data.get('otp')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "status_code": 404,
                    "message": "User not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if not user.otp or not user.otp_expired_at:
            return Response(
                {
                    "status": False,
                    "status_code": 400,
                    "message": "No OTP found. Please request again."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if timezone.now() > user.otp_expired_at:
            return Response(
                {
                    "status": False,
                    "status_code": 400,
                    "message": "OTP expired. Please request a new one."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user.otp != otp:
            return Response(
                {
                    "status": False,
                    "status_code": 400,
                    "message": "Invalid OTP."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user.is_verified = True
            user.is_active = False
            user.otp = None
            user.otp_expired_at = None
            user.save()
        except Exception as e:
            return Response(
                {
                    "status": False,
                    "status_code": 400,
                    "message": f"Verification failed: {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "status": True,
                "status_code": 200,
                "message": "Your account has been verified successfully. Please wait for admin approval before accessing all features."
            },
            status=status.HTTP_200_OK
        )

class LoginView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data.get('email')
        password = serializer.validated_data.get('password')

        # --- Validation layer ---
        if not email or not password:
            return Response({"status":False,"status_code": 400,"message": "Email and password are required."}, status=400)

        user = authenticate(email=email, password=password)
        if User.objects.filter(email=email).exists() and not User.objects.filter(email=email).first().is_active:
            return Response({"status":False,"status_code": 403,"message": "Your account has not been approved by the admin yet. Please check your login details and try again."}, status=403)
        
        
        if not user:
            return Response({"status":False,"status_code": 400,"message": "Invalid username or password !"}, status=400)
        if not user.is_active:
            return Response({"status":False,"status_code": 403,"message": "Account not verified. Please verify OTP."}, status=403)
        
        serializer = UserProfileSerializer(user, context={'request': request})

        refresh = RefreshToken.for_user(user)
        tokens = str(refresh.access_token)
        # if user.role == "driver":
        #     data = {"id": user.id,"name": user.name, "email": user.email, "image": user.image.url, "role": user.role, "phone_number": user.phone_number, "account_balance": user.account_balance, "address": user.address, "vehicle": user.vehicle, "vehicle_registration_number": user.vehicle_registration_number, "driving_license_number": user.driving_license_number}
        # else:
        #     data = {"id": user.id,"name": user.name, "email": user.email, "image": user.image.url, "role": user.role, "phone_number": user.phone_number, "account_balance": user.account_balance, "address": user.address}
        return Response({
            "status":True,
            "status_code": 200,
            "message": "Login successful.",
            "access_token": tokens,
            "user": serializer.data
        }, status=200)
    

class AdminLoginView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data.get('email')
        password = serializer.validated_data.get('password')

        # --- Validation layer ---
        if not email or not password:
            return Response({"status":False,"status_code": 400,"message": "Email and password are required."}, status=400)

        user = authenticate(email=email, password=password)
        if not user.is_superuser:
            return Response({"status":False,"status_code": 400,"message": "Permission denied."}, status=400)
        if not user:
            return Response({"status":False,"status_code": 400,"message": "Invalid email or password."}, status=400)
        if not user.is_active:
            return Response({"status":False,"status_code": 403,"message": "Account not verified. Please verify OTP."}, status=403)
        
        serializer = UserProfileSerializer(user, context={'request': request})


        refresh = RefreshToken.for_user(user)
        tokens = str(refresh.access_token)
        # if user.role == "driver":
        #     data = {"id": user.id,"name": user.name, "email": user.email, "image": user.image.url, "role": user.role, "phone_number": user.phone_number, "account_balance": user.account_balance, "address": user.address, "vehicle": user.vehicle, "vehicle_registration_number": user.vehicle_registration_number, "driving_license_number": user.driving_license_number}
        # else:
        #     data = {"id": user.id,"name": user.name, "email": user.email, "image": user.image.url, "role": user.role, "phone_number": user.phone_number, "account_balance": user.account_balance, "address": user.address}
        return Response({
            "status":True,
            "status_code": 200,
            "message": "Login successful.",
            "access_token": tokens,
            "user": serializer.data
        }, status=200)

class ResetPasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        # --- Validation layer ---
        if not new_password or not confirm_password:
            return Response({"status":False,"status_code": 400,"message": "Both new and confirm passwords are required."}, status=400)
        if len(new_password) < 6:
            return Response({"status":False,"status_code": 400,"message": "New password must be at least 6 characters long."}, status=400)
        if confirm_password != new_password:
            return Response({"status":False,"status_code": 400,"message": "Password doesn't match."}, status=400)

        user = request.user
        
        user.set_password(new_password)
        user.save()
        return Response({"status":True,"status_code": 200,"message": "Password reset successfully."}, status=200)

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        # --- Validation layer ---
        if not old_password or not new_password:
            return Response({"status":False,"status_code": 400,"message": "Both old and new passwords are required."}, status=400)
        if len(new_password) < 6:
            return Response({"status":False,"status_code": 400,"message": "New password must be at least 6 characters long."}, status=400)
        if old_password == new_password:
            return Response({"status":False,"status_code": 400,"message": "New password cannot be same as old password."}, status=400)

        user = request.user
        if not user.check_password(old_password):
            return Response({"status":False,"status_code": 400,"message": "Old password is incorrect."}, status=400)

        user.set_password(new_password)
        user.save()
        return Response({"status":True,"status_code": 200,"message": "Password changed successfully."}, status=200)



#--------------------------------------------------------------------------------------------------

class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]


    def get(self, request):
        user = request.user
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        serializer = UserDetailSerializer(request.user, context={'request': request})
        return Response(
            {
                "status": True,
                "status_code": 200,
                "message": "User profile retrieved successfully.",
                "access_token": access_token,
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "status_code": 200,
                    "message": "Profile updated successfully.",
                    "data": UserDetailSerializer(request.user).data
                },
                status=status.HTTP_200_OK
            )
        return Response(
            {
                "status": False,
                "status_code": 400,
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request):
        serializer = UserProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=False
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "status_code": 200,
                    "message": "Profile updated successfully.",
                    "data": UserDetailSerializer(request.user).data
                },
                status=status.HTTP_200_OK
            )
        return Response(
            {
                "status": False,
                "status_code": 400,
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    

class UserListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = User.objects.filter(is_verified=True).order_by("-date_joined")

        search = request.GET.get("search")
        is_active = request.GET.get("is_active")


        if is_active is not None:
            if is_active.lower() == "true":
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() == "false":
                queryset = queryset.filter(is_active=False)


        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )

        paginator = CustomPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request, view=self)
        serializer = UserListSerializer(paginated_queryset, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)
    


class UserDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_object(self, user_id):
        return get_object_or_404(User, user_id=user_id)

    def get(self, request, user_id):
        user = self.get_object(user_id)

        serializer = UserDetailSerializer(user, context={'request': request})

        return Response(
            {
                "status": True,
                "status_code": 200,
                "message": "User retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    def patch(self, request, user_id):
        user = self.get_object(user_id)
        if not user:
            return Response(
                {
                    "status": False,
                    "status_code": 404,
                    "message": "User not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "status_code": 200,
                    "message": "User updated successfully.",
                    "data": UserDetailSerializer(user).data
                },
                status=status.HTTP_200_OK
            )
        return Response(
            {
                "status": False,
                "status_code": 400,
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request, user_id):
        user = self.get_object(user_id)
        if not user:
            return Response(
                {
                    "status": False,
                    "status_code": 404,
                    "message": "User not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "status_code": 200,
                    "message": "User updated successfully.",
                    "data": UserDetailSerializer(user).data
                },
                status=status.HTTP_200_OK
            )
        return Response(
            {
                "status": False,
                "status_code": 400,
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, user_id):
        user = self.get_object(user_id)

        try:
            user.delete()
        except Exception as e:
            return Response(
                {
                    "status": False,
                    "status_code": 400,
                    "message": f"Cannot delete user. {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "status": True,
                "status_code": 200,
                "message": "User deleted successfully."
            },
            status=status.HTTP_200_OK
        )


class UserStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def patch(self, request, user_id):
        try:
            user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "status_code": 404,
                    "message": "User not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = UserStatusUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            message = "User status updated successfully."
            return Response(
                {
                    "status": True,
                    "status_code": 200,
                    "message": message,
                    "data": {
                        "user_id": user.user_id,
                        "is_active": user.is_active
                    }
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "status": False,
                "status_code": 400,
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    


class DashboardAPIView(APIView):

    def get(self, request):
        user = request.user
        if not user.is_superuser:
            return Response(
                {
                    "status": False,
                    "status_code": 403,
                    "message": "You are not authorized to access this resource."
                },
                status=status.HTTP_403_FORBIDDEN
            )
        # Counts
        total_clients = User.objects.filter(role="Client").count()
        total_agents = User.objects.filter(role="Agent").count()
        total_talents = Talent.objects.count()
        total_jobs = Job.objects.filter(status="active").count()

        # Recent users (latest 10)
        recent_users = User.objects.order_by("-date_joined")[:10]

        return Response({
            "status": True,
            "status_code": 200,
            "total_clients": total_clients,
            "total_agents": total_agents,
            "total_jobs": total_jobs,
            "total_talents": total_talents,
            "recent_users": RecentUserSerializer(recent_users, many=True).data
        })
    






from django.core.mail import EmailMultiAlternatives
from django.conf import settings


def send_email(to_email, subject, message):
    email = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email.send()

class AgentApprovalAPIView(APIView):
    def get_object(self, user_id):
        return get_object_or_404(User, user_id=user_id)

    def patch(self, request):
        try:
            user_id = request.data.get("user_id")
            action = request.data.get("action")  # approve / reject
            message = request.data.get("message")

            if not user_id or not action:
                return Response(
                    {"error": "User Id and action are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if action == "reject" and not message:
                return Response({"error": "message is required for rejection"}, status=400)

            if action not in ["approve", "reject"]:
                return Response(
                    {"error": "action must be 'approve' or 'reject'"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                user = self.get_object(user_id=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "Uer not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
        

            # Update status
            if action == "approve":
                user.is_active = True
                user.save()
                subject = "Congratulations! Your account has been approved"
                message = (
                    "We are pleased to inform you that your agent profile has been approved. "
                    "Your profile is now active and visible to clients for potential opportunities. "
                    "You can start receiving job requests shortly."
                )
            else:
                user.is_active = False
                subject = "Sorry! Your request has been rejected"


            user.save()

            # Send email (optional but recommended). Do not fail approval on email error.
            email_error = None
            if subject and message:
                try:
                    send_email(
                        to_email=user.email,
                        subject=subject,
                        message=message
                    )
                except Exception as e:
                    logger.exception("Failed to send agent approval email")
                    email_error = str(e)

            resp = {"message": f"User {action}d successfully"}
            if email_error:
                resp["email_error"] = email_error

            return Response(resp, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error in AgentApprovalAPIView.patch")
            return Response(
                {
                    "success": False,
                    "message": "An error occurred while processing the request.",
                    "error": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST
            )


from jobs.models import Notifications


class ClientDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != "Client":
            return Response(
                {
                    "status": False,
                    "status_code": 403,
                    "message": "Only clients can access dashboard."
                },
                status=403
            )

        # =========================
        # 📊 STATS
        # =========================
        jobs_qs = Job.objects.filter(job_created_by_id=user.user_id)

        active_jobs = jobs_qs.filter(status="active").count()
        total_jobs = jobs_qs.count()

        # total talents (from AI results)
        ai_results = JobAIResult.objects.filter(job_id__in=jobs_qs.values_list("job_id", flat=True))

        total_talents = 0
        booked = 0
        pending = 0

        for ai in ai_results:
            talents = ai.suggested_talents or []

            if isinstance(talents, str):
                import json
                talents = json.loads(talents)

            total_talents += len(talents)

            for t in talents:
                if t.get("is_active"):
                    booked += 1
                else:
                    pending += 1

        # =========================
        # 📦 RECENT JOBS
        # =========================
        recent_jobs_qs = jobs_qs.order_by("-created_at")[:5]

        recent_jobs = []
        for job in recent_jobs_qs:
            recent_jobs.append({
                "job_id": job.job_id,
                "session_id": job.session_id,
                "title": job.title,
                "location": job.location,
                "status": job.status,
                "created_at": job.created_at,
                "applicants": job.applicants_count,
                "shortlisted": job.shortlisted_count,
            })

        # =========================
        # ⚡ RECENT ACTIVITY
        # =========================
        # Example: last 10 AI suggested talents

        recent_activity = Notifications.objects.filter(receiver = request.user).order_by('-created_at')[:15]

        recent_activitys = NotificationDetailSerializer(recent_activity, many=True, context={'request': request})




        return Response(
            {
                "status": True,
                "status_code": 200,
                "message": "Dashboard data fetched successfully.",
                "data": {
                    "stats": {
                        "active_jobs": active_jobs,
                        "total_talent": total_talents,
                        "booked": booked,
                        "pending": pending
                    },
                    "recent_jobs": recent_jobs,
                    "recent_activity": recent_activitys.data
                }
            },
            status=200
        )
    



class AgentDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != "Agent":
            return Response(
                {
                    "status": False,
                    "status_code": 403,
                    "message": "Only agents can access dashboard."
                },
                status=403
            )

        # =========================
        # 📊 TOTAL TALENTS (added by agent)
        # =========================
        total_talents = Talent.objects.filter(agent=user).count()

        # =========================
        # 📦 ACTIVE JOBS (where agent talents are used)
        # =========================
        agent_talent_ids = Talent.objects.filter(agent=user).values_list("talent_id", flat=True)

        ai_results = JobAIResult.objects.all()

        active_job_ids = set()

        import json

        for ai in ai_results:
            talents = ai.suggested_talents or []

            if isinstance(talents, str):
                try:
                    talents = json.loads(talents)
                except:
                    talents = []

            for t in talents:
                if t.get("talent_id") in agent_talent_ids:
                    active_job_ids.add(ai.job_id)

        active_jobs_count = Job.objects.filter(
            job_id__in=active_job_ids,
            status="active"
        ).count()

        # =========================
        # 💬 NEW MESSAGES
        # =========================
        new_messages = Message.objects.filter(
            receiver=user,
            is_seen=False
        ).count()

        # =========================
        # ⚡ RECENT ACTIVITY
        # =========================
        recent_activity = Notifications.objects.filter(receiver = request.user).order_by('-created_at')[:15]

        recent_activitys = NotificationDetailSerializer(recent_activity, many=True, context={'request': request})

      
        return Response(
            {
                "status": True,
                "status_code": 200,
                "message": "Agent dashboard data fetched successfully.",
                "data": {
                    "stats": {
                        "total_talents": total_talents,
                        "active_jobs": active_jobs_count,
                        "new_messages": new_messages
                    },
                    "recent_activity": recent_activitys.data
                }
            },
            status=200
        )
