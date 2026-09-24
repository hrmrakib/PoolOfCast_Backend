from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Meetings, MeetingRecord, Notifications


@admin.register(Notifications)
class NotificationsAdmin(ModelAdmin):
    list_display = ("id",)


@admin.register(MeetingRecord)
class MeetingRecordAdmin(ModelAdmin):
    list_display = ("id",)


@admin.register(Meetings)
class MeetingsAdmin(ModelAdmin):
    list_display = (
        "id",
        "title",
        "code",
        "job",
        "records_count",
    )

    search_fields = (
        "title",
        "code",
        "job__job_id",
    )

    list_filter = (
        "job",
    )

    ordering = ("-id",)

    list_per_page = 25

    readonly_fields = ("id",)

    fieldsets = (
        ("Meeting Information", {
            "fields": (
                "job",
                "title",
                "code",
                "records",
            )
        }),
    )

    filter_horizontal = ("records",)

    def records_count(self, obj):
        return obj.records.count()
