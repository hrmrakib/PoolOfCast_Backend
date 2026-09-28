import json
import os
import uuid

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import connection

from .models import Job, JobAIResult, Notifications

User = get_user_model()


def parse_json_field(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


def resolve_owned_job(user_id, job_id=None, session_id=None):
    job = None
    if job_id:
        job = Job.objects.filter(job_id=job_id, job_created_by_id=user_id).first()
    if not job and session_id:
        job = Job.objects.filter(
            session_id=session_id, job_created_by_id=user_id
        ).order_by("-created_at").first()
    return job


def resolve_job_for_upload(user_id, job_id=None, session_id=None):
    job = None
    if job_id:
        job = Job.objects.filter(job_id=job_id).first()
    if not job and session_id:
        job = Job.objects.filter(
            session_id=session_id, job_created_by_id=user_id
        ).order_by("-created_at").first()
    return job


def get_or_create_ai_result(job_id):
    ai_result = JobAIResult.objects.filter(job_id=job_id).first()
    if ai_result:
        return ai_result
    with connection.cursor() as cursor:
        # jobs_ai_results.session_id is NOT NULL at the DB level but isn't modeled in
        # Django (FastAPI-owned column outside JobAIResult's field list) and carries no
        # FK/uniqueness constraint, so a fresh, non-colliding integer satisfies it.
        cursor.execute(
            "INSERT INTO jobs_ai_results (job_id, session_id, created_at, updated_at) "
            "VALUES (%s, (SELECT COALESCE(MAX(session_id), 0) + 1 FROM jobs_ai_results), NOW(), NOW()) "
            "RETURNING result_id",
            [job_id],
        )
        result_id = cursor.fetchone()[0]
    return JobAIResult.objects.get(result_id=result_id)


def create_notification(receiver_id, sender_id, event):
    if not receiver_id:
        return
    receiver = User.objects.filter(user_id=receiver_id).first()
    if not receiver:
        return
    sender = User.objects.filter(user_id=sender_id).first() if sender_id else None
    Notifications.objects.create(receiver=receiver, sender=sender, event=event)


def build_talent_snapshot(talent, job_id, request, include_status_tapes=True):
    images = []
    for img in talent.images.order_by("image_id"):
        if not img.image:
            continue
        url = img.image.url
        if not url.startswith("http"):
            url = request.build_absolute_uri(url)
        images.append(url)

    available_dates = [
        d.available_date.isoformat()
        for d in talent.available_dates.filter(is_active=True).order_by("available_date")
    ]

    snapshot = {
        "talent_id": talent.talent_id,
        "job_id": job_id,
        "name": talent.name,
        "role": talent.role,
        "gender": talent.gender,
        "location": talent.location,
        "country": talent.country,
        "continent": talent.continent,
        "is_active": talent.is_active,
        "approval_status": talent.approval_status,
        "is_available": talent.is_available,
        "is_available_on_request": talent.is_available_on_request,
        "agent_id": talent.agent_id,
        "agent_name": (talent.agent.full_name if talent.agent_id and talent.agent.full_name else "Unknown"),
        "images": images,
        "eye_color": talent.eye_colour,
        "hair_type": talent.hair_type,
        "hair_color": talent.hair_colour,
        "skin_color": talent.skin_color,
        "height": talent.height,
        "bust": talent.bust,
        "waist": talent.waist,
        "hips": talent.hips,
        "shoe_size": talent.shoe_size,
        "dress_size": talent.dress_size,
        "available_dates": available_dates,
    }
    if include_status_tapes:
        snapshot["status"] = "requested"
        snapshot["tapes"] = []
    return snapshot


def normalize_url_list(raw_values):
    urls = []
    if not raw_values:
        return urls
    if isinstance(raw_values, str):
        raw_values = [raw_values]

    for raw in raw_values:
        if raw is None:
            continue
        raw = str(raw).strip()
        if not raw:
            continue

        parsed = None
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            parsed = None

        if isinstance(parsed, list):
            urls.extend(str(u).strip() for u in parsed if str(u).strip())
        elif "," in raw:
            urls.extend(u.strip() for u in raw.split(",") if u.strip())
        else:
            urls.append(raw)

    seen = set()
    result = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


def get_multi_values(request, *keys):
    values = []
    for key in keys:
        try:
            values.extend(request.data.getlist(key))
        except AttributeError:
            value = request.data.get(key)
            if value:
                values.append(value)
    return values


def save_uploaded_file(uploaded_file, subfolder, allowed_exts, content_type_prefix):
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    content_type = uploaded_file.content_type or ""
    if ext not in allowed_exts or not content_type.startswith(content_type_prefix):
        return None, uploaded_file.name

    filename = f"{uuid.uuid4()}{ext}"
    saved_path = default_storage.save(f"{subfolder}/{filename}", uploaded_file)
    return saved_path, None
