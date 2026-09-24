from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from .manager import UserManager



class User(AbstractBaseUser, PermissionsMixin):
    
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Agent', 'Agent'),
        ('Client', 'Client'),
    ]
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]

    user_id = models.BigAutoField(primary_key=True)

    email = models.EmailField(unique=True, max_length=255)
    phone = models.CharField(max_length=15, unique=True)

    full_name = models.CharField(max_length=255)
    profile_pic = models.ImageField(
        upload_to="profile/",
        default="profile/profile.png",
        null=True,
        blank=True,
    )
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Client')
    
    bio = models.TextField(null=True, blank=True)
    
    agency_name = models.CharField(max_length=255, null=True, blank=True)
    company = models.CharField(max_length=255, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    
    country = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)

    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_expired_at = models.DateTimeField(null=True, blank=True)

    is_superuser = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=True)
    
    is_subscribed = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    def __str__(self) -> str:
        return self.email
