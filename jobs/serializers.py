from rest_framework import serializers
from .models import *
import json
class JobSerializer(serializers.ModelSerializer):
    ai_result = serializers.SerializerMethodField()
    job_photo = serializers.SerializerMethodField()
    casting_roles = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "job_id",
            "session_id",
            "title",
            "description",
            "casting_roles",
            "location",
            "budget_min",
            "budget_max",
            "currency",
            "job_type",
            "applicants_count",
            "shortlisted_count",
            "selftapes_count",
            "ecastings_count",
            "polas_count",
            "ai_result",
            "status",
            "job_photo",
            "created_at",
            "updated_at",
        ]

    def get_casting_roles(self, obj):
        return self._parse_json(obj.casting_roles)

    def get_ai_result(self, obj):
        request = self.context.get("request")
        ai_map = self.context.get("ai_map", {})
        # print(ai_map)

        ai = ai_map.get(str(obj.job_id))
        
        if not ai:
            return None

        suggested = self._parse_json(ai.suggested_talents)
        selftapes = self._parse_json(ai.requested_selftapes)
        ecastings = self._parse_json(ai.requested_ecastings)
        polas = self._parse_json(ai.requested_polas)

        def _fix_talent_images(talent_list):
            if not talent_list:
                return
            for t in talent_list:
                if isinstance(t, dict) and 'images' in t and isinstance(t['images'], list):
                    new_images = []
                    for img in t['images']:
                        if isinstance(img, str) and img.startswith('http'):
                            from urllib.parse import urlparse, urlunparse
                            parsed = urlparse(img)
                            if parsed.hostname and parsed.hostname.startswith('ai.'):
                                parsed = parsed._replace(netloc=parsed.netloc.replace('ai.', 'api.', 1))
                                img = urlunparse(parsed)
                        new_images.append(img)
                    t['images'] = new_images

        _fix_talent_images(suggested)
        _fix_talent_images(selftapes)
        _fix_talent_images(ecastings)
        _fix_talent_images(polas)
       
        shoot_date = self._parse_json(ai.shoot_date)
        if isinstance(shoot_date, dict):
            if "available_dates" in shoot_date:
                shoot_date = shoot_date["available_dates"]
            elif "shoot_date" in shoot_date:
                shoot_date = shoot_date["shoot_date"]
            elif "shot_date" in shoot_date:
                shoot_date = shoot_date["shot_date"]
            else:
                for v in shoot_date.values():
                    if isinstance(v, list):
                        shoot_date = v
                        break

        # Agent filtering
        if request and request.user.role == "Agent":
            agent_id = request.user.user_id

            suggested = [t for t in suggested if t.get("agent_id") == agent_id]
            selftapes = [t for t in selftapes if t.get("agent_id") == agent_id]
            ecastings = [t for t in ecastings if t.get("agent_id") == agent_id]
            polas = [t for t in polas if t.get("agent_id") == agent_id]

            # If no data for this agent → block
            if not (suggested or selftapes or ecastings or polas):
                return {"error": "No data available for this agent"}

        return {
            "suggested_talents": suggested,
            "requested_selftapes": selftapes,
            "requested_ecastings": ecastings,
            "requested_polas": polas,
            "shot_date": shoot_date,
        }

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


    def _make_urls_absolute(self, data):
        request = self.context.get("request")
        if not request:
            return data

        def convert(obj):
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            elif isinstance(obj, str) and (obj.startswith('/media/') or obj.startswith('media/')):
                url = obj
                if not url.startswith('/'):
                    url = '/' + url
                abs_url = request.build_absolute_uri(url)
                if '/media/polas/' in url:
                    from urllib.parse import urlparse, urlunparse
                    parsed = urlparse(abs_url)
                    if parsed.hostname and parsed.hostname.startswith('api.'):
                        parsed = parsed._replace(netloc=parsed.netloc.replace('api.', 'ai.', 1))
                        return urlunparse(parsed)
                return abs_url
            return obj

        return convert(data)

    def _parse_json(self, value):
        parsed = []
        if isinstance(value, list):
            parsed = value
        elif isinstance(value, str):
            import json
            try:
                parsed = json.loads(value)
            except Exception:
                import ast
                try:
                    parsed = ast.literal_eval(value)
                except Exception:
                    # Fallback for "[date1, date2]" format if not valid JSON or literal
                    val = value.strip()
                    if val.startswith('[') and val.endswith(']'):
                        items = val[1:-1].split(',')
                        parsed = [item.strip().strip("'").strip('"') for item in items if item.strip()]
        return self._make_urls_absolute(parsed)


class DraftJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = DraftJob
        fields = '__all__'


class JobAIResultSerializer(serializers.ModelSerializer):
    suggested_talents = serializers.SerializerMethodField()
    requested_selftapes = serializers.SerializerMethodField()
    requested_ecastings = serializers.SerializerMethodField()
    requested_polas = serializers.SerializerMethodField()
    shot_date = serializers.SerializerMethodField(method_name="get_shoot_date")

    class Meta:
        model = JobAIResult
        fields = [
            "result_id", "job_id", "suggested_talents", "requested_selftapes",
            "requested_ecastings", "requested_polas", "shot_date",
            "created_at", "updated_at"
        ]

    def _make_urls_absolute(self, data):
        request = self.context.get("request")
        if not request:
            return data

        def convert(obj):
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            elif isinstance(obj, str) and (obj.startswith('/media/') or obj.startswith('media/')):
                url = obj
                if not url.startswith('/'):
                    url = '/' + url
                abs_url = request.build_absolute_uri(url)
                if '/media/polas/' in url:
                    from urllib.parse import urlparse, urlunparse
                    parsed = urlparse(abs_url)
                    if parsed.hostname and parsed.hostname.startswith('api.'):
                        parsed = parsed._replace(netloc=parsed.netloc.replace('api.', 'ai.', 1))
                        return urlunparse(parsed)
                return abs_url
            return obj

        return convert(data)

    def _parse_json(self, value):
        parsed = []
        if isinstance(value, list):
            parsed = value
        elif isinstance(value, str):
            import json
            try:
                parsed = json.loads(value)
            except Exception:
                import ast
                try:
                    parsed = ast.literal_eval(value)
                except Exception:
                    val = value.strip()
                    if val.startswith('[') and val.endswith(']'):
                        items = val[1:-1].split(',')
                        parsed = [item.strip().strip("'").strip('"') for item in items if item.strip()]
        return self._make_urls_absolute(parsed)

    def get_suggested_talents(self, obj):
        return self._parse_json(obj.suggested_talents)

    def get_requested_selftapes(self, obj):
        return self._parse_json(obj.requested_selftapes)

    def get_requested_ecastings(self, obj):
        return self._parse_json(obj.requested_ecastings)

    def get_requested_polas(self, obj):
        return self._parse_json(obj.requested_polas)

    def get_shoot_date(self, obj):
        shoot_date = self._parse_json(obj.shoot_date)
        if isinstance(shoot_date, dict):
            if "available_dates" in shoot_date:
                shoot_date = shoot_date["available_dates"]
            elif "shoot_date" in shoot_date:
                shoot_date = shoot_date["shoot_date"]
            elif "shot_date" in shoot_date:
                shoot_date = shoot_date["shot_date"]
            else:
                for v in shoot_date.values():
                    if isinstance(v, list):
                        shoot_date = v
                        break
        return shoot_date






# model serialzer for meeting link save and get

from rest_framework import serializers
from .models import Meetings, MeetingRecord


class MeetingsSerializer(serializers.ModelSerializer):
    records = serializers.ListField(
        child=serializers.URLField(),
        write_only=True,
        required=False
    )
    meeting_records = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Meetings
        fields = ["id", "job", "title", "code", "records", "meeting_records"]

    def get_meeting_records(self, obj):
        return [r.meeting_record for r in obj.records.all() if r.meeting_record]

    def create(self, validated_data):
        records = validated_data.pop("records", [])
        meeting = Meetings.objects.create(**validated_data)
        if records:
            record_objs = [MeetingRecord.objects.create(meeting_record=url) for url in records]
            meeting.records.set(record_objs)
        return meeting

    def update(self, instance, validated_data):
        records = validated_data.pop("records", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if records is not None:
            instance.records.clear()
            record_objs = [MeetingRecord.objects.create(meeting_record=url) for url in records]
            instance.records.set(record_objs)
        return instance
