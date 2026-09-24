import asyncio
import json
import os

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import ClientChatMessage, ClientChatThread
from .utils import resolve_guest_by_token

User = get_user_model()

# A JWT (or guest token) in the connection URL ends up in access logs and browser
# history, so credentials are never accepted as query params here. The client must
# connect anonymously and send {"action": "auth", ...} as its first message; the
# connection is held open-but-unauthorized until that arrives, and dropped if it
# doesn't within this window.
AUTH_TIMEOUT_SECONDS = 5

MAX_MESSAGE_LENGTH = 4000


class GuestChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.thread_id = self.scope["url_route"]["kwargs"]["thread_id"]
        self.room_group_name = f"client_chat_{self.thread_id}"
        self.authenticated = False
        self.sender_type = None
        self.sender_agent_id = None
        self._auth_timeout_task = None

        thread = await self.get_thread(self.thread_id)
        if not thread:
            await self.close(code=4004)
            return
        self.thread = thread

        await self.accept()
        self._auth_timeout_task = asyncio.ensure_future(self._enforce_auth_timeout())

    async def _enforce_auth_timeout(self):
        await asyncio.sleep(AUTH_TIMEOUT_SECONDS)
        if not self.authenticated:
            await self.send_json({"type": "error", "message": "Authentication timed out."})
            await self.close(code=4001)

    async def disconnect(self, close_code):
        if self._auth_timeout_task and not self._auth_timeout_task.done():
            self._auth_timeout_task.cancel()

        if self.authenticated:
            try:
                await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            except Exception:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json({"type": "error", "message": "Invalid JSON payload."})
            return

        if not isinstance(data, dict):
            await self.send_json({"type": "error", "message": "Payload must be a JSON object."})
            return

        action = data.get("action")

        if not self.authenticated:
            if action != "auth":
                await self.send_json({
                    "type": "error",
                    "message": 'Send {"action": "auth", "token": "..."} or {"action": "auth", "guest_token": "..."} first.',
                })
                return
            await self._handle_auth(data)
            return

        if action == "fetch_chat":
            messages = await self.get_thread_messages(self.thread_id)
            await self.send_json({
                "type": "fetch_chat",
                "message": "Conversation messages fetched successfully.",
                "data": {"thread_id": int(self.thread_id), "messages": messages},
            })

        elif action == "send_message":
            text = data.get("text")
            if not isinstance(text, str):
                await self.send_json({"type": "error", "message": "Message text must be a string."})
                return

            text = text.strip()
            if not text:
                await self.send_json({"type": "error", "message": "Message text is required."})
                return
            if len(text) > MAX_MESSAGE_LENGTH:
                await self.send_json({
                    "type": "error",
                    "message": f"Message text must be {MAX_MESSAGE_LENGTH} characters or fewer.",
                })
                return

            saved_message = await self.save_text_message(
                thread_id=self.thread_id,
                sender_type=self.sender_type,
                sender_agent_id=self.sender_agent_id,
                text=text,
            )

            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat.message", "payload": saved_message},
            )

        elif action == "seen":
            await self.mark_messages_seen(thread_id=self.thread_id, seen_by=self.sender_type)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "messages.seen",
                    "payload": {"thread_id": int(self.thread_id), "seen_by": self.sender_type},
                },
            )

        else:
            await self.send_json({"type": "error", "message": "Unsupported action."})

    async def _handle_auth(self, data):
        guest_token = data.get("guest_token")
        jwt_token = data.get("token")

        if guest_token:
            guest = await self.get_guest_client(guest_token)
            if not guest or guest["id"] != self.thread["guest_client_id"]:
                await self.send_json({"type": "error", "message": "Invalid guest session."})
                await self.close(code=4003)
                return
            self.sender_type = "client"
            self.sender_agent_id = None

        elif jwt_token:
            user = await self.get_user_from_jwt(jwt_token)
            if not user:
                await self.send_json({"type": "error", "message": "Invalid or expired token."})
                await self.close(code=4001)
                return
            is_owner_agent = self.thread["agent_id"] == user["id"]
            is_admin = user["role"] == "Admin"
            if not (is_owner_agent or is_admin):
                await self.send_json({"type": "error", "message": "Not authorized for this conversation."})
                await self.close(code=4003)
                return
            self.sender_type = "agent"
            self.sender_agent_id = user["id"]

        else:
            await self.send_json({"type": "error", "message": "token or guest_token is required."})
            return

        self.authenticated = True
        if self._auth_timeout_task and not self._auth_timeout_task.done():
            self._auth_timeout_task.cancel()

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.send_json({"type": "auth_ok", "data": {"sender_type": self.sender_type}})

    async def chat_message(self, event):
        await self.send_json({"type": "message", "data": event["payload"]})

    async def messages_seen(self, event):
        await self.send_json({"type": "seen", "data": event["payload"]})

    async def send_json(self, content):
        await self.send(text_data=json.dumps(content, default=str))

    @database_sync_to_async
    def get_thread(self, thread_id):
        thread = ClientChatThread.objects.filter(id=thread_id).first()
        if not thread:
            return None
        return {"id": thread.id, "guest_client_id": thread.guest_client_id, "agent_id": thread.agent_id}

    @database_sync_to_async
    def get_guest_client(self, token):
        guest = resolve_guest_by_token(token)
        if not guest:
            return None
        return {"id": guest.id}

    @database_sync_to_async
    def get_user_from_jwt(self, token):
        try:
            validated_token = AccessToken(token)
            user_pk = validated_token["user_id"]
        except (TokenError, KeyError, Exception):
            return None

        user = User.objects.filter(pk=user_pk).first()
        if not user:
            return None
        return {"id": user.pk, "role": getattr(user, "role", None)}

    @database_sync_to_async
    def save_text_message(self, thread_id, sender_type, sender_agent_id, text):
        msg = ClientChatMessage.objects.create(
            thread_id=thread_id,
            sender_type=sender_type,
            sender_agent_id=sender_agent_id,
            message_type="text",
            text=text,
            is_seen_by_agent=(sender_type == "agent"),
            is_seen_by_client=(sender_type == "client"),
        )

        ClientChatThread.objects.filter(id=thread_id).update(updated_at=timezone.now())

        return {
            "message_id": msg.id,
            "thread_id": msg.thread_id,
            "sender_type": msg.sender_type,
            "sender_agent_id": msg.sender_agent_id,
            "message_type": msg.message_type,
            "text": msg.text,
            "attachment_url": msg.attachment.url if msg.attachment else None,
            "file_name": os.path.basename(msg.attachment.name) if msg.attachment else None,
            "is_seen_by_agent": msg.is_seen_by_agent,
            "is_seen_by_client": msg.is_seen_by_client,
            "seen_at": msg.seen_at,
            "created_at": msg.created_at.isoformat(),
        }

    @database_sync_to_async
    def mark_messages_seen(self, thread_id, seen_by):
        now = timezone.now()
        if seen_by == "agent":
            ClientChatMessage.objects.filter(
                thread_id=thread_id, sender_type="client", is_seen_by_agent=False
            ).update(is_seen_by_agent=True, seen_at=now)
        else:
            ClientChatMessage.objects.filter(
                thread_id=thread_id, sender_type="agent", is_seen_by_client=False
            ).update(is_seen_by_client=True, seen_at=now)

    @database_sync_to_async
    def get_thread_messages(self, thread_id):
        messages = ClientChatMessage.objects.filter(thread_id=thread_id).select_related("sender_agent").order_by("created_at")

        message_list = []
        for msg in messages:
            message_list.append({
                "message_id": msg.id,
                "thread_id": msg.thread_id,
                "sender_type": msg.sender_type,
                "sender_agent_id": msg.sender_agent_id,
                "message_type": msg.message_type,
                "text": msg.text,
                "attachment_url": msg.attachment.url if msg.attachment else None,
                "file_name": os.path.basename(msg.attachment.name) if msg.attachment else None,
                "is_seen_by_agent": msg.is_seen_by_agent,
                "is_seen_by_client": msg.is_seen_by_client,
                "seen_at": msg.seen_at.isoformat() if msg.seen_at else None,
                "created_at": msg.created_at.isoformat(),
            })

        return message_list
