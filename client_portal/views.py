import os

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.send_otp import generate_and_send_otp
from core.pagination import CustomPagination
from jobs.models import Job
from talent.models import Talent
from utils.permissions import IsAdminRole, IsClient
from .models import ClientChatMessage, ClientChatThread, GuestClient, TalentComment, TalentFavorite
from .schema import ERROR_RESPONSE, GUEST_TOKEN_PARAMETER, envelope, paginated_envelope
from .serializers import (
    AgentChatInboxSerializer,
    AgentGuestClientListSerializer,
    AgentGuestTalentActivitySerializer,
    ClientChatMessageSerializer,
    GuestClientSerializer,
    TalentCommentSerializer,
    TalentFavoriteSerializer,
)
from .utils import get_job_owner, job_belongs_to_agent, normalize_email, resolve_guest

MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10MB, matches the WS text-length guard's spirit


def success_response(message, data=None, status_code=200):
    return Response(
        {"status": True, "status_code": status_code, "message": message, "data": data},
        status=status_code,
    )


def error_response(message, status_code=400):
    return Response(
        {"status": False, "status_code": status_code, "message": message},
        status=status_code,
    )


def broadcast_chat_message(thread_id, message, request):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        f"client_chat_{thread_id}",
        {
            "type": "chat.message",
            "payload": {
                "message_id": message.id,
                "thread_id": message.thread_id,
                "sender_type": message.sender_type,
                "sender_agent_id": message.sender_agent_id,
                "message_type": message.message_type,
                "text": message.text,
                "attachment_url": request.build_absolute_uri(message.attachment.url) if message.attachment else None,
                "file_name": os.path.basename(message.attachment.name) if message.attachment else None,
                "is_seen_by_agent": message.is_seen_by_agent,
                "is_seen_by_client": message.is_seen_by_client,
                "seen_at": message.seen_at,
                "created_at": message.created_at.isoformat(),
            },
        },
    )


# ---------------------------------------------------------------------------
# Guest-facing views
# ---------------------------------------------------------------------------

GUEST_IDENTITY_DATA = inline_serializer(
    name="GuestIdentityData",
    fields={
        "guest_token": serializers.CharField(help_text="Store this and send it back as X-Guest-Token on every subsequent request."),
        "guest_client": GuestClientSerializer(),
        "thread_id": serializers.IntegerField(allow_null=True),
    },
)


@extend_schema(tags=["Client Portal - Guest"])
class GuestIdentifyAPIView(APIView):
    """First-touch endpoint: client submits name + email; triggers an OTP email.

    No guest_token is issued here. job_id in the URL is a small guessable integer,
    not a secret, so email is the only thing standing between a stranger and someone
    else's existing chat/favorites/comments — this proves they actually control that
    inbox before any token is ever handed out. See GuestVerifyOTPAPIView for step two.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="client_portal_guest_identify",
        summary="Start identifying on a shortlist link (sends an OTP email)",
        description=(
            "Submit a name + email to unlock favorites, comments, and chat on this job's "
            "shortlist link — no password, no account. Sends a 6-digit code to that email; "
            "call verify/ with it to actually receive a guest_token. Safe to call again to "
            "resend a fresh code — it doesn't create a duplicate guest or rotate an "
            "already-issued token, it only regenerates the pending OTP."
        ),
        request=inline_serializer(
            name="GuestIdentifyRequest",
            fields={"name": serializers.CharField(), "email": serializers.EmailField()},
        ),
        responses={
            200: envelope(
                "GuestIdentifyResponse",
                data_field=inline_serializer(name="GuestIdentifyData", fields={"email": serializers.EmailField(), "otp_required": serializers.BooleanField(default=True)}),
                message_example="We've sent a verification code to your email.",
            ),
            400: ERROR_RESPONSE,
            502: OpenApiResponse(response=ERROR_RESPONSE, description="The OTP email failed to send (upstream mail provider issue) — safe to retry."),
        },
    )
    def post(self, request, job_id):
        get_object_or_404(Job, job_id=job_id)

        name = (request.data.get("name") or "").strip()
        email = normalize_email(request.data.get("email"))

        if not name or not email:
            return error_response("name and email are required.", 400)

        # Only set `name` on first creation. An unverified caller doesn't get to
        # rewrite an existing guest's stored name just by knowing their email — that
        # mutation is deferred to verify/, after ownership of the inbox is proven.
        guest, _ = GuestClient.objects.get_or_create(
            job_id=job_id,
            email=email,
            defaults={
                "name": name,
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
        )

        if not generate_and_send_otp(guest):
            # generate_and_send_otp already persisted otp/otp_expired_at before the
            # send attempt failed — clear them so no undelivered, unknown-to-the-
            # caller code is left sitting on the row.
            guest.otp = None
            guest.otp_expired_at = None
            guest.save(update_fields=["otp", "otp_expired_at"])
            return error_response("Couldn't send the verification email. Please try again.", 502)

        return success_response(
            "We've sent a verification code to your email.",
            data={"email": guest.email, "otp_required": True},
        )


@extend_schema(tags=["Client Portal - Guest"])
class GuestVerifyOTPAPIView(APIView):
    """Second step: exchange a valid OTP for the guest's actual token."""
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="client_portal_guest_verify_otp",
        summary="Verify the OTP and receive the guest token",
        description="On success, returns the same guest_token every time this guest completes verification — it doesn't rotate, so other already-authenticated tabs/devices aren't invalidated.",
        request=inline_serializer(
            name="GuestVerifyOTPRequest",
            fields={
                "email": serializers.EmailField(),
                "otp": serializers.CharField(),
                "name": serializers.CharField(required=False, help_text="Optional — updates the stored display name, applied only now that email ownership is proven."),
            },
        ),
        responses={
            200: envelope("GuestVerifyOTPResponse", data_field=GUEST_IDENTITY_DATA, message_example="Verified."),
            400: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
        },
    )
    def post(self, request, job_id):
        job = get_object_or_404(Job, job_id=job_id)

        email = normalize_email(request.data.get("email"))
        otp = (request.data.get("otp") or "").strip()

        if not email or not otp:
            return error_response("email and otp are required.", 400)

        guest = GuestClient.objects.filter(job_id=job_id, email=email).first()
        if not guest:
            return error_response("No pending verification for this email — call identify first.", 404)

        if not guest.otp or not guest.otp_expired_at:
            return error_response("No OTP found. Please request a new one.", 400)

        if timezone.now() > guest.otp_expired_at:
            return error_response("OTP expired. Please request a new one.", 400)

        if guest.otp != otp:
            return error_response("Invalid OTP.", 400)

        name = (request.data.get("name") or "").strip()

        guest.otp = None
        guest.otp_expired_at = None
        guest.is_verified = True
        guest.last_seen_at = timezone.now()
        update_fields = ["otp", "otp_expired_at", "is_verified", "last_seen_at"]
        if name:
            guest.name = name
            update_fields.append("name")
        guest.save(update_fields=update_fields)

        thread, _ = ClientChatThread.objects.get_or_create(
            guest_client=guest,
            defaults={"agent": get_job_owner(job), "job_id": job_id},
        )

        return success_response(
            "Verified.",
            data={
                "guest_token": str(guest.token),
                "guest_client": GuestClientSerializer(guest).data,
                "thread_id": thread.id,
            },
        )


@extend_schema(tags=["Client Portal - Guest"])
class GuestSessionAPIView(APIView):
    """Lets a returning client silently resolve their identity from a stored token."""
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="client_portal_guest_session",
        summary="Resolve a guest's identity from a stored token",
        description=(
            "Call this before showing the identify form. A 401 means there's no valid "
            "session for this job — show the name/email form. A 200 means the guest is "
            "already known — skip straight to the shortlist."
        ),
        parameters=[GUEST_TOKEN_PARAMETER],
        responses={
            200: envelope("GuestSessionResponse", data_field=GUEST_IDENTITY_DATA, message_example="Session resolved."),
            401: ERROR_RESPONSE,
        },
    )
    def get(self, request, job_id):
        guest = resolve_guest(request, job_id)
        if not guest:
            return error_response("No active session for this link.", 401)

        guest.last_seen_at = timezone.now()
        guest.save(update_fields=["last_seen_at"])

        thread = ClientChatThread.objects.filter(guest_client=guest).first()

        return success_response(
            "Session resolved.",
            data={
                "guest_token": str(guest.token),
                "guest_client": GuestClientSerializer(guest).data,
                "thread_id": thread.id if thread else None,
            },
        )


@extend_schema(tags=["Client Portal - Guest"])
class GuestFavoriteListCreateAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="client_portal_guest_favorites_list",
        summary="List the guest's favorited talents on this job",
        parameters=[GUEST_TOKEN_PARAMETER],
        responses={
            200: envelope("GuestFavoriteListResponse", data_field=TalentFavoriteSerializer(many=True), message_example="Favorites fetched successfully."),
            401: ERROR_RESPONSE,
        },
    )
    def get(self, request, job_id):
        guest = resolve_guest(request, job_id)
        if not guest:
            return error_response("Invalid or missing guest session.", 401)

        favorites = TalentFavorite.objects.filter(guest_client=guest).select_related("talent").prefetch_related("talent__images")
        serializer = TalentFavoriteSerializer(favorites, many=True, context={"request": request})
        return success_response("Favorites fetched successfully.", serializer.data)

    @extend_schema(
        operation_id="client_portal_guest_favorites_create",
        summary="Favorite a talent",
        description="Idempotent — favoriting an already-favorited talent returns 200 with the existing row instead of erroring.",
        parameters=[GUEST_TOKEN_PARAMETER],
        request=inline_serializer(name="GuestFavoriteCreateRequest", fields={"talent_id": serializers.IntegerField()}),
        responses={
            200: envelope("GuestFavoriteCreateResponse", data_field=TalentFavoriteSerializer(), message_example="Talent already favorited."),
            201: envelope("GuestFavoriteCreateResponse", data_field=TalentFavoriteSerializer(), message_example="Talent favorited successfully."),
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
        },
    )
    def post(self, request, job_id):
        guest = resolve_guest(request, job_id)
        if not guest:
            return error_response("Invalid or missing guest session.", 401)

        talent_id = request.data.get("talent_id")
        if not talent_id:
            return error_response("talent_id is required.", 400)

        talent = get_object_or_404(Talent, talent_id=talent_id)

        favorite, created = TalentFavorite.objects.get_or_create(
            guest_client=guest,
            talent=talent,
            defaults={"job_id": job_id},
        )

        serializer = TalentFavoriteSerializer(favorite, context={"request": request})
        return success_response(
            "Talent favorited successfully." if created else "Talent already favorited.",
            serializer.data,
            status_code=201 if created else 200,
        )


@extend_schema(tags=["Client Portal - Guest"])
class GuestFavoriteDeleteAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="client_portal_guest_favorites_delete",
        summary="Remove a favorite",
        parameters=[GUEST_TOKEN_PARAMETER],
        responses={
            200: envelope("GuestFavoriteDeleteResponse", message_example="Favorite removed successfully."),
            401: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
        },
    )
    def delete(self, request, job_id, talent_id):
        guest = resolve_guest(request, job_id)
        if not guest:
            return error_response("Invalid or missing guest session.", 401)

        deleted, _ = TalentFavorite.objects.filter(guest_client=guest, talent_id=talent_id).delete()
        if not deleted:
            return error_response("Favorite not found.", 404)

        return success_response("Favorite removed successfully.")


@extend_schema(tags=["Client Portal - Guest"])
class GuestTalentCommentAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="client_portal_guest_comments_list",
        summary="List the guest's own comments on one talent",
        description="Only the calling guest's own comments — other guests' comments on the same talent are never visible to each other.",
        parameters=[GUEST_TOKEN_PARAMETER],
        responses={
            200: envelope("GuestCommentListResponse", data_field=TalentCommentSerializer(many=True), message_example="Comments fetched successfully."),
            401: ERROR_RESPONSE,
        },
    )
    def get(self, request, job_id, talent_id):
        guest = resolve_guest(request, job_id)
        if not guest:
            return error_response("Invalid or missing guest session.", 401)

        comments = TalentComment.objects.filter(guest_client=guest, talent_id=talent_id)
        serializer = TalentCommentSerializer(comments, many=True)
        return success_response("Comments fetched successfully.", serializer.data)

    @extend_schema(
        operation_id="client_portal_guest_comments_create",
        summary="Add a comment on a talent",
        description="Comments accumulate — this adds a new comment, it doesn't replace a prior one.",
        parameters=[GUEST_TOKEN_PARAMETER],
        request=inline_serializer(name="GuestCommentCreateRequest", fields={"comment": serializers.CharField()}),
        responses={
            201: envelope("GuestCommentCreateResponse", data_field=TalentCommentSerializer(), message_example="Comment added successfully."),
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
        },
    )
    def post(self, request, job_id, talent_id):
        guest = resolve_guest(request, job_id)
        if not guest:
            return error_response("Invalid or missing guest session.", 401)

        comment_text = (request.data.get("comment") or "").strip()
        if not comment_text:
            return error_response("comment is required.", 400)

        talent = get_object_or_404(Talent, talent_id=talent_id)

        comment = TalentComment.objects.create(
            guest_client=guest,
            talent=talent,
            job_id=job_id,
            comment=comment_text,
        )

        serializer = TalentCommentSerializer(comment)
        return success_response("Comment added successfully.", serializer.data, status_code=201)


@extend_schema(tags=["Client Portal - Guest"])
class GuestChatMessagesAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="client_portal_guest_chat_messages",
        summary="Fetch chat history with the agent (REST fallback)",
        description="History fallback for when the WebSocket isn't connected. Marks the agent's messages as seen by this guest.",
        parameters=[GUEST_TOKEN_PARAMETER],
        responses={
            200: paginated_envelope(
                "GuestChatMessagesResponse",
                data_field=inline_serializer(
                    name="GuestChatMessagesData",
                    fields={
                        "thread_id": serializers.IntegerField(allow_null=True),
                        "messages": ClientChatMessageSerializer(many=True),
                    },
                ),
            ),
            401: ERROR_RESPONSE,
        },
    )
    def get(self, request, job_id):
        guest = resolve_guest(request, job_id)
        if not guest:
            return error_response("Invalid or missing guest session.", 401)

        thread = ClientChatThread.objects.filter(guest_client=guest).first()
        if not thread:
            return success_response("No conversation yet.", {"thread_id": None, "messages": []})

        ClientChatMessage.objects.filter(
            thread=thread, sender_type="agent", is_seen_by_client=False
        ).update(is_seen_by_client=True, seen_at=timezone.now())

        messages = thread.messages.all()
        paginator = CustomPagination()
        paginated = paginator.paginate_queryset(messages, request, view=self)
        serializer = ClientChatMessageSerializer(paginated, many=True, context={"request": request})
        return paginator.get_paginated_response({"thread_id": thread.id, "messages": serializer.data})


@extend_schema(tags=["Client Portal - Guest"])
class GuestChatUploadAPIView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        operation_id="client_portal_guest_chat_upload",
        summary="Send an image/file attachment in the chat",
        description="Requires an existing conversation (i.e. the guest must have already been through identify/verify at least once, which creates the thread).",
        parameters=[GUEST_TOKEN_PARAMETER],
        request={"multipart/form-data": inline_serializer(
            name="GuestChatUploadRequest",
            fields={
                "attachment": serializers.FileField(),
                "message_type": serializers.ChoiceField(choices=["image", "file"], required=False, help_text="Defaults to 'file'."),
                "text": serializers.CharField(required=False, help_text="Optional caption."),
            },
        )},
        responses={
            201: envelope("GuestChatUploadResponse", data_field=ClientChatMessageSerializer(), message_example="Attachment sent successfully."),
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
        },
    )
    def post(self, request, job_id):
        guest = resolve_guest(request, job_id)
        if not guest:
            return error_response("Invalid or missing guest session.", 401)

        thread = ClientChatThread.objects.filter(guest_client=guest).first()
        if not thread:
            return error_response("No conversation yet — identify/verify first.", 400)

        attachment = request.FILES.get("attachment")
        if not attachment:
            return error_response("attachment is required.", 400)
        if attachment.size > MAX_ATTACHMENT_SIZE_BYTES:
            return error_response(f"attachment must be {MAX_ATTACHMENT_SIZE_BYTES // (1024 * 1024)}MB or smaller.", 400)

        message_type = request.data.get("message_type", "file")
        if message_type not in ["image", "file"]:
            return error_response("message_type must be either 'image' or 'file'.", 400)

        message = ClientChatMessage.objects.create(
            thread=thread,
            sender_type="client",
            message_type=message_type,
            text=request.data.get("text", ""),
            attachment=attachment,
            is_seen_by_client=True,
        )
        ClientChatThread.objects.filter(id=thread.id).update(updated_at=timezone.now())
        broadcast_chat_message(thread.id, message, request)

        serializer = ClientChatMessageSerializer(message, context={"request": request})
        return success_response("Attachment sent successfully.", serializer.data, status_code=201)


# ---------------------------------------------------------------------------
# Agent-facing views
# ---------------------------------------------------------------------------

class AgentJobOwnershipMixin:
    def check_job_ownership(self, request, job_id):
        job = get_object_or_404(Job, job_id=job_id)
        return job_belongs_to_agent(job, request.user)


AGENT_FORBIDDEN_RESPONSE = ERROR_RESPONSE


@extend_schema(tags=["Client Portal - Agent"])
class AgentJobGuestClientsAPIView(AgentJobOwnershipMixin, APIView):
    permission_classes = [IsAuthenticated & (IsClient | IsAdminRole)]

    @extend_schema(
        operation_id="client_portal_agent_job_clients_list",
        summary="List guest clients who opened this job's shortlist link",
        description="Only the job's owning agent (or an Admin) can see this. Each guest is annotated with favorite/comment/unread counts.",
        responses={
            200: paginated_envelope("AgentJobClientsResponse", data_field=AgentGuestClientListSerializer(many=True)),
            403: AGENT_FORBIDDEN_RESPONSE,
        },
    )
    def get(self, request, job_id):
        if not self.check_job_ownership(request, job_id):
            return error_response("You do not have access to this job's clients.", 403)

        guests = GuestClient.objects.filter(job_id=job_id).annotate(
            favorite_count=Count("favorites", distinct=True),
            comment_count=Count("comments", distinct=True),
            unread_count=Count(
                "chat_thread__messages",
                filter=Q(chat_thread__messages__sender_type="client", chat_thread__messages__is_seen_by_agent=False),
                distinct=True,
            ),
        ).prefetch_related("chat_thread")

        paginator = CustomPagination()
        paginated = paginator.paginate_queryset(guests, request, view=self)
        serializer = AgentGuestClientListSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(tags=["Client Portal - Agent"])
class AgentGuestClientDetailAPIView(AgentJobOwnershipMixin, APIView):
    permission_classes = [IsAuthenticated & (IsClient | IsAdminRole)]

    @extend_schema(
        operation_id="client_portal_agent_guest_client_detail",
        summary="Get one guest's full activity on this job",
        description="Every talent this guest favorited and/or commented on, with their comment thread per talent.",
        responses={
            200: envelope(
                "AgentGuestClientDetailResponse",
                data_field=inline_serializer(
                    name="AgentGuestClientDetailData",
                    fields={
                        "guest_client": GuestClientSerializer(),
                        "activity": AgentGuestTalentActivitySerializer(many=True),
                    },
                ),
                message_example="Client activity fetched successfully.",
            ),
            403: AGENT_FORBIDDEN_RESPONSE,
            404: ERROR_RESPONSE,
        },
    )
    def get(self, request, job_id, guest_client_id):
        if not self.check_job_ownership(request, job_id):
            return error_response("You do not have access to this job's clients.", 403)

        guest = get_object_or_404(GuestClient, id=guest_client_id, job_id=job_id)

        favorited_talent_ids = set(
            TalentFavorite.objects.filter(guest_client=guest).values_list("talent_id", flat=True)
        )
        commented_talent_ids = list(
            TalentComment.objects.filter(guest_client=guest).values_list("talent_id", flat=True).distinct()
        )
        talent_ids = favorited_talent_ids.union(commented_talent_ids)

        talents = Talent.objects.filter(talent_id__in=talent_ids).prefetch_related("images")
        comments_by_talent = {}
        for comment in TalentComment.objects.filter(guest_client=guest).order_by("-created_at"):
            comments_by_talent.setdefault(comment.talent_id, []).append(comment)

        activity = []
        for talent in talents:
            activity.append({
                "talent": talent,
                "is_favorited": talent.talent_id in favorited_talent_ids,
                "comments": comments_by_talent.get(talent.talent_id, []),
            })

        serializer = AgentGuestTalentActivitySerializer(activity, many=True, context={"request": request})

        return success_response(
            "Client activity fetched successfully.",
            {
                "guest_client": GuestClientSerializer(guest).data,
                "activity": serializer.data,
            },
        )


@extend_schema(tags=["Client Portal - Agent"])
class AgentGuestChatMessagesAPIView(AgentJobOwnershipMixin, APIView):
    permission_classes = [IsAuthenticated & (IsClient | IsAdminRole)]

    @extend_schema(
        operation_id="client_portal_agent_guest_chat_messages",
        summary="Fetch chat history with one guest (REST fallback)",
        description="History fallback for when the WebSocket isn't connected. Marks this guest's messages as seen by the agent.",
        responses={
            200: paginated_envelope(
                "AgentGuestChatMessagesResponse",
                data_field=inline_serializer(
                    name="AgentGuestChatMessagesData",
                    fields={
                        "thread_id": serializers.IntegerField(allow_null=True),
                        "messages": ClientChatMessageSerializer(many=True),
                    },
                ),
            ),
            403: AGENT_FORBIDDEN_RESPONSE,
        },
    )
    def get(self, request, job_id, guest_client_id):
        if not self.check_job_ownership(request, job_id):
            return error_response("You do not have access to this job's clients.", 403)

        guest = get_object_or_404(GuestClient, id=guest_client_id, job_id=job_id)
        thread = ClientChatThread.objects.filter(guest_client=guest).first()
        if not thread:
            return success_response("No conversation yet.", {"thread_id": None, "messages": []})

        ClientChatMessage.objects.filter(
            thread=thread, sender_type="client", is_seen_by_agent=False
        ).update(is_seen_by_agent=True, seen_at=timezone.now())

        messages = thread.messages.all()
        paginator = CustomPagination()
        paginated = paginator.paginate_queryset(messages, request, view=self)
        serializer = ClientChatMessageSerializer(paginated, many=True, context={"request": request})
        return paginator.get_paginated_response({"thread_id": thread.id, "messages": serializer.data})


@extend_schema(tags=["Client Portal - Agent"])
class AgentChatUploadAPIView(AgentJobOwnershipMixin, APIView):
    permission_classes = [IsAuthenticated & (IsClient | IsAdminRole)]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        operation_id="client_portal_agent_chat_upload",
        summary="Send an image/file attachment to one guest",
        request={"multipart/form-data": inline_serializer(
            name="AgentChatUploadRequest",
            fields={
                "attachment": serializers.FileField(),
                "message_type": serializers.ChoiceField(choices=["image", "file"], required=False, help_text="Defaults to 'file'."),
                "text": serializers.CharField(required=False, help_text="Optional caption."),
            },
        )},
        responses={
            201: envelope("AgentChatUploadResponse", data_field=ClientChatMessageSerializer(), message_example="Attachment sent successfully."),
            400: ERROR_RESPONSE,
            403: AGENT_FORBIDDEN_RESPONSE,
        },
    )
    def post(self, request, job_id, guest_client_id):
        if not self.check_job_ownership(request, job_id):
            return error_response("You do not have access to this job's clients.", 403)

        guest = get_object_or_404(GuestClient, id=guest_client_id, job_id=job_id)
        thread = ClientChatThread.objects.filter(guest_client=guest).first()
        if not thread:
            return error_response("No conversation yet.", 400)

        attachment = request.FILES.get("attachment")
        if not attachment:
            return error_response("attachment is required.", 400)
        if attachment.size > MAX_ATTACHMENT_SIZE_BYTES:
            return error_response(f"attachment must be {MAX_ATTACHMENT_SIZE_BYTES // (1024 * 1024)}MB or smaller.", 400)

        message_type = request.data.get("message_type", "file")
        if message_type not in ["image", "file"]:
            return error_response("message_type must be either 'image' or 'file'.", 400)

        message = ClientChatMessage.objects.create(
            thread=thread,
            sender_type="agent",
            sender_agent=request.user,
            message_type=message_type,
            text=request.data.get("text", ""),
            attachment=attachment,
            is_seen_by_agent=True,
        )
        ClientChatThread.objects.filter(id=thread.id).update(updated_at=timezone.now())
        broadcast_chat_message(thread.id, message, request)

        serializer = ClientChatMessageSerializer(message, context={"request": request})
        return success_response("Attachment sent successfully.", serializer.data, status_code=201)


@extend_schema(tags=["Client Portal - Agent"])
class AgentChatInboxAPIView(APIView):
    permission_classes = [IsAuthenticated & (IsClient | IsAdminRole)]

    @extend_schema(
        operation_id="client_portal_agent_chat_inbox",
        summary="Cross-job inbox of all this agent's guest chat threads",
        description="Every ClientChatThread where this user is the agent, across all of their jobs, newest activity first.",
        responses={
            200: paginated_envelope("AgentChatInboxResponse", data_field=AgentChatInboxSerializer(many=True)),
        },
    )
    def get(self, request):
        threads = ClientChatThread.objects.filter(agent=request.user).select_related(
            "guest_client"
        ).annotate(
            last_message_id=Max("messages__id"),
            unread_count=Count(
                "messages",
                filter=Q(messages__sender_type="client", messages__is_seen_by_agent=False),
                distinct=True,
            ),
        ).order_by("-updated_at")

        paginator = CustomPagination()
        paginated = paginator.paginate_queryset(threads, request, view=self)

        last_message_ids = [t.last_message_id for t in paginated if t.last_message_id]
        last_messages_by_id = {
            m.id: m for m in ClientChatMessage.objects.filter(id__in=last_message_ids)
        }
        job_titles_by_id = dict(
            Job.objects.filter(job_id__in={t.job_id for t in paginated}).values_list("job_id", "title")
        )
        for thread in paginated:
            thread.last_message_obj = last_messages_by_id.get(thread.last_message_id)

        serializer = AgentChatInboxSerializer(
            paginated, many=True, context={"job_titles_by_id": job_titles_by_id}
        )
        return paginator.get_paginated_response(serializer.data)
