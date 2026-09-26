from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from .models import Job, DraftJob, Meetings
from .serializers import *
from .services import get_jobs_for_agent
from core.pagination import CustomPagination
from django.db import transaction, IntegrityError



class ActiveJobAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id=None):
        user = request.user

        search = request.query_params.get("search")
        # 🔹 Base queryset
        if user.role == "Admin":
            queryset = Job.objects.all()
        elif user.role == "Agent":
            queryset = get_jobs_for_agent(agent_id=request.user.user_id).filter(status="active").order_by("-created_at")
            
        else:
            queryset = Job.objects.filter(job_created_by_id=user.user_id)

        # 🔹 Single job
        if job_id:
            job = queryset.filter(job_id=job_id).first()
            if not job:
                return Response({
                    "status": False,
                    "message": "Job not found"
                }, status=status.HTTP_404_NOT_FOUND)

            # preload AI
            ai = JobAIResult.objects.filter(job_id=job_id)
            
            ai_map = {str(a.job_id): a for a in ai}

           

            serializer = JobSerializer(
                job,
                context={"request": request, "ai_map": ai_map}
            )

            return Response({
                "status": True,
                "message": "Job fetched successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        # 🔹 Search
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(job_type__icontains=search) |
                Q(location__icontains=search)
            )

        queryset = queryset.order_by("-created_at")

        paginator = CustomPagination()
        jobs = paginator.paginate_queryset(queryset, request, view=self)

        # preload all AI results (optimized)
        job_ids = [str(job.job_id) for job in jobs]
        ai_results = JobAIResult.objects.filter(job_id__in=job_ids)
        ai_map = {str(ai.job_id): ai for ai in ai_results}
        # print(ai_map)

        serializer = JobSerializer(
            jobs,
            many=True,
            context={
                "request": request,
                "ai_map": ai_map
            }
        )

        return paginator.get_paginated_response(serializer.data)


    def delete(self, request, job_id=None):
        user = request.user
       

        if not job_id:
            return Response({"status": False, "message": "job_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # scope the queryset similarly to GET so user can only delete what they are allowed to
        if user.role == "Admin":
            queryset = Job.objects.all()
        elif user.role == "Agent":
            # Agents should not be allowed to delete jobs (change if your rules differ)
            return Response({"status": False, "message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        else:
            queryset = Job.objects.filter(job_created_by_id=user.user_id)

        job = queryset.filter(job_id=job_id).first()
        if not job:
            return Response({"status": False, "message": "Job not found or permission denied"}, status=status.HTTP_404_NOT_FOUND)

        try:
            with transaction.atomic():
                job.delete()
        except IntegrityError as exc:
            return Response({"status": False, "message": "Unable to delete job due to related records.", "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": True, "message": "Job deleted successfully"}, status=status.HTTP_200_OK)

        



class DraftJobAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, draft_id=None):
        user = request.user

        if draft_id:
            single_job = DraftJob.objects.filter(draft_id=draft_id, user_id=request.user.user_id).first()
            if not single_job:
                return Response({
                    "status": False,
                    "message": "Job not found"
                }, status=status.HTTP_404_NOT_FOUND)
            else:
                serializer = DraftJobSerializer(single_job, context={'request': request})
                return Response({
                "status": True,
                "message": "Jobs fetched successfully",
                "data": serializer.data,
            }, status=status.HTTP_200_OK)

        search = request.query_params.get("search")
        if user.role == "Admin":
            return Response({"status": False, "message": "Admins can't access draft jobs"}, status=status.HTTP_403_FORBIDDEN)
        else:
            queryset = DraftJob.objects.filter(user_id=user.user_id)

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(job_type__icontains=search) |
                Q(location__icontains=search)
            )
        queryset = queryset.order_by("-last_updated")

        paginator = CustomPagination()
        jobs = paginator.paginate_queryset(queryset, request, view=self)

        serializer = DraftJobSerializer(jobs, many=True, context={'request': request})

        return paginator.get_paginated_response(serializer.data)


class JobAIResultAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        talent_id = request.query_params.get("talent_id")
        agent_id = request.query_params.get("agent_id")

        ai_result = JobAIResult.objects.filter(job_id=job_id).first()
    
        if not ai_result:
            return Response({
                "status": False,
                "message": "AI result not found"
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = JobAIResultSerializer(ai_result)
        data = serializer.data

        # Filter requested_selftapes if talent_id is provided
        if talent_id:
            try:
                talent_id = int(talent_id)

                data["suggested_talents"] = [
                    tape for tape in data.get("suggested_talents", [])
                    if tape.get("talent_id") == talent_id
                ]

                data["requested_selftapes"] = [
                    tape for tape in data.get("requested_selftapes", [])
                    if tape.get("talent_id") == talent_id
                ]

                data["requested_ecastings"] = [
                    tape for tape in data.get("requested_ecastings", [])
                    if tape.get("talent_id") == talent_id
                ]

                data["requested_polas"] = [
                    tape for tape in data.get("requested_polas", [])
                    if tape.get("talent_id") == talent_id
                ]
            except ValueError:
                return Response({
                    "status": False,
                    "message": "Invalid talent_id"
                }, status=status.HTTP_400_BAD_REQUEST)
            

        # Filter requested_selftapes if agent_id is provided
        if agent_id:
            try:
                agent_id = int(agent_id)

                data["suggested_talents"] = [
                    tape for tape in data.get("suggested_talents", [])
                    if tape.get("agent_id") == agent_id
                ]

                data["requested_selftapes"] = [
                    tape for tape in data.get("requested_selftapes", [])
                    if tape.get("agent_id") == agent_id
                ]

                data["requested_ecastings"] = [
                    tape for tape in data.get("requested_ecastings", [])
                    if tape.get("agent_id") == agent_id
                ]

                data["requested_polas"] = [
                    tape for tape in data.get("requested_polas", [])
                    if tape.get("agent_id") == agent_id
                ]
            except ValueError:
                return Response({
                    "status": False,
                    "message": "Invalid agent_id"
                }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "status": True,
            "message": "AI result fetched successfully",
            "data": data
        }, status=status.HTTP_200_OK)

# class JobAIResultAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, job_id):
#         ai_result = JobAIResult.objects.filter(job_id=job_id).first()
    
#         if not ai_result:
#             return Response({
#                 "status": False,
#                 "message": "AI result not found"
#             }, status=status.HTTP_404_NOT_FOUND)

#         serializer = JobAIResultSerializer(ai_result)
#         return Response({
#             "status": True,
#             "message": "AI result fetched successfully",
#             "data": serializer.data
#         }, status=status.HTTP_200_OK)




class MeetingVideoRecordAll(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        
        meetings = Meetings.objects.filter(job__job_created_by_id=request.user.user_id).order_by("-id")
        paginator = CustomPagination()
        paginated_meetings = paginator.paginate_queryset(meetings, request, view=self)
        serializer = MeetingsSerializer(paginated_meetings, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)



class MeetingVideoRecord(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, job_id):
        try:
            job = Job.objects.get(job_id=job_id)
        except Job.DoesNotExist:
            return Response({
                "status": False,
                "message": "Job not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        meetings = Meetings.objects.filter(job=job).order_by("-id")
        paginator = CustomPagination()
        paginated_meetings = paginator.paginate_queryset(meetings, request, view=self)
        serializer = MeetingsSerializer(paginated_meetings, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, job_id):
        try:
            job = Job.objects.get(job_id=job_id)
        except Job.DoesNotExist:
            return Response({
                "status": False,
                "message": "Job not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        payload = request.data.copy()
        payload["job"] = job.job_id  # Use job_id instead of id
        # Backward compatibility: accept single meeting_record and map to records list.
        if payload.get("meeting_record") and not payload.get("records"):
            payload["records"] = [payload.get("meeting_record")]

        serializer = MeetingsSerializer(data=payload, context={'request': request})
        if serializer.is_valid():
            try:
                serializer.save()
                return Response({
                    "status": True,
                    "message": "Meeting record created successfully.",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({
                    "status": False,
                    "message": "Error saving meeting record",
                    "errors": str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                "status": False,
                "message": "Unable to create the meeting record.",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
