from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Talent, TalentImage, TalentAvailableDate, WebImages, Team


class TalentImageInline(TabularInline):
    model = TalentImage
    extra = 0


@admin.register(Talent)
class TalentAdmin(ModelAdmin):
    list_display = ("talent_id", "name", "agent", "gender", "approval_status", "created_at")
    list_filter = ("approval_status", "gender", "country")
    search_fields = ("name", "agent__full_name", "country", "location")
    inlines = [TalentImageInline]


@admin.register(TalentImage)
class TalentImageAdmin(ModelAdmin):
    list_display = ("image_id", "talent", "is_primary", "uploaded_at")


@admin.register(TalentAvailableDate)
class TalentAvailableDateAdmin(ModelAdmin):
    list_display = ("talent", "available_date")



@admin.register(WebImages)
class WebImagesAdmin(ModelAdmin):
    list_display = ("id", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        # WebImages is a singleton, only allow one to be created
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ("name", "designation", "created_at", "updated_at")
    list_filter = ("designation", "created_at")
    search_fields = ("name", "designation")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("General Information", {
            "fields": ("name", "designation", "image")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
