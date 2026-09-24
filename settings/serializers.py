from rest_framework import serializers
from .models import *


class PrivacyPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyPolicy
        fields = ['id', 'title', 'content', 'created_on', 'updated_on']
        read_only_fields = ['created_on', 'updated_on']


class TermsAndConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TermsAndCondition
        fields = ['id', 'title', 'content', 'created_on', 'updated_on']
        read_only_fields = ['created_on', 'updated_on']


class AboutUsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AboutUs
        fields = ['id', 'title', 'content', 'created_on', 'updated_on']
        read_only_fields = ['created_on', 'updated_on']


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = "__all__"
        read_only_fields = ("id", "created_at")