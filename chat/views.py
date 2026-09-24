from django.db import models, transaction
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, Count
from .models import Conversation, Message
from .serializers import ConversationListSerializer, MessageSerializer
from django.utils import timezone
from core.pagination import CustomPagination

User = get_user_model()


def success_response(message, data=None, status_code=200):
    return Response(
        {
            "status": True,
            "status_code": status_code,
            "message": message,
            "data": data
        },
        status=status_code
    )


def error_response(message, status_code=400):
    return Response(
        {
            "status": False,
            "status_code": status_code,
            "message": message
        },
        status=status_code
    )


class GetOrCreateConversationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        other_user_id = request.data.get("user_id")

        if not other_user_id:
            return error_response("user_id is required.", 400)

        if str(other_user_id) == str(request.user.pk):
            return error_response("You cannot start a conversation with yourself.", 400)

        try:
            other_user = User.objects.get(pk=other_user_id)
        except User.DoesNotExist:
            return error_response("User not found.", 404)

        user1_id = min(request.user.pk, other_user.pk)
        user2_id = max(request.user.pk, other_user.pk)

        conversation, created = Conversation.objects.get_or_create(
            user1_id=user1_id,
            user2_id=user2_id,
        )

        return success_response(
            "Conversation fetched successfully." if not created else "Conversation created successfully.",
            data={
                "conversation_id": conversation.conversation_id,
                "created": created,
            },
            status_code=200 if not created else 201
        )


class ConversationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        search = request.GET.get("search", "").strip()
        message_status = request.GET.get("message_status", "all").strip().lower()

        conversations = (
            Conversation.objects
            .filter(
                Q(user1=request.user) | Q(user2=request.user)
            )
            .annotate(
                unread_count=Count(
                    "messages",
                    filter=Q(messages__receiver=request.user, messages__is_seen=False),
                    distinct=True
                ),
                read_count=Count(
                    "messages",
                    filter=Q(messages__receiver=request.user, messages__is_seen=True),
                    distinct=True
                )
            )
            .select_related("user1", "user2")
            .prefetch_related("messages")
            .order_by("-updated_at")
        )

        # if search:
        #     conversations = conversations.filter(
        #         Q(user1__full_name__icontains=search) |
        #         Q(user2__full_name__icontains=search)
        #     )

        if search:
            conversations = conversations.filter(
                Q(user1__full_name__istartswith=search) |
                Q(user2__full_name__istartswith=search) |
                Q(user1__email__istartswith=search) |
                Q(user2__email__istartswith=search)
            )

        if message_status == "unread":
            conversations = conversations.filter(unread_count__gt=0)

        elif message_status == "read":
            conversations = conversations.filter(unread_count=0)

        elif message_status != "all":
            return error_response("message_status must be one of: all, read, unread.", 400)

        paginator = CustomPagination()
        paginator.page_size = 250
        paginated_conversations = paginator.paginate_queryset(conversations, request, view=self)

        serializer = ConversationListSerializer(
            paginated_conversations,
            many=True,
            context={"request": request}
        )

        unread_total = (
            Conversation.objects
            .filter(Q(user1=request.user) | Q(user2=request.user))
            .annotate(
                unread_count=Count(
                    "messages",
                    filter=Q(messages__receiver=request.user, messages__is_seen=False),
                    distinct=True
                )
            )
            .filter(unread_count__gt=0)
            .count()
        )

        read_total = (
            Conversation.objects
            .filter(Q(user1=request.user) | Q(user2=request.user))
            .annotate(
                unread_count=Count(
                    "messages",
                    filter=Q(messages__receiver=request.user, messages__is_seen=False),
                    distinct=True
                ),
                read_count=Count(
                    "messages",
                    filter=Q(messages__receiver=request.user, messages__is_seen=True),
                    distinct=True
                )
            )
            .filter(unread_count=0, read_count__gt=0)
            .count()
        )

        return paginator.get_paginated_response(
            {
                "unread_conversations": unread_total,
                "read_conversations": read_total,
                "results": serializer.data
            }
        )


class ConversationMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_conversation(self, request, conversation_id):
        return Conversation.objects.filter(
            conversation_id=conversation_id
        ).filter(
            models.Q(user1=request.user) | models.Q(user2=request.user)
        ).first()
    
    def mark_as_read(self, request, conversation_id):
        conversation = self.get_conversation(request, conversation_id)
        if not conversation:
            return 0

        updated_count = Message.objects.filter(
            conversation=conversation,
            receiver=request.user,
            is_seen=False
        ).update(is_seen=True, seen_at=timezone.now())

        return updated_count

    def get(self, request, conversation_id):
        conversation = self.get_conversation(request, conversation_id)
        self.mark_as_read(request, conversation_id)
        if not conversation:
            return error_response("Conversation not found.", 404)

        messages = (
            conversation.messages
            .select_related("sender", "receiver")
            .order_by("created_at")
        )
        paginator = CustomPagination()
        paginated_messages = paginator.paginate_queryset(messages, request, view=self)
        serializer = MessageSerializer(paginated_messages, many=True, context={'request': request})

        return paginator.get_paginated_response(
            {
                "conversation_id": conversation.conversation_id,
                "messages": serializer.data,
            }
        )


class UploadAttachmentMessageAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_conversation(self, request, conversation_id):
        return Conversation.objects.filter(
            conversation_id=conversation_id
        ).filter(
            models.Q(user1=request.user) | models.Q(user2=request.user)
        ).first()

    @transaction.atomic
    def post(self, request, conversation_id):
        conversation = self.get_conversation(request, conversation_id)
        if not conversation:
            return error_response("Conversation not found.", 404)

        attachment = request.FILES.get("attachment")
        text = request.data.get("text", "")
        message_type = request.data.get("message_type", "file")

        if not attachment:
            return error_response("attachment is required.", 400)

        if message_type not in ["image", "file"]:
            return error_response("message_type must be either 'image' or 'file'.", 400)

        if conversation.user1_id == request.user.pk:
            receiver_id = conversation.user2_id
        else:
            receiver_id = conversation.user1_id

        msg = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            receiver_id=receiver_id,
            message_type=message_type,
            text=text,
            attachment=attachment,
        )

        Conversation.objects.filter(conversation_id=conversation_id).update(updated_at=msg.created_at)

        serializer = MessageSerializer(msg, context={'request': request})
        return success_response("Attachment message sent successfully.", serializer.data, 201)


class MarkConversationSeenAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_conversation(self, request, conversation_id):
        return Conversation.objects.filter(
            conversation_id=conversation_id
        ).filter(
            models.Q(user1=request.user) | models.Q(user2=request.user)
        ).first()

    def patch(self, request, conversation_id):
        conversation = self.get_conversation(request, conversation_id)
        if not conversation:
            return error_response("Conversation not found.", 404)

        from django.utils import timezone
        updated_count = Message.objects.filter(
            conversation=conversation,
            receiver=request.user,
            is_seen=False
        ).update(is_seen=True, seen_at=timezone.now())

        return success_response(
            "Messages marked as seen successfully.",
            data={"updated_count": updated_count},
            status_code=200
        )
