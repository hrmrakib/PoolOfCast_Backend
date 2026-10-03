from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

class HelloHorld(APIView):
    def get(self, request):
        return Response(
            {
               "message":"Hello Wrold!"
                
            },
            status=status.HTTP_200_OK
        )



urlpatterns = [
    path('', HelloHorld.as_view(), name="hello-word"),
    path('admin/', admin.site.urls),
    path('api/v1/accounts/', include('accounts.urls')),
    path('api/v1/settings/', include('settings.urls')),
    path("api/v1/", include("talent.urls")),
    path("api/v1/", include("client_portal.urls")),
    path("api/v1/chat/", include("chat.urls")),
    path("api/v1/jobs/", include("jobs.urls")),
    path("api/v1/ecasting/", include("ecasting.urls")),
    path("api/v1/jobs/", include("jobs.casting_requests_urls")),
    path("api/v1/jobs/", include("jobs.job_management_urls")),
    path("api/v1/jobs/", include("jobs.role_assignment_urls")),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
