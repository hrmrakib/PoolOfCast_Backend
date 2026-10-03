from django.urls import path

from .shortlist_booking_views import BookTalentAPIView, DeleteShortlistAPIView, ShortlistTalentAPIView

urlpatterns = [
    path("shortlist", ShortlistTalentAPIView.as_view(), name="shortlistTalent"),
    path("delete-shortlist", DeleteShortlistAPIView.as_view(), name="deleteSingleTalentFromShortlist"),
    path("book", BookTalentAPIView.as_view(), name="bookTalent"),
]
