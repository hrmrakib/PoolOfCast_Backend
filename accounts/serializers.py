from rest_framework import serializers
from django.contrib.auth import get_user_model
User = get_user_model()
class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    phone = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = [
            'email',
            'phone',
            'password',
            'full_name',
            'role',
            'profile_pic',
            'bio',
            'agency_name',
            'company',
            'website',
            'country',
            'city',
            'is_subscribed',
        ]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user



class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)




class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ['password', 'is_superuser', 'is_staff', 'groups', 'user_permissions', 'otp', 'otp_expired_at', 'is_active','last_login']





class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "user_id",
            "full_name",
            "email",
            "phone",
            "role",
            "profile_pic",
            "is_active",
            "is_verified",
            "date_joined",
        ]


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "user_id",
            "full_name",
            "email",
            "phone",
            "profile_pic",
            "role",
            "bio",
            "agency_name",
            "company",
            "website",
            "is_active",
            "is_verified",
            "date_joined",
        ]


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = [
            "full_name",
            "email",
            "phone",
            "profile_pic",
            "bio",
            "agency_name",
            "company",
            "website",
        ]

    def validate_email(self, value):
        user = self.instance
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_phone(self, value):
        user = self.instance
        if User.objects.exclude(pk=user.pk).filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = [
            "full_name",
            "email",
            "phone",
            "profile_pic",
            "role",
            "bio",
            "agency_name",
            "company",
            "website",
            "is_active",
        ]

    def validate_email(self, value):
        user = self.instance
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_phone(self, value):
        user = self.instance
        if User.objects.exclude(pk=user.pk).filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value


class UserStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["is_active"]










class RecentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude =['is_superuser', 'is_staff', 'groups', 'user_permissions', 'otp', 'otp_expired_at', 'is_active','last_login','password']
    





from rest_framework import serializers
from jobs.models import Notifications
from accounts.models import User


class NotificationSenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "user_id",
            "full_name",
            "email",
            "phone",
            "profile_pic",
        ]


class NotificationDetailSerializer(serializers.ModelSerializer):
    sender = NotificationSenderSerializer(read_only=True)
    created_at = serializers.DateTimeField(format="%d %b %Y, %I:%M %p")

    class Meta:
        model = Notifications
        fields = [
            "id",
            "event",
            "sender",
            "created_at",
        ]