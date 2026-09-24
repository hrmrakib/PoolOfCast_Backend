import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from chat.middleware import JWTAuthMiddleware
from chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns
from client_portal.routing import websocket_urlpatterns as client_portal_websocket_urlpatterns

# JWTAuthMiddleware populates scope["user"] from ?token=<jwt> for chat.consumers.ChatConsumer.
# client_portal.consumers.GuestChatConsumer doesn't rely on it — a credential in the
# connection URL ends up in access logs and browser history, so that route authenticates
# guests and agents from the first WebSocket message instead (see GuestChatConsumer._handle_auth).
# The middleware still wraps that route too, but has nothing to populate for it.
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter([*chat_websocket_urlpatterns, *client_portal_websocket_urlpatterns])
    ),
})
