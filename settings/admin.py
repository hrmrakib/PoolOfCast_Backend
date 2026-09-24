from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import PrivacyPolicy, TermsAndCondition, AboutUs, ContactMessage


@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(ModelAdmin):
    list_display = ("id", "title", "created_on", "updated_on")
    search_fields = ("title", "content")
    list_filter = ("created_on", "updated_on")
    ordering = ("-created_on",)


@admin.register(TermsAndCondition)
class TermsAndConditionAdmin(ModelAdmin):
    list_display = ("id", "title", "created_on", "updated_on")
    search_fields = ("title", "content")
    list_filter = ("created_on", "updated_on")
    ordering = ("-created_on",)


@admin.register(AboutUs)
class AboutUsAdmin(ModelAdmin):
    list_display = ("id", "title", "created_on", "updated_on")
    search_fields = ("title", "content")
    list_filter = ("created_on", "updated_on")
    ordering = ("-created_on",)


@admin.register(ContactMessage)
class ContactMessageAdmin(ModelAdmin):
    list_display = ("id", "first_name", "last_name", "email", "phone_number", "created_at")
    search_fields = ("first_name", "last_name", "email", "phone_number", "message")
    list_filter = ("created_at",)
    ordering = ("-created_at",)