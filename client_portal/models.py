import uuid

from django.conf import settings
from django.db import models

from talent.models import Talent

# NOTE: jobs.Job.job_id is declared as a CharField in Django, but the physical
# `jobs_talent_job.job_id` column in the (legacy, unmanaged) database is actually an
# integer. A real ForeignKey to Job triggers "operator does not exist: character
# varying = integer" as soon as Django needs to JOIN across it. Job.job_created_by_id
# already works around this in the same table by being a bare int field instead of an
# FK; every `job_id` field below follows that same precedent deliberately.


class GuestClient(models.Model):
    """A non-registered client identified only by name + email on a single shortlist link."""

    id = models.BigAutoField(primary_key=True)
    job_id = models.PositiveIntegerField(db_index=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)

    # Proves the caller actually controls `email` before a guest_token is ever handed
    # out — otherwise anyone who knows/guesses a client's email (job_id in the link is
    # a small guessable int, not a secret) could type it in and get handed that guest's
    # existing token, chat history, favorites, and comments. See generate_and_send_otp
    # in accounts/send_otp.py, reused as-is (it's duck-typed on otp/otp_expired_at/email).
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_expired_at = models.DateTimeField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "client_portal_guest_clients"
        ordering = ["-last_seen_at"]
        constraints = [
            models.UniqueConstraint(fields=["job_id", "email"], name="uniq_guest_per_job_email")
        ]

    def __str__(self):
        return f"{self.name} <{self.email}> - job {self.job_id}"


class TalentFavorite(models.Model):
    id = models.BigAutoField(primary_key=True)
    guest_client = models.ForeignKey(
        GuestClient,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    talent = models.ForeignKey(
        Talent,
        on_delete=models.CASCADE,
        related_name="guest_favorites",
    )
    job_id = models.PositiveIntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "client_portal_talent_favorites"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["guest_client", "talent"], name="uniq_favorite_per_guest_talent")
        ]

    def __str__(self):
        return f"{self.guest_client_id} favorited {self.talent_id}"


class TalentComment(models.Model):
    id = models.BigAutoField(primary_key=True)
    guest_client = models.ForeignKey(
        GuestClient,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    talent = models.ForeignKey(
        Talent,
        on_delete=models.CASCADE,
        related_name="guest_comments",
    )
    job_id = models.PositiveIntegerField(db_index=True)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "client_portal_talent_comments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.guest_client_id} on {self.talent_id}: {self.comment[:40]}"


class ClientChatThread(models.Model):
    id = models.BigAutoField(primary_key=True)
    guest_client = models.OneToOneField(
        GuestClient,
        on_delete=models.CASCADE,
        related_name="chat_thread",
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="guest_chat_threads",
        null=True,
        blank=True,
    )
    job_id = models.PositiveIntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "client_portal_chat_threads"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Thread {self.id}: guest {self.guest_client_id} <-> agent {self.agent_id}"


class ClientChatMessage(models.Model):
    SENDER_TYPE_CHOICES = [
        ("client", "Client"),
        ("agent", "Agent"),
    ]
    MESSAGE_TYPE_CHOICES = [
        ("text", "Text"),
        ("image", "Image"),
        ("file", "File"),
    ]

    id = models.BigAutoField(primary_key=True)
    thread = models.ForeignKey(
        ClientChatThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender_type = models.CharField(max_length=10, choices=SENDER_TYPE_CHOICES)
    sender_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sent_guest_chat_messages",
        null=True,
        blank=True,
    )
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default="text")
    text = models.TextField(blank=True, null=True)
    attachment = models.FileField(upload_to="client_chat_attachments/", blank=True, null=True)
    is_seen_by_agent = models.BooleanField(default=False)
    is_seen_by_client = models.BooleanField(default=False)
    seen_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "client_portal_chat_messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
        ]

    def __str__(self):
        return f"Message {self.id} in thread {self.thread_id}"
