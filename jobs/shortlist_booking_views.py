from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from talent.models import ShortListedTalent, Talent, TalentAvailableDate

from .casting_requests_utils import create_notification
from .models import Booking, Job, JobRole, JobRoleAssignment
from .shortlist_booking_utils import (
    build_shortlist_filters,
    resolve_job_and_shoot_date,
    resolve_job_display_name,
    send_booking_email,
    send_shortlist_email,
)


def _parse_date(value):
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    return value


class ShortlistTalentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.user.user_id
        job_id = request.data.get("job_id")
        talent_id = request.data.get("talent_id")
        session_id = request.data.get("session_id")

        talent = Talent.objects.filter(talent_id=talent_id).first()
        if not talent:
            return Response({"status_code": 404, "status_message": "Talent not found"}, status=404)

        job, shoot_date_str = resolve_job_and_shoot_date(user_id, job_id=job_id, session_id=session_id)

        if not job and not session_id:
            return Response(
                {"status_code": 400, "status_message": "Missing job_id or session_id"}, status=400
            )

        filters = build_shortlist_filters(user_id, talent, job, session_id)
        if ShortListedTalent.objects.filter(filters).exists():
            return Response(
                {"status_code": 400, "status_message": f"Talent {talent.name} already shortlisted."},
                status=400,
            )

        try:
            with transaction.atomic():
                if job:
                    job.shortlisted_count = (job.shortlisted_count or 0) + 1
                    job.save(update_fields=["shortlisted_count"])

                ShortListedTalent.objects.create(
                    session_id=session_id,
                    user_id=user_id,
                    talent=talent,
                    job=job,
                    created_at=timezone.now(),
                )

                job_display_name = resolve_job_display_name(job, session_id)

                create_notification(
                    receiver_id=talent.agent_id,
                    sender_id=user_id,
                    event=(
                        f"{talent.name} has been shortlisted for the project "
                        f"'{job_display_name}'{shoot_date_str}."
                    ),
                )

                agent = talent.agent
                if agent and agent.email:
                    send_shortlist_email(agent, talent, job_display_name, shoot_date_str)
        except Exception as e:
            return Response(
                {"status_code": 500, "status_message": f"Failed to shortlist talent: {e}"}, status=500
            )

        return Response(
            {"status_code": 200, "status_message": f"Talent {talent.name} shortlisted."}, status=200
        )


class DeleteShortlistAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user_id = request.user.user_id
        talent_id = request.query_params.get("talent_id")
        job_id = request.query_params.get("job_id")
        session_id = request.query_params.get("session_id")

        if not talent_id:
            return Response({"status_code": 400, "status_message": "talent_id is required"}, status=400)

        filters = Q(user_id=user_id, talent_id=talent_id)
        job = None
        if job_id:
            filters &= Q(job_id=job_id)
            job = Job.objects.filter(job_id=job_id, job_created_by_id=user_id).first()
        elif session_id:
            filters &= Q(session_id=session_id, job__isnull=True)
        else:
            return Response(
                {"status_code": 400, "status_message": "Missing job_id or session_id"}, status=400
            )

        record = ShortListedTalent.objects.filter(filters).first()
        if not record:
            return Response({"status_code": 404, "status_message": "Shortlist record not found"}, status=404)

        try:
            with transaction.atomic():
                if job:
                    job.shortlisted_count = max((job.shortlisted_count or 0) - 1, 0)
                    job.save(update_fields=["shortlisted_count"])
                record.delete()
        except Exception as e:
            return Response(
                {"status_code": 500, "status_message": f"Failed to remove from shortlist: {e}"}, status=500
            )

        return Response(
            {"status_code": 200, "status_message": "Talent removed from shortlist successfully."}, status=200
        )


class DeleteAllShortlistsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user_id = request.user.user_id
        job_id = request.query_params.get("job_id")
        if not job_id:
            return Response({"status_code": 400, "status_message": "job_id is required"}, status=400)

        job = Job.objects.filter(job_id=job_id, job_created_by_id=user_id).first()
        if not job:
            return Response(
                {"status_code": 404, "status_message": "Job not found or unauthorized."}, status=404
            )

        try:
            with transaction.atomic():
                deleted_count, _ = ShortListedTalent.objects.filter(user_id=user_id, job=job).delete()
                if deleted_count == 0:
                    return Response(
                        {"status_code": 200, "status_message": "No shortlisted talents to remove for this job."},
                        status=200,
                    )
                job.shortlisted_count = 0
                job.save(update_fields=["shortlisted_count"])
        except Exception as e:
            return Response(
                {"status_code": 500, "status_message": f"Failed to delete shortlists: {e}"}, status=500
            )

        return Response(
            {
                "status_code": 200,
                "status_message": (
                    f"Successfully removed {deleted_count} talent(s) from the shortlist for job - "
                    f"'{job.title}'."
                ),
            },
            status=200,
        )


class BookTalentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.user.user_id
        job_id = request.data.get("job_id")
        talent_id = request.data.get("talent_id")
        session_id = request.data.get("session_id")
        booking_dates_raw = request.data.get("booking_dates") or []

        talent = Talent.objects.filter(talent_id=talent_id).first()
        if not talent:
            return Response({"status_code": 404, "status_message": "Talent not found"}, status=404)

        if not booking_dates_raw:
            return Response(
                {"status_code": 400, "status_message": "At least one booking date must be provided."},
                status=400,
            )

        try:
            booking_dates = sorted({_parse_date(d) for d in booking_dates_raw})
        except (ValueError, TypeError):
            return Response({"status_code": 400, "status_message": "Invalid date format."}, status=400)

        available_dates = set(
            TalentAvailableDate.objects.filter(
                talent=talent, available_date__in=booking_dates, is_active=True
            ).values_list("available_date", flat=True)
        )
        missing = sorted(set(booking_dates) - available_dates)
        if missing:
            missing_str = ", ".join(d.strftime("%Y-%m-%d") for d in missing)
            return Response(
                {
                    "status_code": 400,
                    "status_message": (
                        f"Talent {talent.name} is not available on the following date(s): {missing_str}."
                    ),
                },
                status=400,
            )

        job, _ = resolve_job_and_shoot_date(user_id, job_id=job_id, session_id=session_id)

        booking_filters = Q(user_id=user_id, talent=talent, booking_date__in=booking_dates)
        if job:
            booking_filters &= Q(job_id=int(job.job_id))
        elif session_id:
            booking_filters &= Q(session_id=session_id, job_id__isnull=True)

        conflicting = sorted(
            set(Booking.objects.filter(booking_filters).values_list("booking_date", flat=True))
        )
        if conflicting:
            conflict_str = ", ".join(d.strftime("%Y-%m-%d") for d in conflicting)
            return Response(
                {
                    "status_code": 400,
                    "status_message": (
                        f"Talent {talent.name} is already booked for the following date(s): {conflict_str}."
                    ),
                },
                status=400,
            )

        role_names = []
        if job:
            for name in JobRoleAssignment.objects.filter(
                job_id=int(job.job_id), talent=talent
            ).values_list("job_role__job_role", flat=True):
                if name not in role_names:
                    role_names.append(name)

            for name in JobRole.objects.filter(job=job, talent=talent).values_list("job_role", flat=True):
                if name not in role_names:
                    role_names.append(name)

        role_text = f" as {', '.join(role_names)}" if role_names else ""

        try:
            with transaction.atomic():
                shortlist_filters = build_shortlist_filters(user_id, talent, job, session_id)
                if not ShortListedTalent.objects.filter(shortlist_filters).exists():
                    ShortListedTalent.objects.create(
                        session_id=session_id,
                        user_id=user_id,
                        talent=talent,
                        job=job,
                        created_at=timezone.now(),
                    )
                    if job:
                        job.shortlisted_count = (job.shortlisted_count or 0) + 1
                        job.save(update_fields=["shortlisted_count"])

                for d in booking_dates:
                    Booking.objects.create(
                        session_id=session_id,
                        user_id=user_id,
                        talent=talent,
                        job_id=int(job.job_id) if job else None,
                        booking_date=d,
                    )

                job_display_name = resolve_job_display_name(job, session_id)
                booking_dates_str = ", ".join(d.strftime("%B %d, %Y") for d in booking_dates)

                create_notification(
                    receiver_id=talent.agent_id,
                    sender_id=user_id,
                    event=(
                        f"Booking Confirmation: {talent.name} has been booked for '{job_display_name}' "
                        f"for the shoot on {booking_dates_str}{role_text}."
                    ),
                )

                agent = talent.agent
                if agent and agent.email:
                    send_booking_email(agent, talent, job_display_name, booking_dates_str, role_names)

                TalentAvailableDate.objects.filter(
                    talent=talent, available_date__in=booking_dates, is_active=True
                ).update(is_active=False)
        except Exception as e:
            return Response({"status_code": 500, "status_message": f"Failed to book talent: {e}"}, status=500)

        return Response(
            {
                "status_code": 200,
                "status_message": (
                    f"Talent {talent.name} booked successfully for {booking_dates_str}{role_text}."
                ),
            },
            status=200,
        )
