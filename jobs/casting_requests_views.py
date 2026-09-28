import json

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from talent.models import Talent

from .casting_requests_utils import (
    build_talent_snapshot,
    create_notification,
    get_multi_values,
    get_or_create_ai_result,
    normalize_url_list,
    parse_json_field,
    resolve_job_for_upload,
    resolve_owned_job,
    save_uploaded_file,
)
from .models import DraftJob, PolaLink, PolaRequest, SelfTapeLink, SelfTapeRequest


def _bump_draft_timestamp(session_id):
    if not session_id:
        return
    draft = DraftJob.objects.filter(session_id=session_id).first()
    if not draft:
        return
    saved_filters = parse_json_field(draft.saved_filters, {})
    saved_filters["last_updated_timestamp"] = timezone.now().isoformat()
    draft.saved_filters = json.dumps(saved_filters)
    draft.save(update_fields=["saved_filters"])


class BaseRequestMediaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    saved_filters_key = None
    job_count_field = None
    create_request_model = None
    already_added_message_draft = None
    already_added_message_job = None
    pending_message = None

    def post(self, request):
        user_id = request.user.user_id
        talent_id = request.data.get("talent_id")
        job_id = request.data.get("job_id")
        session_id = request.data.get("session_id")

        if not talent_id:
            return Response(
                {"status_code": 400, "status_message": "talent_id is required"}, status=400
            )

        talent = Talent.objects.filter(talent_id=talent_id).first()
        if not talent:
            return Response({"status_code": 404, "status_message": "Talent not found"}, status=404)

        job = resolve_owned_job(user_id, job_id=job_id, session_id=session_id)

        with transaction.atomic():
            if not job:
                return self._handle_no_job(request, user_id, talent, session_id)
            return self._handle_existing_job(request, user_id, talent, job)

    def _handle_no_job(self, request, user_id, talent, session_id):
        if not session_id:
            return Response(
                {"status_code": 400, "status_message": "Job not found and no session_id provided"},
                status=400,
            )

        draft = DraftJob.objects.filter(session_id=session_id, user_id=user_id).first()
        if not draft:
            return Response(
                {"status_code": 404, "status_message": "Session not found to store request"}, status=404
            )

        saved_filters = parse_json_field(draft.saved_filters, {})
        snapshots = saved_filters.get(self.saved_filters_key, [])
        if any(str(t.get("talent_id")) == str(talent.talent_id) for t in snapshots):
            return Response(
                {"status_code": 400, "status_message": self.already_added_message_draft}, status=400
            )

        snapshot = build_talent_snapshot(
            talent, None, request, include_status_tapes=self.create_request_model is not None
        )
        snapshots.append(snapshot)
        saved_filters[self.saved_filters_key] = snapshots
        saved_filters["last_updated_timestamp"] = timezone.now().isoformat()
        draft.saved_filters = json.dumps(saved_filters)
        draft.save(update_fields=["saved_filters"])

        receiver_id = talent.agent_id or user_id
        create_notification(
            receiver_id=receiver_id,
            sender_id=user_id,
            event=self.notification_event(talent, draft.title or "a new project"),
        )

        return Response(
            {
                "status_code": 200,
                "status_message": f"{self.pending_message} {talent.name} (Pending job generation)",
            },
            status=200,
        )

    def _handle_existing_job(self, request, user_id, talent, job):
        ai_result = get_or_create_ai_result(int(job.job_id))
        snapshots = parse_json_field(getattr(ai_result, self.saved_filters_key), [])
        if any(str(t.get("talent_id")) == str(talent.talent_id) for t in snapshots):
            return Response(
                {"status_code": 400, "status_message": self.already_added_message_job}, status=400
            )

        setattr(job, self.job_count_field, (getattr(job, self.job_count_field) or 0) + 1)
        job.save(update_fields=[self.job_count_field])

        snapshot = build_talent_snapshot(
            talent, int(job.job_id), request, include_status_tapes=self.create_request_model is not None
        )
        snapshots.append(snapshot)
        setattr(ai_result, self.saved_filters_key, json.dumps(snapshots))
        ai_result.save(update_fields=[self.saved_filters_key])

        if self.create_request_model is not None:
            self.create_request_model.objects.create(
                job_id=int(job.job_id), talent_id=talent.talent_id, status="requested"
            )

        receiver_id = talent.agent_id or job.job_created_by_id
        create_notification(
            receiver_id=receiver_id,
            sender_id=user_id,
            event=self.notification_event(talent, job.title),
        )

        _bump_draft_timestamp(job.session_id)

        return Response(
            {"status_code": 200, "status_message": f"{self.pending_message} {talent.name}"},
            status=200,
        )

    def notification_event(self, talent, project_title):
        raise NotImplementedError


class RequestSelfTapeAPIView(BaseRequestMediaAPIView):
    saved_filters_key = "requested_selftapes"
    job_count_field = "selftapes_count"
    create_request_model = SelfTapeRequest
    already_added_message_draft = "Selftape already added"
    already_added_message_job = "Self-tape already added"
    pending_message = "Self-tape requested for"

    def notification_event(self, talent, project_title):
        return f"A self-tape has been requested for {talent.name} for the project '{project_title}'."


class RequestECastingAPIView(BaseRequestMediaAPIView):
    saved_filters_key = "requested_ecastings"
    job_count_field = "ecastings_count"
    create_request_model = None
    already_added_message_draft = "E-casting already added"
    already_added_message_job = "E-casting already added"
    pending_message = "E-casting requested for"

    def notification_event(self, talent, project_title):
        return f"An e-casting has been requested for {talent.name} for the project '{project_title}'."


class RequestPolasAPIView(BaseRequestMediaAPIView):
    saved_filters_key = "requested_polas"
    job_count_field = "polas_count"
    create_request_model = PolaRequest
    already_added_message_draft = "Polas already added"
    already_added_message_job = "Polas already added"
    pending_message = "Polas requested for"

    def notification_event(self, talent, project_title):
        return f"A polas request has been requested for {talent.name} for the project '{project_title}'."


class SelfTapeUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user_id = request.user.user_id
        talent_id = request.data.get("talent_id")
        job_id = request.data.get("job_id")
        session_id = request.data.get("session_id")

        if not talent_id:
            return Response({"status_code": 400, "status_message": "talent_id is required"}, status=400)
        if not job_id and not session_id:
            return Response(
                {"status_code": 400, "status_message": "job_id or session_id is required"}, status=400
            )

        talent = Talent.objects.filter(talent_id=talent_id).first()
        job = resolve_job_for_upload(user_id, job_id=job_id, session_id=session_id)
        if not talent or not job:
            return Response({"status_code": 404, "status_message": "Talent or job not found"}, status=404)

        allowed_ids = {talent.talent_id, talent.agent_id, job.job_created_by_id}
        if user_id not in allowed_ids:
            return Response(
                {"status_code": 403, "status_message": "Unauthorized to upload tapes for this talent."},
                status=403,
            )

        ai_result = get_or_create_ai_result(int(job.job_id))
        snapshots = parse_json_field(ai_result.requested_selftapes, [])
        snapshot = next(
            (t for t in snapshots if str(t.get("talent_id")) == str(talent.talent_id)), None
        )
        if not snapshot:
            return Response(
                {"status_code": 404, "status_message": "Self-tape request not found in job snapshot."},
                status=404,
            )

        with transaction.atomic():
            selftape_request, _ = SelfTapeRequest.objects.get_or_create(
                job_id=int(job.job_id), talent_id=talent.talent_id, defaults={"status": "requested"}
            )
            if selftape_request.status == "responded":
                return Response(
                    {"status_code": 400, "status_message": "You have already responded to this request."},
                    status=400,
                )

            files = get_files(request, "files")
            raw_urls = get_multi_values(request, "tape_urls", "tape_urls[]")
            normalized_urls = normalize_url_list(raw_urls)

            if not files and not normalized_urls:
                return Response(
                    {"status_code": 400, "status_message": "No files or video URLs provided."}, status=400
                )

            allowed_exts = {".mp4", ".mov", ".avi", ".wmv", ".m4v"}
            uploaded_urls = []
            for f in files:
                saved_path, bad_name = save_uploaded_file(f, "selftapes", allowed_exts, "video/")
                if bad_name is not None:
                    return Response(
                        {"status_code": 400, "status_message": f"Invalid video file: {bad_name}"},
                        status=400,
                    )
                url = request.build_absolute_uri(settings.MEDIA_URL + saved_path.replace("\\", "/"))
                uploaded_urls.append(url)

            all_urls = uploaded_urls + normalized_urls

            existing_link_urls = set(
                SelfTapeLink.objects.filter(request=selftape_request).values_list("tape_url", flat=True)
            )
            existing_tapes = snapshot.get("tapes", [])
            new_urls = []
            for url in all_urls:
                if url not in existing_link_urls:
                    SelfTapeLink.objects.create(request=selftape_request, tape_url=url)
                    existing_link_urls.add(url)
                    new_urls.append(url)
                if url not in existing_tapes:
                    existing_tapes.append(url)

            selftape_request.status = "responded"
            selftape_request.save(update_fields=["status"])

            snapshot["status"] = "responded"
            snapshot["tapes"] = existing_tapes
            ai_result.requested_selftapes = json.dumps(snapshots)
            ai_result.save(update_fields=["requested_selftapes"])

            _bump_draft_timestamp(job.session_id)

            create_notification(
                receiver_id=job.job_created_by_id,
                sender_id=user_id,
                event=f"{talent.name} has uploaded a self-tape for the project '{job.title}'.",
            )

        return Response(
            {
                "status_code": 200,
                "status_message": "Self-tapes uploaded and status updated to responded.",
                "uploaded_urls": new_urls,
            },
            status=200,
        )


class PolaUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user_id = request.user.user_id
        talent_id = request.data.get("talent_id")
        job_id = request.data.get("job_id")
        session_id = request.data.get("session_id")

        if not talent_id:
            return Response({"status_code": 400, "status_message": "talent_id is required"}, status=400)
        if not job_id and not session_id:
            return Response(
                {"status_code": 400, "status_message": "job_id or session_id is required"}, status=400
            )

        talent = Talent.objects.filter(talent_id=talent_id).first()
        job = resolve_job_for_upload(user_id, job_id=job_id, session_id=session_id)
        if not talent or not job:
            return Response({"status_code": 404, "status_message": "Talent or job not found"}, status=404)

        allowed_ids = {talent.talent_id, talent.agent_id, job.job_created_by_id}
        if user_id not in allowed_ids:
            return Response(
                {"status_code": 403, "status_message": "Unauthorized to upload tapes for this talent."},
                status=403,
            )

        ai_result = get_or_create_ai_result(int(job.job_id))
        snapshots = parse_json_field(ai_result.requested_polas, [])
        snapshot = next(
            (t for t in snapshots if str(t.get("talent_id")) == str(talent.talent_id)), None
        )
        if not snapshot:
            return Response(
                {"status_code": 404, "status_message": "Polas request not found in job snapshot."},
                status=404,
            )

        with transaction.atomic():
            pola_request, _ = PolaRequest.objects.get_or_create(
                job_id=int(job.job_id), talent_id=talent.talent_id, defaults={"status": "requested"}
            )
            if pola_request.status == "responded":
                return Response(
                    {"status_code": 400, "status_message": "You have already responded to this request."},
                    status=400,
                )

            files = get_files(request, "files")
            raw_urls = get_multi_values(request, "image_urls", "image_urls[]")
            normalized_urls = normalize_url_list(raw_urls)

            if not files and not normalized_urls:
                return Response(
                    {"status_code": 400, "status_message": "No files or image URLs provided."}, status=400
                )

            allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
            uploaded_urls = []
            for f in files:
                saved_path, bad_name = save_uploaded_file(f, "polas", allowed_exts, "image/")
                if bad_name is not None:
                    return Response(
                        {"status_code": 400, "status_message": f"Invalid image file: {bad_name}"},
                        status=400,
                    )
                url = request.build_absolute_uri(settings.MEDIA_URL + saved_path.replace("\\", "/"))
                uploaded_urls.append(url)

            all_urls = uploaded_urls + normalized_urls

            existing_link_urls = set(
                PolaLink.objects.filter(request=pola_request).values_list("pola_url", flat=True)
            )
            existing_tapes = snapshot.get("tapes", [])
            new_urls = []
            for url in all_urls:
                if url not in existing_link_urls:
                    PolaLink.objects.create(request=pola_request, pola_url=url)
                    existing_link_urls.add(url)
                    new_urls.append(url)
                if url not in existing_tapes:
                    existing_tapes.append(url)

            pola_request.status = "responded"
            pola_request.save(update_fields=["status"])

            snapshot["status"] = "responded"
            snapshot["tapes"] = existing_tapes
            ai_result.requested_polas = json.dumps(snapshots)
            ai_result.save(update_fields=["requested_polas"])

            _bump_draft_timestamp(job.session_id)

            create_notification(
                receiver_id=job.job_created_by_id,
                sender_id=user_id,
                event=f"{talent.name} has uploaded polas for the project '{job.title}'.",
            )

        return Response(
            {
                "status_code": 200,
                "status_message": "Polas uploaded and status updated to responded.",
                "uploaded_urls": new_urls,
            },
            status=200,
        )


def get_files(request, key):
    files = request.FILES.getlist(key)
    if not files:
        files = request.FILES.getlist(f"{key}[]")
    return files
