from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model

User = get_user_model()


@database_sync_to_async
def get_user_from_db(user_pk):
    try:
        return User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Usage:
    ws://127.0.0.1:8000/ws/chat/<conversation_id>/?token=<access_token>
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope["user"] = AnonymousUser()

        try:
            query_string = scope.get("query_string", b"").decode()
            query_params = parse_qs(query_string)
            token_list = query_params.get("token")

            if token_list:
                raw_token = token_list[0]
                validated_token = AccessToken(raw_token)
                user_pk = validated_token["user_id"]
                scope["user"] = await get_user_from_db(user_pk)
        except (TokenError, KeyError, Exception):
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)