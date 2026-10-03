from django.db import transaction
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from talent.models import Talent

from .models import Job, JobRole, JobRoleAssignment


class AvailableRolesAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        job_id = request.query_params.get("job_id")
        session_id = request.query_params.get("session_id")

        if job_id:
            job_identifier = job_id
        elif session_id:
            job = Job.objects.filter(session_id=session_id).order_by("-created_at").first()
            if not job:
                return Response([], status=200)
            job_identifier = job.job_id
        else:
            return Response(
                {"status_code": 400, "status_message": "Must provide job_id or session_id"}, status=400
            )

        roles = JobRole.objects.filter(job_id=job_identifier).order_by("job_role", "id")

        groups = []
        group_index_by_name = {}
        for role in roles:
            if role.job_role not in group_index_by_name:
                group_index_by_name[role.job_role] = len(groups)
                groups.append([])
            groups[group_index_by_name[role.job_role]].append(role)

        result = []
        for group in groups:
            canonical = group[0]
            talent_ids = [r.talent_id for r in group if r.talent_id is not None]
            result.append(
                {
                    "id": canonical.id,
                    "job_role": canonical.job_role,
                    "assign_status": bool(talent_ids),
                    "talent_id": talent_ids,
                    "session_id": None,
                }
            )

        return Response(result, status=200)


class AssignRoleAPIView(APIView):
    # Deliberately stricter than the FastAPI version, which has no auth on this endpoint
    # at all - that's a gap on their side, not something to mirror here (flagged to the
    # team to patch there too). Every other job-mutating endpoint in this project
    # requires a JWT and checks job ownership, so this does too.
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role_id = request.data.get("id")
        talent_id = request.data.get("talent_id")

        if role_id is None or talent_id is None:
            return Response(
                {"status_code": 400, "status_message": "id and talent_id are required"}, status=400
            )

        source_role = JobRole.objects.filter(id=role_id).first()
        if not source_role:
            return Response({"status_code": 404, "status_message": "Role not found."}, status=404)

        job = Job.objects.filter(job_id=source_role.job_id).first()
        if not job or job.job_created_by_id != request.user.user_id:
            return Response(
                {"status_code": 403, "status_message": "You do not have permission to modify this job's roles."},
                status=403,
            )

        talent = Talent.objects.filter(talent_id=talent_id).first()
        if not talent:
            return Response({"status_code": 404, "status_message": "Talent not found."}, status=404)

        already_assigned_message = (
            f"Talent is already assigned to the role '{source_role.job_role}'."
        )

        if source_role.talent_id == talent.talent_id:
            return Response({"status_code": 200, "status_message": already_assigned_message}, status=200)

        existing = JobRole.objects.filter(
            job_id=source_role.job_id, job_role=source_role.job_role, talent_id=talent.talent_id
        ).first()
        if existing:
            return Response({"status_code": 200, "status_message": already_assigned_message}, status=200)

        try:
            with transaction.atomic():
                new_role = JobRole.objects.create(
                    job_id=source_role.job_id,
                    job_role=source_role.job_role,
                    talent_id=talent.talent_id,
                    assign_status=True,
                )
                JobRoleAssignment.objects.create(
                    job_id=source_role.job_id,
                    job_role_id=new_role.id,
                    talent_id=talent.talent_id,
                )
        except Exception as e:
            return Response({"status_code": 500, "status_message": f"Failed to assign role: {e}"}, status=500)

        return Response(
            {
                "status_code": 200,
                "status_message": f"Talent successfully assigned to role '{source_role.job_role}'.",
            },
            status=200,
        )


class UnassignRoleAPIView(APIView):
    # Same deliberate deviation from FastAPI as AssignRoleAPIView - see its comment.
    permission_classes = [IsAuthenticated]

    def _handle(self, request):
        job_role_id = request.query_params.get("job_role_id")
        job_id = request.query_params.get("job_id")

        if not job_role_id and not job_id:
            return Response(
                {"status_code": 400, "status_message": "Provide either job_role_id or job_id."}, status=400
            )

        if job_role_id:
            target_role = JobRole.objects.filter(id=job_role_id).first()
        else:
            assigned_roles = list(JobRole.objects.filter(job_id=job_id, talent_id__isnull=False))
            if len(assigned_roles) == 0:
                return Response(
                    {"status_code": 404, "status_message": "No assigned role found for the provided job_id."},
                    status=404,
                )
            if len(assigned_roles) > 1:
                return Response(
                    {
                        "status_code": 400,
                        "status_message": (
                            "Multiple assigned roles found for this job. "
                            "Use job_role_id to unassign a specific role."
                        ),
                    },
                    status=400,
                )
            target_role = assigned_roles[0]

        if not target_role:
            return Response({"status_code": 404, "status_message": "Role not found."}, status=404)

        job = Job.objects.filter(job_id=target_role.job_id).first()
        if not job or job.job_created_by_id != request.user.user_id:
            return Response(
                {"status_code": 403, "status_message": "You do not have permission to modify this job's roles."},
                status=403,
            )

        if target_role.talent_id is not None:
            assigned_row = target_role
        else:
            assigned_row = (
                JobRole.objects.filter(
                    job_id=target_role.job_id, job_role=target_role.job_role, talent_id__isnull=False
                )
                .order_by("id")
                .first()
            )
            if not assigned_row:
                return Response(
                    {"status_code": 404, "status_message": "No assigned talent found for the provided role."},
                    status=404,
                )

        removed_talent_id = assigned_row.talent_id

        try:
            with transaction.atomic():
                JobRoleAssignment.objects.filter(
                    job_role_id=target_role.id, talent_id=removed_talent_id
                ).delete()

                if target_role.talent_id == removed_talent_id:
                    remaining = (
                        JobRoleAssignment.objects.filter(job_role_id=target_role.id).order_by("id").first()
                    )
                    if remaining:
                        target_role.talent_id = remaining.talent_id
                        target_role.assign_status = True
                    else:
                        target_role.talent_id = None
                        target_role.assign_status = False
                    target_role.save(update_fields=["talent", "assign_status"])
        except Exception as e:
            return Response({"status_code": 500, "status_message": f"Failed to unassign role: {e}"}, status=500)

        return Response(
            {"status_code": 200, "status_message": "Talent successfully unassigned from the role."}, status=200
        )

    def patch(self, request):
        return self._handle(request)

    def delete(self, request):
        return self._handle(request)
