from rest_framework import serializers
from .models import Conversation, Message


class ConversationListSerializer(serializers.ModelSerializer):
    other_user_id = serializers.SerializerMethodField()
    other_user_name = serializers.SerializerMethodField()
    other_user_email = serializers.SerializerMethodField()
    other_user_profile_pic = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "conversation_id",
            "other_user_id",
            "other_user_name",
            "other_user_email",
            "other_user_profile_pic",
            "last_message",
            "unread_count",
            "updated_at",
            "created_at",
        ]

    def _get_other_user(self, obj):
        request = self.context.get("request")
        if obj.user1_id == request.user.pk:
            return obj.user2
        return obj.user1

    def get_other_user_id(self, obj):
        other_user = self._get_other_user(obj)
        return other_user.pk

    def get_other_user_name(self, obj):
        other_user = self._get_other_user(obj)
        return getattr(other_user, "full_name", None) or getattr(other_user, "username", None) or str(other_user)

    def get_other_user_email(self, obj):
        other_user = self._get_other_user(obj)
        return getattr(other_user, "email", None)

    def get_other_user_profile_pic(self, obj):
        other_user = self._get_other_user(obj)
        profile_pic = getattr(other_user, "profile_pic", None)
        try:
            if profile_pic:
                url = profile_pic.url
                request = self.context.get("request")
                return request.build_absolute_uri(url) if request else url
            return None
        except Exception:
            return None

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by("-created_at").first()
        if not last_msg:
            return None
        return {
            "message_id": last_msg.message_id,
            "text": last_msg.text,
            "message_type": last_msg.message_type,
            "attachment": self.context.get("request").build_absolute_uri(last_msg.attachment.url) if last_msg.attachment and self.context.get("request") else (last_msg.attachment.url if last_msg.attachment else None),
            "sender_id": last_msg.sender_id,
            "created_at": last_msg.created_at,
        }

    def get_unread_count(self, obj):
        request = self.context.get("request")
        return obj.messages.filter(receiver=request.user, is_seen=False).count()


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "message_id",
            "conversation",
            "sender",
            "sender_name",
            "receiver",
            "receiver_name",
            "message_type",
            "text",
            "attachment",
            "attachment_url",
            "is_seen",
            "seen_at",
            "created_at",
        ]
        read_only_fields = [
            "message_id",
            "conversation",
            "sender",
            "receiver",
            "is_seen",
            "seen_at",
            "created_at",
        ]

    def get_sender_name(self, obj):
        return getattr(obj.sender, "full_name", None) or getattr(obj.sender, "username", None) or str(obj.sender)

    def get_receiver_name(self, obj):
        return getattr(obj.receiver, "full_name", None) or getattr(obj.receiver, "username", None) or str(obj.receiver)

    def get_attachment_url(self, obj):
        try:
            if obj.attachment:
                url = obj.attachment.url
                request = self.context.get("request")
                return request.build_absolute_uri(url) if request else url
            return None
        except Exception:
            return None