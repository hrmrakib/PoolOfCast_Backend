from django.urls import path

from .casting_requests_views import (
    PolaUploadAPIView,
    RequestECastingAPIView,
    RequestPolasAPIView,
    RequestSelfTapeAPIView,
    SelfTapeUploadAPIView,
)

urlpatterns = [
    path("request-selftape", RequestSelfTapeAPIView.as_view(), name="request_selftape"),
    path("request-ecasting", RequestECastingAPIView.as_view(), name="request_ecasting"),
    path("request-polas", RequestPolasAPIView.as_view(), name="request_polas"),
    path("selftape/upload", SelfTapeUploadAPIView.as_view(), name="selftape_upload"),
    path("polas/upload", PolaUploadAPIView.as_view(), name="polas_upload"),
]
