import os

from drf_spectacular.utils import OpenApiTypes, extend_schema_field, inline_serializer
from rest_framework import serializers
from talent.models import Talent
from .models import ClientChatMessage, ClientChatThread, GuestClient, TalentComment, TalentFavorite


class GuestClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestClient
        fields = ["id", "name", "email", "created_at", "last_seen_at"]


class TalentBriefSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Talent
        fields = ["talent_id", "name", "role", "character", "location", "image"]

    @extend_schema_field(OpenApiTypes.URI)
    def get_image(self, obj):
        image = obj.images.filter(is_primary=True).first() or obj.images.first()
        if not image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.image.url) if request else image.image.url


class TalentFavoriteSerializer(serializers.ModelSerializer):
    talent = TalentBriefSerializer(read_only=True)

    class Meta:
        model = TalentFavorite
        fields = ["id", "talent", "created_at"]


class TalentCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TalentComment
        fields = ["id", "talent_id", "comment", "created_at", "updated_at"]
        read_only_fields = ["id", "talent_id", "created_at", "updated_at"]


class ClientChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = ClientChatMessage
        fields = [
            "id", "thread_id", "sender_type",
            "sender_name", "message_type", "text",
            "attachment", "attachment_url", "file_name", "is_seen_by_agent",
            "is_seen_by_client", "seen_at", "created_at",
        ]
        read_only_fields = [
            "id", "thread_id", "sender_type", "is_seen_by_agent", "is_seen_by_client", "seen_at", "created_at",
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_sender_name(self, obj):
        if obj.sender_type == "agent":
            agent = obj.sender_agent
            return getattr(agent, "full_name", None) or getattr(agent, "email", None) if agent else "Agent"
        thread = obj.thread
        return thread.guest_client.name if thread and thread.guest_client_id else "Client"

    @extend_schema_field(OpenApiTypes.URI)
    def get_attachment_url(self, obj):
        if not obj.attachment:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.attachment.url) if request else obj.attachment.url

    @extend_schema_field(OpenApiTypes.STR)
    def get_file_name(self, obj):
        # The storage backend can rename on collision (e.g. contract_x7f3a2.pdf), so
        # the frontend shouldn't derive a display name by parsing attachment_url.
        if not obj.attachment:
            return None
        return os.path.basename(obj.attachment.name)


# ---- Agent-facing serializers ----

class AgentGuestClientListSerializer(serializers.ModelSerializer):
    favorite_count = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    unread_count = serializers.IntegerField(read_only=True)
    thread_id = serializers.SerializerMethodField()

    class Meta:
        model = GuestClient
        fields = [
            "id", "name", "email", "created_at", "last_seen_at",
            "favorite_count", "comment_count", "unread_count", "thread_id",
        ]

    @extend_schema_field(OpenApiTypes.INT)
    def get_thread_id(self, obj):
        thread = getattr(obj, "chat_thread", None)
        return thread.id if thread else None


class AgentGuestTalentActivitySerializer(serializers.Serializer):
    talent = TalentBriefSerializer()
    is_favorited = serializers.BooleanField()
    comments = TalentCommentSerializer(many=True)


class AgentChatInboxSerializer(serializers.ModelSerializer):
    job_title = serializers.SerializerMethodField()
    guest_client = GuestClientSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ClientChatThread
        fields = [
            "id", "job_id", "job_title", "guest_client",
            "last_message", "unread_count", "updated_at", "created_at",
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_job_title(self, obj):
        job_titles_by_id = self.context.get("job_titles_by_id") or {}
        return job_titles_by_id.get(obj.job_id)

    @extend_schema_field(
        inline_serializer(
            name="ChatThreadLastMessage",
            fields={
                "id": serializers.IntegerField(),
                "text": serializers.CharField(allow_null=True),
                "sender_type": serializers.ChoiceField(choices=ClientChatMessage.SENDER_TYPE_CHOICES),
                "created_at": serializers.DateTimeField(),
            },
        )
    )
    def get_last_message(self, obj):
        last_msg = getattr(obj, "last_message_obj", None)
        if not last_msg:
            return None
        return {
            "id": last_msg.id,
            "text": last_msg.text,
            "sender_type": last_msg.sender_type,
            "created_at": last_msg.created_at,
        }
