import uuid
from django.utils.timezone import now
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import EcastingSession, EcastingParticipant, EcastingInvite
from .serializers import *
from ecasting.zego_token import generate_zego_token


# CREATE SESSION
class CreateSessionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        room_id = f"room_{uuid.uuid4().hex[:8]}"
        job_id = request.data.get("job_id")
        scheduled_date = request.data.get("scheduled_date")
        title = request.data.get("title")

        check_session = EcastingSession.objects.filter(job_id=job_id).first()

        # if check_session:
        #     return Response({
        #         "status": False,
        #         "message": "Job already scheduled at {}".format(check_session.scheduled_at)
        #     }, status=400)

        if not job_id or not scheduled_date:
            return Response({
                "status": False,
                "message": "Job ID and scheduled date are required"
            }, status=400)

        session = EcastingSession.objects.create(
            room_id=room_id,
            job_id=job_id,
            scheduled_at=scheduled_date,
            created_by=request.user,
            title=title or None
        )

        # creator is host
        EcastingParticipant.objects.create(
            session=session,
            user=request.user,
            is_host=True,
            joined_at=now()
        )

        join_link = f"{settings.FRONTEND_URL}/room/{room_id}"

        return Response({
            "status": True,
            "message": "Session created",
            "data": {
                "job_id": job_id,
                "title": title,
                "session": session.session_id,
                "room_id": room_id,
                "join_link": join_link
            }
        })


# ✅ INVITE USERS
class InviteUsersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        user_ids = request.data.get("user_ids", [])

        try:
            session = EcastingSession.objects.get(session_id=session_id)
        except EcastingSession.DoesNotExist:
            return Response({"status": False, "message": "Session not found"}, status=404)

        for uid in user_ids:
            EcastingInvite.objects.get_or_create(
                session=session,
                user_id=uid
            )

        return Response({
            "status": True,
            "message": "Users invited successfully"
        })

from django.utils import timezone
class JoinSessionAPIView(APIView):

    def get(self, request, room_id):
        try:
            session = EcastingSession.objects.get(room_id=room_id)
        except EcastingSession.DoesNotExist:
            return Response({"status": False, "message": "Session not found"}, status=404)

        # check invite (optional)
        # invited = EcastingInvite.objects.filter(
        #     session=session
        # ).exists()

        # if session.created_by != request.user and not invited:
        #     return Response({
        #         "status": False,
        #         "message": "You are not invited"
        #     }, status=403)

        if session.scheduled_at > timezone.now():
            return Response({
                "status": False,
                "message": "Session is not started yet"
            }, status=403)

        participant, created = EcastingParticipant.objects.get_or_create(
            session=session,
            user=request.user if request.user.is_authenticated else None
        )

        participant.joined_at = now()
        participant.save()

        if request.user.is_authenticated:
            token = generate_zego_token(request.user.user_id)
        else:
            token = generate_zego_token(str(uuid.uuid4()))


        join_link = f"{settings.FRONTEND_URL}/room/{room_id}"


        return Response({
            "status": True,
            "message": "Joined successfully",
            "data": {
                "token": token,
                "app_id": settings.ZEGO_APP_ID,
                "room_id": room_id,
                "join_link": join_link,
                "user_id": str(request.user.user_id) if request.user.is_authenticated else str(uuid.uuid4()),
            }
        })


# ✅ LEAVE SESSION
class LeaveSessionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        try:
            session = EcastingSession.objects.get(room_id=room_id)
        except EcastingSession.DoesNotExist:
            return Response({"status": False, "message": "Session not found"}, status=404)

        try:
            participant = EcastingParticipant.objects.get(
                session=session,
                user=request.user
            )
            participant.left_at = now()
            participant.save()
        except EcastingParticipant.DoesNotExist:
            pass

        return Response({
            "status": True,
            "message": "Left session"
        })


# ✅ SESSION DETAILS
class SessionDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        try:
            session = EcastingSession.objects.get(room_id=room_id)
        except EcastingSession.DoesNotExist:
            return Response({"status": False, "message": "Session not found"}, status=404)

        participants = session.participants.select_related("user")

        data = {
            "room_id": session.room_id,
            "title": session.title,
            "participants": [
                {
                    "user_id": p.user.user_id,
                    "name": getattr(p.user, "full_name", ""),
                    "joined_at": p.joined_at,
                    "is_host": p.is_host
                }
                for p in participants
            ]
        }

        return Response({
            "status": True,
            "data": data
        })
    
