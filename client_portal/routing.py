from django.urls import re_path

from .consumers import GuestChatConsumer

websocket_urlpatterns = [
    re_path(r"ws/client-chat/(?P<thread_id>\d+)/?$", GuestChatConsumer.as_asgi())
]
