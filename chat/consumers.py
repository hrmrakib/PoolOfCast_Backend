import json
from django.db import models
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from .models import Conversation, Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user", AnonymousUser())

        if not self.user or self.user.is_anonymous:
            await self.close(code=4001)
            return

        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"

        is_member = await self.is_user_in_conversation(self.user.pk, self.conversation_id)
        if not is_member:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )
        except Exception:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json({
                "type": "error",
                "message": "Invalid JSON payload."
            })
            return

        action = data.get("action")

        if action == "fetch_chat":
            messages = await self.get_conversation_messages(
                conversation_id=self.conversation_id
            )

            await self.send_json({
                "type": "fetch_chat",
                "message": "Conversation messages fetched successfully.",
                "data": {
                    "conversation_id": int(self.conversation_id),
                    "messages": messages
                }
            })

        elif action == "send_message":
            text = (data.get("text") or "").strip()
            if not text:
                await self.send_json({
                    "type": "error",
                    "message": "Message text is required."
                })
                return

            saved_message = await self.save_text_message(
                conversation_id=self.conversation_id,
                sender_id=self.user.pk,
                text=text,
            )

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat.message",
                    "payload": saved_message,
                }
            )


        elif action == "seen":
            await self.mark_messages_seen(
                conversation_id=self.conversation_id,
                receiver_id=self.user.pk,
            )

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "messages.seen",
                    "payload": {
                        "conversation_id": int(self.conversation_id),
                        "seen_by": self.user.pk,
                    },
                }
            )

        else:
            await self.send_json({
                "type": "error",
                "message": "Unsupported action."
            })

    async def chat_message(self, event):
        await self.send_json({
            "type": "message",
            "data": event["payload"]
        })

    async def messages_seen(self, event):
        await self.send_json({
            "type": "seen",
            "data": event["payload"]
        })

    async def send_json(self, content):
        await self.send(text_data=json.dumps(content, default=str))

    @database_sync_to_async
    def is_user_in_conversation(self, user_id, conversation_id):
        return Conversation.objects.filter(
            conversation_id=conversation_id
        ).filter(
            models.Q(user1_id=user_id) | models.Q(user2_id=user_id)
        ).exists()

    @database_sync_to_async
    def save_text_message(self, conversation_id, sender_id, text):
        conversation = Conversation.objects.get(conversation_id=conversation_id)

        if conversation.user1_id == sender_id:
            receiver_id = conversation.user2_id
        else:
            receiver_id = conversation.user1_id

        msg = Message.objects.create(
            conversation=conversation,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="text",
            text=text,
        )

        Conversation.objects.filter(conversation_id=conversation_id).update(updated_at=timezone.now())

        return {
            "message_id": msg.message_id,
            "conversation_id": msg.conversation_id,
            "sender_id": msg.sender_id,
            "receiver_id": msg.receiver_id,
            "message_type": msg.message_type,
            "text": msg.text,
            "attachment_url": msg.attachment.url if msg.attachment else None,
            "is_seen": msg.is_seen,
            "seen_at": msg.seen_at,
            "created_at": msg.created_at.isoformat(),
        }

    @database_sync_to_async
    def mark_messages_seen(self, conversation_id, receiver_id):
        now = timezone.now()
        Message.objects.filter(
            conversation_id=conversation_id,
            receiver_id=receiver_id,
            is_seen=False
        ).update(is_seen=True, seen_at=now)


    @database_sync_to_async
    def get_conversation_messages(self, conversation_id):
        messages = (
            Message.objects
            .filter(conversation_id=conversation_id)
            .select_related("sender", "receiver")
            .order_by("created_at")
        )

        message_list = []
        for msg in messages:
            message_list.append({
                "message_id": msg.message_id,
                "conversation_id": msg.conversation_id,
                "sender_id": msg.sender_id,
                "sender_name": getattr(msg.sender, "full_name", None) or getattr(msg.sender, "username", None) or str(msg.sender),
                "receiver_id": msg.receiver_id,
                "receiver_name": getattr(msg.receiver, "full_name", None) or getattr(msg.receiver, "username", None) or str(msg.receiver),
                "message_type": msg.message_type,
                "text": msg.text,
                "attachment_url": msg.attachment.url if msg.attachment else None,
                "is_seen": msg.is_seen,
                "seen_at": msg.seen_at.isoformat() if msg.seen_at else None,
                "created_at": msg.created_at.isoformat(),
            })

        return message_list