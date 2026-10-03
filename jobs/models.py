from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()


class Job(models.Model):

    job_id = models.CharField(max_length=50, primary_key=True)
    job_created_by_id = models.PositiveIntegerField()
    session_id = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    casting_roles = models.TextField()
    location = models.CharField(max_length=255, blank=True)

    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    job_type = models.CharField(max_length=100)

    applicants_count = models.PositiveIntegerField(default=0)
    shortlisted_count = models.PositiveIntegerField(default=0)
    selftapes_count = models.PositiveIntegerField(default=0)
    ecastings_count = models.PositiveIntegerField(default=0)
    polas_count = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=20)
    currency = models.CharField(max_length=250)
    job_photo = models.CharField(max_length=250, null=True, blank=True)

    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "jobs_talent_job"
        ordering = ["-created_at"]
        managed = False


class JobAIResult(models.Model):
    result_id = models.IntegerField(primary_key=True)
    job_id = models.IntegerField(blank=True, null=True)
    suggested_talents = models.TextField(blank=True, null=True)
    shoot_date = models.TextField(blank=True, null=True)
    requested_selftapes = models.TextField(blank=True, null=True)
    requested_ecastings = models.TextField(blank=True, null=True)
    requested_polas = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobs_ai_results"
        managed = False


class DraftJob(models.Model):

    draft_id = models.CharField(max_length=50, primary_key=True)
    user_id = models.PositiveIntegerField()
    session_id = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    phase = models.CharField(max_length=255)
    saved_filters = models.TextField()
    job_type = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)
    shoot_date = models.CharField(max_length=255, blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    last_updated = models.DateTimeField()

    class Meta:
        db_table = "jobs_talent_drafts"
        managed = False


class MeetingRecord(models.Model):
    meeting_record = models.URLField(null=True, blank=True)


class Meetings(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=250, null=True, blank=True)
    code = models.CharField(max_length=250, null=True, blank=True)
    records = models.ManyToManyField(MeetingRecord, related_name='meeting_records')

    def __str__(self):
        job_id = self.job.job_id if self.job else "no-job"
        return f"{job_id}---{self.title or 'untitled'}"


class Notifications(models.Model):
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="receiver")
    event = models.TextField()
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="sender", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)



class JobRole(models.Model):
    job_role = models.CharField(max_length=250)

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        db_column="job_id",
        to_field="job_id",
        related_name="roles"
    )

    talent = models.ForeignKey(
        "talent.Talent",
        on_delete=models.CASCADE,
        related_name="job_roles",
        null=True,
        blank=True,
    )

    assign_status = models.BooleanField(default=True)
    # session_id = models.ForeignKey()

    def __str__(self):
        return self.job_role


class AgentHiddenJob(models.Model):
    agent_id = models.PositiveIntegerField()
    job_id = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('agent_id', 'job_id')


REQUEST_STATUS_CHOICES = [
    ("requested", "Requested"),
    ("accepted", "Accepted"),
    ("rejected", "Rejected"),
    ("responded", "Responded"),
]


class SelfTapeRequest(models.Model):
    request_id = models.AutoField(primary_key=True)
    job_id = models.IntegerField()
    talent_id = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default="requested")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobs_selftape_requests"
        managed = False


class SelfTapeLink(models.Model):
    link_id = models.AutoField(primary_key=True)
    request = models.ForeignKey(
        SelfTapeRequest,
        on_delete=models.DO_NOTHING,
        db_column="request_id",
        related_name="links",
    )
    tape_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "jobs_selftape_links"
        managed = False


class PolaRequest(models.Model):
    request_id = models.AutoField(primary_key=True)
    job_id = models.IntegerField()
    talent_id = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default="requested")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobs_pola_requests"
        managed = False


class PolaLink(models.Model):
    link_id = models.AutoField(primary_key=True)
    request = models.ForeignKey(
        PolaRequest,
        on_delete=models.DO_NOTHING,
        db_column="request_id",
        related_name="links",
    )
    pola_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "jobs_pola_links"
        managed = False


class JobRoleAssignment(models.Model):
    id = models.AutoField(primary_key=True)
    job_id = models.IntegerField()
    job_role = models.ForeignKey(
        JobRole,
        on_delete=models.CASCADE,
        db_column="job_role_id",
        related_name="assignments",
    )
    talent = models.ForeignKey(
        "talent.Talent",
        on_delete=models.DO_NOTHING,
        db_column="talent_id",
        related_name="role_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "jobs_jobrole_assignments"
        managed = False


class Booking(models.Model):
    booking_id = models.AutoField(primary_key=True)
    session_id = models.CharField(max_length=255, null=True, blank=True)
    user_id = models.BigIntegerField()
    talent = models.ForeignKey(
        "talent.Talent",
        on_delete=models.DO_NOTHING,
        db_column="talent_id",
        related_name="bookings",
    )
    job_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    booking_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "jobs_talent_bookings"
        managed = False