import json

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from talent.models import ShortListedTalent

from .casting_requests_utils import get_or_create_ai_result
from .job_management_utils import (
    build_job_response,
    parse_budget,
    parse_roles_input,
    send_job_update_email,
)
from .models import (
    Booking,
    Job,
    JobAIResult,
    JobRole,
    JobRoleAssignment,
    Notifications,
    PolaLink,
    PolaRequest,
    SelfTapeLink,
    SelfTapeRequest,
)

User = get_user_model()

EDITABLE_FIELDS = (
    "title",
    "description",
    "location",
    "shoot_dates",
    "budget_range",
    "currency",
    "casting_roles",
    "add_roles",
    "remove_roles",
)


class EditJobAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, job_id):
        user_id = request.user.user_id
        data = request.data

        job = Job.objects.filter(job_id=job_id, job_created_by_id=user_id).first()
        if not job:
            return Response(
                {"status_code": 404, "status_message": "Job not found or unauthorized"}, status=404
            )

        if job.status != "active":
            return Response(
                {"status_code": 400, "status_message": "Only active jobs can be edited."}, status=400
            )

        if not any(field in data for field in EDITABLE_FIELDS):
            return Response({"status_code": 400, "status_message": "No fields to update."}, status=400)

        changes = []

        try:
            with transaction.atomic():
                if "title" in data and data["title"] != job.title:
                    job.title = data["title"]
                    changes.append(f"title to '{data['title']}'")

                if "description" in data and data["description"] != job.description:
                    job.description = data["description"]
                    changes.append("description")

                if "location" in data and data["location"] != job.location:
                    job.location = data["location"]
                    changes.append(f"location to '{data['location']}'")

                if "budget_range" in data:
                    budget_range = data["budget_range"]
                    parsed_min, parsed_max, parsed_currency = parse_budget(budget_range)
                    if parsed_min != job.budget_min or parsed_max != job.budget_max:
                        job.budget_min = parsed_min
                        job.budget_max = parsed_max
                        changes.append(f"budget to '{budget_range}'")
                    if "currency" not in data and parsed_currency != job.currency:
                        job.currency = parsed_currency
                        changes.append(f"currency to '{parsed_currency}'")

                if "currency" in data and data["currency"] != job.currency:
                    job.currency = data["currency"]
                    changes.append(f"currency to '{data['currency']}'")

                if "shoot_dates" in data:
                    shoot_dates = data["shoot_dates"]
                    ai_result = get_or_create_ai_result(int(job.job_id))
                    new_value = json.dumps(shoot_dates)
                    if new_value != (ai_result.shoot_date or ""):
                        ai_result.shoot_date = new_value
                        ai_result.save(update_fields=["shoot_date"])
                        changes.append(f"shoot date to {', '.join(shoot_dates)}")

                if any(field in data for field in ("casting_roles", "add_roles", "remove_roles")):
                    if self._apply_role_changes(job, data):
                        changes.append("casting roles")

                if not changes:
                    return Response(
                        {"status_code": 200, "status_message": "No changes detected."}, status=200
                    )

                job.save()
                self._notify(job, changes, user_id)
        except Exception as e:
            return Response(
                {"status_code": 500, "status_message": f"Database error during job update: {e}"},
                status=500,
            )

        return Response(
            {
                "status_code": 200,
                "status_message": "Job updated successfully. Relevant talent have been notified.",
                "data": build_job_response(job),
            },
            status=200,
        )

    def _apply_role_changes(self, job, data):
        existing_roles_set = set(JobRole.objects.filter(job=job).values_list("job_role", flat=True))

        if "add_roles" in data or "remove_roles" in data:
            roles_to_add = parse_roles_input(data.get("add_roles")) - existing_roles_set
            roles_to_remove = parse_roles_input(data.get("remove_roles")) & existing_roles_set
        else:
            target = parse_roles_input(data.get("casting_roles"))
            roles_to_add = target - existing_roles_set
            roles_to_remove = existing_roles_set - target

        if not roles_to_add and not roles_to_remove:
            return False

        if roles_to_remove:
            roles_qs = JobRole.objects.filter(job=job, job_role__in=roles_to_remove)
            role_ids = list(roles_qs.values_list("id", flat=True))
            if role_ids:
                JobRoleAssignment.objects.filter(job_role_id__in=role_ids).delete()
            roles_qs.delete()

        for name in roles_to_add:
            JobRole.objects.create(job=job, job_role=name, talent=None)

        final_set = (existing_roles_set - roles_to_remove) | roles_to_add
        job.casting_roles = json.dumps(sorted(final_set))
        return True

    def _notify(self, job, changes, user_id):
        numeric_job_id = int(job.job_id)
        agent_ids = set(
            ShortListedTalent.objects.filter(job=job).values_list("talent__agent_id", flat=True)
        ) | set(
            Booking.objects.filter(job_id=numeric_job_id).values_list("talent__agent_id", flat=True)
        )
        agent_ids.discard(None)
        if not agent_ids:
            return

        agents = list(User.objects.filter(user_id__in=agent_ids))
        change_str = ", ".join(changes)

        Notifications.objects.bulk_create(
            [
                Notifications(
                    receiver=agent,
                    sender_id=user_id,
                    event=(
                        f"The details for the job '{job.title}' have been updated. "
                        f"Changes were made to the {change_str}."
                    ),
                )
                for agent in agents
            ]
        )

        for agent in agents:
            if agent.email:
                send_job_update_email(agent, job, change_str)


class DeleteJobAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user_id = request.user.user_id
        job_id = request.query_params.get("job_id")
        if not job_id:
            return Response({"status_code": 400, "status_message": "job_id is required"}, status=400)

        job = Job.objects.filter(job_id=job_id, job_created_by_id=user_id).first()
        if not job:
            return Response(
                {"status_code": 404, "status_message": "Job not found or unauthorized"}, status=404
            )

        numeric_job_id = int(job.job_id)

        try:
            with transaction.atomic():
                st_requests = SelfTapeRequest.objects.filter(job_id=numeric_job_id)
                SelfTapeLink.objects.filter(request__in=st_requests).delete()
                st_requests.delete()

                pola_requests = PolaRequest.objects.filter(job_id=numeric_job_id)
                PolaLink.objects.filter(request__in=pola_requests).delete()
                pola_requests.delete()

                JobAIResult.objects.filter(job_id=numeric_job_id).delete()

                ShortListedTalent.objects.filter(job=job).update(job=None)
                Booking.objects.filter(job_id=numeric_job_id).update(job_id=None)

                role_ids = list(JobRole.objects.filter(job=job).values_list("id", flat=True))
                if role_ids:
                    JobRoleAssignment.objects.filter(job_role_id__in=role_ids).delete()
                JobRole.objects.filter(job=job).delete()

                job.delete()
        except Exception as e:
            return Response({"status_code": 500, "status_message": f"Failed to delete job: {e}"}, status=500)

        return Response({"status_code": 200, "status_message": "Job deleted successfully"}, status=200)
