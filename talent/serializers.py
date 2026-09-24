from rest_framework import serializers
from django.db import transaction
from .models import *
from django.contrib.auth import get_user_model

User = get_user_model()

class TalentImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TalentImage
        fields = ["image_id", "image", "is_primary", "uploaded_at"]
        read_only_fields = ["image_id", "uploaded_at"]


class TalentSerializer(serializers.ModelSerializer):
    images = TalentImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    available_date = serializers.ListField(
        child=serializers.DateField(),
        write_only=True,
        required=False
    )
    available_dates = serializers.SerializerMethodField()

    class Meta:
        model = Talent
        fields = [
            "talent_id",
            "role",
            "character",
            "gender",
            "name",
            "height",
            "waist",
            "bust",
            "hips",
            "dress_size",
            "shoe_size",
            "hair_colour",
            "eye_colour",
            "skin_color",
            "hair_type",
            "continent",
            "country",
            "location",
            "date_of_birth",
            "portfolio_link",
            "instagram_link",
            "rate",
            "skills",
            "approval_status",
            "rejection_reason",
            "is_active",
            "is_available",
            "is_available_on_request",
            "images",
            "uploaded_images",
            "available_dates",
            "available_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "talent_id",
            "approval_status",
            "rejection_reason",
            "is_active",
            "created_at",
            "updated_at",
        ]

    @transaction.atomic
    def create(self, validated_data):
        uploaded_images = validated_data.pop("uploaded_images", [])
        available_dates = validated_data.pop("available_date", [])

        request = self.context.get("request")

        talent = Talent.objects.create(
            agent=request.user,
            **validated_data
        )

        for index, img in enumerate(uploaded_images):
            TalentImage.objects.create(
                talent=talent,
                image=img,
                is_primary=(index == 0)
            )

        TalentAvailableDate.objects.bulk_create([
            TalentAvailableDate(talent=talent, available_date=date)
            for date in available_dates
        ])

        return talent

    def get_available_dates(self, obj):
        return [d.available_date for d in obj.available_dates.all()]

    @transaction.atomic
    def update(self, instance, validated_data):
        uploaded_images = validated_data.pop("uploaded_images", None)
        available_dates = validated_data.pop("available_date", None)

        # update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # reset approval state
        instance.approval_status = "pending"
        instance.rejection_reason = None
        instance.approved_by = None
        instance.approved_at = None
        instance.save()

        if uploaded_images is not None:
            instance.images.all().delete()
            for index, img in enumerate(uploaded_images):
                TalentImage.objects.create(
                    talent=instance,
                    image=img,
                    is_primary=(index == 0)
                )

        if available_dates is not None:
            # delete old
            instance.available_dates.all().delete()

            # create new
            TalentAvailableDate.objects.bulk_create([
                TalentAvailableDate(talent=instance, available_date=date)
                for date in available_dates if date
            ])

        return instance


class TalentListSerializer(serializers.ModelSerializer):
    images = TalentImageSerializer(many=True, read_only=True)
    agent_name = serializers.CharField(source="agent.full_name", read_only=True)

    class Meta:
        model = Talent
        fields = [
            "talent_id",
            "role",
            "character",
            "agent_name",
            "gender",
            "name",
            "height",
            "country",
            "skills",
            "location",
            "portfolio_link",
            "instagram_link",
            "rate",
            "approval_status",
            "images",
            "created_at",
        ]


class TalentApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Talent
        fields = ["approval_status", "rejection_reason"]

    def validate(self, attrs):
        approval_status = attrs.get("approval_status")
        rejection_reason = attrs.get("rejection_reason")

        if approval_status == "rejected" and not rejection_reason:
            raise serializers.ValidationError({
                "rejection_reason": "Rejection reason is required when rejecting a talent."
            })

        return attrs
    



class TalentAvailableDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TalentAvailableDate
        fields = [
            "availability_id",
            "available_date",
            "note",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["availability_id", "created_at"]


class BulkTalentAvailableDateSerializer(serializers.Serializer):
    dates = serializers.ListField(
        child=serializers.DateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"]),
        allow_empty=False
    )
    note = serializers.CharField(required=False, allow_blank=True)

    def validate_dates(self, value):
        unique_dates = list(set(value))
        return sorted(unique_dates)
    


class TalentSerializerDetail(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    agency_name = serializers.SerializerMethodField()
    class Meta:
        model = Talent
        fields = ["talent_id", "name", "role", "gender", "country","agency_name","images"]

    def get_images(self, obj):
        primary_images = obj.images.filter(is_primary=True)
        return TalentImageSerializer(primary_images, many=True).data
    
    def get_agency_name(self, obj):
        if obj.agent and obj.agent.agency_name:
            return obj.agent.agency_name
        return None
    


class ShortListedTalentSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)
    job_description = serializers.CharField(source="job.description", read_only=True)
    class Meta:
        model = ShortListedTalent
        fields = [
            "job_title",
            "job_description",
            "shortlisted_id",
            "talent_id",
            "user_id",
            "job_id",
            "session_id",
            "created_at",
        ]

    



# serializers.py
from rest_framework import serializers
from .models import Job, ShortListedTalent

class ShortlistedTalentSerializer(serializers.ModelSerializer):
    talent_name = serializers.SerializerMethodField()
    talent_email = serializers.SerializerMethodField()

    class Meta:
        model = ShortListedTalent
        fields = [
            'shortlisted_id',
            'talent_id',
            'talent_name',
            'talent_email',
            'user_id',
            'session_id',
            'created_at',
        ]

    def get_talent_name(self, obj):
        if obj.talent:
            return f"{obj.talent.first_name} {obj.talent.last_name}"
        return None

    def get_talent_email(self, obj):
        if obj.talent:
            return obj.talent.email
        return None


########################################################################################################

from jobs.models import JobRole


class TalentImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TalentImage
        fields = [
            'image_id',
            'image',
            'is_primary',
            'uploaded_at',
        ]


# ─── 2. Available Dates ─────────────────────────────────────────────────────────

class TalentAvailableDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TalentAvailableDate
        fields = [
            'availability_id',
            'available_date',
            'is_active',
            'note',
            'created_at',
        ]


# ─── 3. Talent Info (used inside shortlisted) ───────────────────────────────────

class ShortlistedTalentInfoSerializer(serializers.ModelSerializer):
    images = TalentImageSerializer(many=True, read_only=True)
    available_dates = serializers.SerializerMethodField()

    class Meta:
        model = Talent
        fields = [
            'talent_id',
            'name',
            'gender',
            'role',
            'character',
            'height',
            'waist',
            'bust',
            'hips',
            'dress_size',
            'shoe_size',
            'hair_colour',
            'eye_colour',
            'skin_color',
            'hair_type',
            'continent',
            'country',
            'location',
            'skills',
            'portfolio_link',
            'instagram_link',
            'rate',
            'is_available',
            'images',
            'available_dates',
        ]

    def get_available_dates(self, obj):
        return list(
            obj.available_dates.filter(is_active=True).values_list('available_date', flat=True)
        )


# ─── 4. Shortlisted Talent Row ──────────────────────────────────────────────────

class ShortlistedTalentSerializer(serializers.ModelSerializer):
    talent_info = ShortlistedTalentInfoSerializer(source='talent', read_only=True)

    class Meta:
        model = ShortListedTalent
        fields = [
            'shortlisted_id',
            'session_id',
            'created_at',
            'talent_info',
        ]


# ─── 4.5. Job Role (one row per talent assigned to a role on a job) ────────────

class JobRoleSerializer(serializers.ModelSerializer):
    talent_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = JobRole
        fields = [
            'id',
            'job_role',
            'assign_status',
            'talent_id',
        ]


# ─── 5. Job with Shortlisted Talents ────────────────────────────────────────────

class JobWithShortlistedSerializer(serializers.ModelSerializer):
    shortlisted_talents = serializers.SerializerMethodField()
    job_roles = serializers.SerializerMethodField()
    job_photo = serializers.SerializerMethodField()
    created_by_image = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'job_id',
            'job_photo',
            'title',
            'description',
            'casting_roles',
            'location',
            'budget_min',
            'budget_max',
            'job_type',
            'status',
            'applicants_count',
            'shortlisted_count',
            'selftapes_count',
            'ecastings_count',
            'polas_count',
            'created_at',
            'updated_at',
            'shortlisted_talents',
            'job_roles',
            'created_by_image',
            'created_by_name',
        ]

    def _get_creator(self, obj):
        # Job.job_created_by_id is a bare int, not a real FK, so this can't be
        # select_related — cache per creator_id instead, so get_created_by_image and
        # get_created_by_name share one lookup instead of querying twice, and a
        # many=True list of jobs by the same creator only queries once total.
        cache = self.__dict__.setdefault('_creator_cache', {})
        creator_id = obj.job_created_by_id
        if creator_id not in cache:
            cache[creator_id] = User.objects.filter(user_id=creator_id).first()
        return cache[creator_id]

    def get_created_by_image(self, obj):
        creator = self._get_creator(obj)
        if not creator or not creator.profile_pic:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(creator.profile_pic.url) if request else creator.profile_pic.url

    def get_created_by_name(self, obj):
        creator = self._get_creator(obj)
        if not creator:
            return None
        return getattr(creator, 'full_name', None) or getattr(creator, 'email', None)

    def get_job_roles(self, obj):
        # No select_related/prefetch needed — JobRoleSerializer only reads the raw
        # talent_id FK column, already present on the JobRole row itself.
        roles = obj.roles.all()
        return JobRoleSerializer(roles, many=True, context=self.context).data

    def get_shortlisted_talents(self, obj):
        shortlisted = obj.shortlistedtalent_set.all(
        ).select_related('talent').prefetch_related(
            'talent__images',
            'talent__available_dates',
        )
        return ShortlistedTalentSerializer(shortlisted, many=True, context=self.context).data

    def get_job_photo(self, obj):
            if not obj.job_photo:
                return None
            url = obj.job_photo
            request = self.context.get("request")
            if request and (url.startswith('/media/') or url.startswith('media/')):
                if not url.startswith('/'):
                    url = '/' + url
                abs_url = request.build_absolute_uri(url)
                
                # Switch subdomain from api. to ai.
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(abs_url)
                if parsed.hostname and parsed.hostname.startswith('api.'):
                    new_netloc = parsed.netloc.replace('api.', 'ai.', 1)
                    parsed = parsed._replace(netloc=new_netloc)
                    return urlunparse(parsed)
                
                return abs_url
            return url
    
class WebImagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebImages
        fields = ['id', 'iamge1', 'iamge2', 'iamge3', 'iamge4', 'created_at', 'updated_at']

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'name', 'designation', 'image', 'created_at', 'updated_at']
