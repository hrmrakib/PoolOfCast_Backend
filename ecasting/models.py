import uuid
from django.db import models
from django.conf import settings
from accounts.models import User


class EcastingSession(models.Model):
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_id = models.CharField(max_length=255, blank=True, null=True)
    room_id = models.CharField(max_length=255, unique=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_sessions")
    title = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ecasting_sessions"
        ordering = ["-created_at"]

    def __str__(self):
        return self.room_id




class EcastingParticipant(models.Model):
    session = models.ForeignKey(EcastingSession, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(User, on_delete=models.CASCADE,null=True, blank=True)

    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)

    is_host = models.BooleanField(default=False)

    class Meta:
        db_table = "ecasting_participants"

    class Meta:
        unique_together = ("session", "user")



class EcastingInvite(models.Model):
    session = models.ForeignKey(EcastingSession, on_delete=models.CASCADE, related_name="invites")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "ecasting_invites"