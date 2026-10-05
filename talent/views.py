from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from .models import Talent, ShortListedTalent, ShortlistOrder
from .serializers import *
from utils.permissions import IsAgent, IsAdminUserRole
from core.pagination import CustomPagination
import logging

logger = logging.getLogger(__name__)

def send_email(to_email, subject, message):
    email = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email.send()


class AgentTalentCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        # print("FULL DATA:", request.data)
        serializer = TalentSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    talent = serializer.save()
            except Exception as e:
                return Response(
                    {
                        "status": False,
                        "status_code": 400,
                        "errors": {"non_field_errors": [str(e)]}
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {
                    "status": True,
                    "status_code": 201,
                    "message": "Talent created successfully and sent for admin approval.",
                    "data": TalentSerializer(talent, context={"request": request}).data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(
            {"status": False, "status_code": 400, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )


class AgentTalentListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    def get(self, request):
        queryset = Talent.objects.filter(agent=request.user)

        search = request.query_params.get("search", "").strip()
        gender = request.query_params.get("gender")
        is_available = request.query_params.get("is_available")
        is_available_on_request = request.query_params.get("is_available_on_request")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(role__icontains=search) |
                Q(character__icontains=search) 
            )

        if gender:
            queryset = queryset.filter(gender=gender)

        if is_available is not None:
            if is_available.lower() == "true":
                queryset = queryset.filter(is_available=True)
            elif is_available.lower() == "false":
                queryset = queryset.filter(is_available=False)

        if is_available_on_request is not None:
            if is_available_on_request.lower() == "true":
                queryset = queryset.filter(is_available_on_request=True)
            elif is_available_on_request.lower() == "false":
                queryset = queryset.filter(is_available_on_request=False)
        paginator = CustomPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request, view=self)
        serializer = TalentSerializer(paginated_queryset, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AgentTalentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, request, talent_id):
        try:
            return Talent.objects.get(talent_id=talent_id, agent=request.user)
        except Talent.DoesNotExist:
            return None

    def get(self, request, talent_id):
        talent = self.get_object(request, talent_id)
        if not talent:
            return Response(
                {"status": False,"status_code": 404, "message": "Talent not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TalentSerializer(talent, context={'request': request})
        return Response(
            {"status": True, "status_code": 200, "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def put(self, request, talent_id):
        talent = self.get_object(request, talent_id)
        if not talent:
            return Response(
                {"status": False, "status_code": 404, "message": "Talent not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TalentSerializer(
            talent,
            data=request.data,
            partial=False,
            context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "status_code": 200,
                    "message": "Talent updated successfully and resubmitted for approval.",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        return Response(
            {"status": False, "status_code": 400, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request, talent_id):
        talent = self.get_object(request, talent_id)
        if not talent:
            return Response(
                {"status": False, "status_code": 404, "message": "Talent not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TalentSerializer(
            talent,
            data=request.data,
            partial=True,
            context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "status_code": 200,
                    "message": "Talent updated successfully and resubmitted for approval.",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        return Response(
            {"status": False, "status_code": 400, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, talent_id):
        talent = self.get_object(request, talent_id)
        if not talent:
            return Response(
                {"status": False, "status_code": 404, "message": "Talent not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        with transaction.atomic():
            # These relations use DO_NOTHING (unmanaged tables), so clear them manually.
            ShortListedTalent.objects.filter(talent=talent).delete()
            talent.role_assignments.all().delete()
            talent.bookings.all().delete()
            talent.delete()
        return Response(
            {"status": True, "status_code": 200, "message": "Talent deleted successfully."},
            status=status.HTTP_200_OK
        )


class AdminTalentListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        approval_status = request.GET.get("approval_status")
        search = request.GET.get("search", "").strip()
        queryset = Talent.objects.select_related("agent").all()

        if approval_status:
            queryset = queryset.filter(approval_status=approval_status)

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(agent__email__icontains=search) |
                Q(agent__full_name__icontains=search) |
                Q(agent__phone__icontains=search) |
                Q(agent__agency_name__icontains=search) |
                Q(agent__company__icontains=search) |
                Q(agent__country__icontains=search) |
                Q(agent__city__icontains=search)
            )

        paginator = CustomPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request, view=self)
        serializer = TalentListSerializer(paginated_queryset, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AdminTalentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get_object(self, request, talent_id):
        try:
            return Talent.objects.get(talent_id=talent_id)
        except Talent.DoesNotExist:
            return None

    def get(self, request, talent_id):
        try:
            talent = Talent.objects.get(talent_id=talent_id)
        except Talent.DoesNotExist:
            return Response(
                {"status": False, "status_code": 404, "message": "Talent not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TalentSerializer(talent, context={'request': request})
        return Response(
            {"status": True, "status_code": 200, "data": serializer.data},
            status=status.HTTP_200_OK
        )
    
    def delete(self, request, talent_id):
        talent = self.get_object(request, talent_id)
        if not talent:
            return Response(
                {"status": False, "status_code": 404, "message": "Talent not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        with transaction.atomic():
            ShortListedTalent.objects.filter(talent=talent).delete()
            talent.role_assignments.all().delete()
            talent.bookings.all().delete()
            talent.delete()
        return Response(
            {"status": True, "status_code": 200, "message": "Talent deleted successfully."},
            status=status.HTTP_200_OK
        )


class AdminTalentApprovalAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def patch(self, request, talent_id):
        try:
            talent = Talent.objects.get(talent_id=talent_id)
        except Talent.DoesNotExist:
            return Response(
                {"status": False, "status_code": 404, "message": "Talent not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TalentApprovalSerializer(talent, data=request.data, partial=True)
        if serializer.is_valid():
            talent = serializer.save()

            if talent.approval_status == "approved":
                talent.approved_by = request.user
                talent.approved_at = timezone.now()
                talent.rejection_reason = None
            elif talent.approval_status == "rejected":
                talent.approved_by = None
                talent.approved_at = None

            talent.save()

            return Response(
                {
                    "status": True,
                    "status_code": 200,
                    "message": f"Talent {talent.approval_status} successfully.",
                    "data": TalentSerializer(talent).data
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {"status": False, "status_code": 400, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )


class TalentApprovalAPIView(APIView):

    def patch(self, request):
        try:
            talent_id = request.data.get("talent_id")
            action = request.data.get("action")  # approve / reject
            message = request.data.get("message")

            if not talent_id or not action:
                return Response(
                    {"error": "talent_id and action are required"},
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
                talent = Talent.objects.select_related("agent").get(pk=talent_id)
            except Talent.DoesNotExist:
                return Response(
                    {"error": "Talent not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if talent.approval_status != "pending":
                return Response({"error": "Talent already processed"}, status=400)

            # Update status
            if action == "approve":
                talent.approval_status = "approved"
                talent.rejection_reason = None
                subject = "Congratulations! Your talent has been approved"
                message = (
                    "We are pleased to inform you that your talent profile has been approved. "
                    "Your profile is now active and visible to clients for potential opportunities. "
                    "You can start receiving job requests shortly."
                )
            else:
                talent.approval_status = "rejected"
                talent.rejection_reason = message
                subject = "Sorry! Your talent has been rejected"

            talent.approved_by = request.user
            talent.approved_at = timezone.now()
            talent.save()

            # Send email (optional but recommended). Failures shouldn't break approval.
            email_error = None
            if subject and message:
                try:
                    send_email(
                        to_email=talent.agent.email,
                        subject=subject,
                        message=message
                    )
                except Exception as e:
                    logger.exception("Failed to send talent approval email")
                    email_error = str(e)

            resp = {"message": f"Talent {action}d successfully"}
            if email_error:
                resp["email_error"] = email_error

            return Response(resp, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error in TalentApprovalAPIView.patch")
            return Response(
                {
                    "message": "An error occurred while processing the request.",
                    "error": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import Job, ShortListedTalent
from .serializers import JobWithShortlistedSerializer




class ShortListedTalentAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = JobWithShortlistedSerializer

    def get_queryset(self):
        return Job.objects.filter(
            job_created_by_id=self.request.user.user_id,
            status='active',
            shortlisted_count__gt=0
        ).prefetch_related(
            'shortlistedtalent_set__talent__images',
            'shortlistedtalent_set__talent__available_dates',
        )


# class ActiveJobDetailView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, job_id):
#         job = get_object_or_404(
#             Job,
#             job_id=job_id
#         )
#         if request.user.user_id == job.job_created_by_id:
#             serializer = JobWithShortlistedSerializer(job, context={'request': request})
#             return Response(serializer.data, status=status.HTTP_200_OK)
#         else:
#             return Response(
#                 {
#                     "success":False,
#                     "message":"Only Job Creator can access this page",
#                 }
#             )

class ActiveJobDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, job_id):
        job = get_object_or_404(
            Job,
            job_id=job_id
        )
        serializer = JobWithShortlistedSerializer(job, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    


class ShortlistReorderAPIView(APIView):
    """Save the drag-and-drop order of a job's shortlisted talents.

    PUT body: {"order": [shortlisted_id, shortlisted_id, ...]}  (first = top)
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, job_id):
        job = get_object_or_404(Job, job_id=job_id)
        if job.job_created_by_id != request.user.user_id:
            return Response(
                {"status": False, "status_code": 403, "message": "Only the job creator can reorder."},
                status=status.HTTP_403_FORBIDDEN
            )

        order = request.data.get("order")
        if not isinstance(order, list) or not order or not all(isinstance(i, int) for i in order):
            return Response(
                {"status": False, "status_code": 400, "message": "'order' must be a non-empty list of shortlisted_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if len(set(order)) != len(order):
            return Response(
                {"status": False, "status_code": 400, "message": "'order' contains duplicate ids."},
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_ids = set(
            ShortListedTalent.objects.filter(job=job, shortlisted_id__in=order)
            .values_list("shortlisted_id", flat=True)
        )
        invalid = [i for i in order if i not in valid_ids]
        if invalid:
            return Response(
                {"status": False, "status_code": 400, "message": f"Not shortlisted in this job: {invalid}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            ShortlistOrder.objects.filter(job_id=job.job_id).delete()
            ShortlistOrder.objects.bulk_create([
                ShortlistOrder(shortlisted_id=sid, job_id=job.job_id, position=pos)
                for pos, sid in enumerate(order, start=1)
            ])

        return Response(
            {"status": True, "status_code": 200, "message": "Shortlist order saved."},
            status=status.HTTP_200_OK
        )


class PublicShortListedTalentAPIView(APIView):

    def get(self, request):
        job_id = request.query_params.get("job_id")

        queryset = ShortListedTalent.objects.select_related(
            "job", "talent", "talent__agent"
        ).prefetch_related("talent__images")

        if job_id:
            queryset = queryset.filter(job_id=job_id)

        if not queryset.exists():
            return Response({
                "status": False,
                "message": "No shortlisted talents found"
            }, status=status.HTTP_404_NOT_FOUND)

        # -----------------------------
        # ✅ CASE 1: job_id provided → character-wise grouping
        # -----------------------------
        if job_id:
            obj = queryset.first()  # since all belong to same job

            data = {
                "job_id": obj.job_id,
                "job_title": obj.job.title if obj.job else None,
                "job_description": obj.job.description if obj.job else None,
                "characters": {
                    "lead_male": [],
                    "lead_female": [],
                    "extra": []
                }
            }

            for obj in queryset:
                character = obj.talent.character if obj.talent else None

                talent_data = {
                    "talent_id": obj.talent_id,
                    "talent_name": obj.talent.name,
                    "talent_role": obj.talent.role,
                    "available_dates": obj.talent.available_dates.all().values_list("available_date", flat=True),
                    "location": obj.talent.location if obj.talent else None,
                    "agency_name": obj.talent.agent.agency_name if obj.talent and obj.talent.agent else None,
                    "image": obj.talent.images.first().image.url if obj.talent and obj.talent.images.exists() else None,
                    "created_at": obj.created_at,
                }

                if character in data["characters"]:
                    data["characters"][character].append(talent_data)
                else:
                    data["characters"].setdefault("others", []).append(talent_data)

        # -----------------------------
        # ✅ CASE 2: no job_id → previous format
        # -----------------------------
        else:
            grouped_data = {}

            for obj in queryset:
                j_id = obj.job_id

                if j_id not in grouped_data:
                    grouped_data[j_id] = {
                        "job_id": j_id,
                        "job_title": obj.job.title if obj.job else None,
                        "job_description": obj.job.description if obj.job else None,
                        "talents": []
                    }

                grouped_data[j_id]["talents"].append({
                    "talent_id": obj.talent_id,
                    "talent_name": obj.talent.name,
                    "talent_role": obj.talent.role,
                    "character": obj.talent.character,
                    "available_dates": obj.talent.available_dates.all().values_list("available_date", flat=True),
                    "location": obj.talent.location if obj.talent else None,
                    "agency_name": obj.talent.agent.agency_name if obj.talent and obj.talent.agent else None,
                    "image": obj.talent.images.first().image.url if obj.talent and obj.talent.images.exists() else None,
                    "created_at": obj.created_at,
                })

            data = list(grouped_data.values())
            paginator = CustomPagination()
            paginated_data = paginator.paginate_queryset(data, request, view=self)
            return paginator.get_paginated_response(paginated_data)

        return Response({
            "status": True,
            "status_code": 200,
            "data": data
        }, status=status.HTTP_200_OK)


class WebImagesAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        obj = WebImages.load()
        serializer = WebImagesSerializer(obj, context={'request': request})
        return Response({
            "status": True,
            "status_code": 200,
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def put(self, request):
        obj = WebImages.load()
        serializer = WebImagesSerializer(
            obj, 
            data=request.data, 
            partial=True, 
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": True,
                "status_code": 200,
                "message": "Web images updated successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "status": False,
            "status_code": 400,
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class PublicWebImagesAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        obj = WebImages.load()
        serializer = WebImagesSerializer(obj, context={'request': request})
        return Response({
            "status": True,
            "status_code": 200,
            "data": serializer.data
        }, status=status.HTTP_200_OK)

class TeamListCreateAPIView(generics.ListCreateAPIView):
    queryset = Team.objects.all().order_by('-created_at')
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

class PublicTeamListAPIView(generics.ListAPIView):
    queryset = Team.objects.all().order_by('-created_at')
    serializer_class = TeamSerializer
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

class TeamDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
