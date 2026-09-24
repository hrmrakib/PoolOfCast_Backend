from rest_framework import serializers
from .models import EcastingSession, EcastingParticipant, EcastingInvite


class EcastingSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EcastingSession
        fields = "__all__"


class EcastingParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = EcastingParticipant
        fields = "__all__"


class EcastingInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EcastingInvite
        fields = "__all__"