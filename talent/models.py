from django.db import models
from django.conf import settings
from jobs.models import Job

class Talent(models.Model):
    ROLE_CHOICES = [
        ("model", "Model"),
        ("actor", "Actor"),
    ]

    CHARACTER_CHOICES = [
        ("Actor", "Actor"),
        ("Model", "Model"),
        ("Character", "Character"),
        ("Influencer", "Influencer"),
        ("Performer", "Performer"),
        ("Dancer", "Dancer"),
        ("Kid", "Kid"),
        ("Plus size", "Plus size"),
    ]

    GENDER_CHOICES = [
        ("female", "Female"),
        ("male", "Male"),
        ("nonbinary", "Nonbinary"),
    ]

    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    talent_id = models.BigAutoField(primary_key=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="model")
    character = models.CharField(max_length=20, choices=CHARACTER_CHOICES, default="actor")

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="talents"
    )

    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    name = models.CharField(max_length=255)

    height = models.CharField(max_length=50, blank=True, null=True)
    waist = models.CharField(max_length=50, blank=True, null=True)
    bust = models.CharField(max_length=50, blank=True, null=True)
    hips = models.CharField(max_length=50, blank=True, null=True)
    dress_size = models.CharField(max_length=50, blank=True, null=True)
    shoe_size = models.CharField(max_length=50, blank=True, null=True)

    hair_colour = models.CharField(max_length=100, blank=True, null=True)
    eye_colour = models.CharField(max_length=100, blank=True, null=True)
    skin_color = models.CharField(max_length=100, blank=True, null=True)
    hair_type = models.CharField(max_length=100, blank=True, null=True)

    continent = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    skills = models.TextField()
    portfolio_link = models.URLField(blank=True, null=True)
    instagram_link = models.URLField(blank=True, null=True)
    rate = models.CharField(max_length=100, blank=True, null=True)

    date_of_birth = models.DateField(blank=True, null=True)

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default="pending"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_talents",
        blank=True,
        null=True
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    is_available_on_request = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "talents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.approval_status}"


class TalentImage(models.Model):
    image_id = models.BigAutoField(primary_key=True)

    talent = models.ForeignKey(
        Talent,
        on_delete=models.CASCADE,
        related_name="images"
    )
    image = models.ImageField(upload_to="talents/")
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "talent_images"
        ordering = ["image_id"]

    def __str__(self):
        return f"{self.talent.name} Image {self.image_id}"
    


class TalentAvailableDate(models.Model):
    availability_id = models.BigAutoField(primary_key=True)
    talent = models.ForeignKey(
        Talent,
        on_delete=models.CASCADE,
        related_name="available_dates"
    )
    available_date = models.DateField()
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "talent_available_dates"
        ordering = ["available_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["talent", "available_date"],
                name="unique_talent_available_date"
            )
        ]

    def __str__(self):
        return f"{self.talent.name} - {self.available_date}"




class TalentBookingDate(models.Model):
    booking_date_id = models.BigAutoField(primary_key=True)
    talent = models.ForeignKey(
        Talent,
        on_delete=models.CASCADE,
        related_name="booking_dates"
    )
    booked_date = models.DateField()
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="booked_talents",
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
        default="confirmed"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "talent_booking_dates"
        ordering = ["booked_date"]

    def __str__(self):
        return f"{self.talent.name} - {self.booked_date}"
    






class ShortListedTalent(models.Model):
    shortlisted_id = models.BigAutoField(primary_key=True)
    talent = models.ForeignKey(
        Talent,
        on_delete=models.DO_NOTHING,
        db_column="talent_id",
        null=True,
        blank=True
    )
    user_id = models.IntegerField(blank=True, null=True)
    job = models.ForeignKey(
        Job,
        on_delete=models.DO_NOTHING,
        db_column="job_id",
        null=True,
        blank=True
    )
    session_id = models.CharField(max_length=255, blank=True, null=True)
    # jobs_talent_job = models.CharField(max_length=255,db_column="jobs_talent_job", blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "jobs_shortlisted_talents"
        ordering = ["-created_at"]
        managed = False




class ShortlistOrder(models.Model):
    """Client-defined drag-and-drop position of a shortlisted talent within a job.

    Kept in its own table because jobs_shortlisted_talents is unmanaged (FastAPI-owned),
    so shortlisted_id is a plain integer, not a FK.
    """
    shortlisted_id = models.BigIntegerField(unique=True)
    job_id = models.IntegerField(db_index=True)
    position = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "talent_shortlist_order"


class WebImages(models.Model):
    iamge1 = models.ImageField(upload_to='webimage')
    iamge2 = models.ImageField(upload_to='webimage')
    iamge3 = models.ImageField(upload_to='webimage')
    iamge4 = models.ImageField(upload_to='webimage')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super(WebImages, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj



class Team(models.Model):
    name = models.CharField(max_length=250)
    designation = models.CharField(max_length=250)
    image = models.ImageField(upload_to='team_images')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    