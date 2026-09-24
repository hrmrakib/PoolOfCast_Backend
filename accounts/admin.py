from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from unfold.admin import ModelAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin, ModelAdmin):

    model = User

    list_display = (
        "user_id",
        "email",
        "phone",
        "full_name",
        "role",
        "is_verified",
        "is_active",
        "is_staff",
        "date_joined",
    )

    list_filter = (
        "role",
        "is_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    )

    search_fields = ("email", "phone", "full_name")
    ordering = ("-date_joined",)

    readonly_fields = ("user_id", "date_joined", "updated_at", "last_login")

    fieldsets = (
        ("Authentication Info", {
            "fields": ("email", "password")
        }),

        ("Personal Info", {
            "fields": (
                "full_name",
                "phone",
                "profile_pic",
                "bio",
            )
        }),

        ("Agency / Company Info", {
            "fields": (
                "agency_name",
                "company",
                "website",
                "country",
                "city",
            )
        }),

        ("Role & Status", {
            "fields": (
                "role",
                "is_verified",
                "is_subscribed",
                "is_active",
                "is_staff",
                "is_superuser",
            )
        }),

        ("OTP Info", {
            "fields": (
                "otp",
                "otp_expired_at",
            )
        }),

        ("Important Dates", {
            "fields": (
                "last_login",
                "date_joined",
                "updated_at",
            )
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "full_name",
                "phone",
                "role",
                "password1",
                "password2",
                "is_active",
                "is_staff",
            ),
        }),
    )