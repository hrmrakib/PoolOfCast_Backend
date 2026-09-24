from django.urls import path
from .views import *

urlpatterns = [
    path('privacy_policies/', PrivacyPolicyListCreateAPIView.as_view(), name='privacy_policies'),
    path('terms_conditions/', TermsAndConditionsListCreateAPIView.as_view(), name='terms_conditions'),
    path('about_us/', AboutUsListCreateAPIView.as_view(), name='about_us'),
    path("contact/", ContactMessageCreateAPIView.as_view(), name="contact-message"),
]