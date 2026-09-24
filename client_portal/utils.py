import uuid

from django.contrib.auth import get_user_model

from .models import GuestClient

User = get_user_model()


def normalize_email(value):
    return (value or "").strip().lower()


def get_job_owner(job):
    """Resolve the agent who owns a job. Job.job_created_by_id is a bare int, not a real FK."""
    if not job or not job.job_created_by_id:
        return None
    return User.objects.filter(user_id=job.job_created_by_id).first()


def job_belongs_to_agent(job, user):
    if not job or not user or not user.is_authenticated:
        return False
    if getattr(user, "role", None) == "Admin":
        return True
    return str(job.job_created_by_id) == str(user.pk)


def _strip_bearer_prefix(token_value):
    """X-Guest-Token is a raw-token header, not a Bearer-scheme one, but frontend
    code reaches for "Bearer <token>" out of habit (that's the Authorization/JWT
    convention). Accept either so that mismatch doesn't 401 every guest request.
    """
    token = str(token_value or "").strip()
    if token[:7].lower() == "bearer ":
        token = token[7:].strip()
    return token


def resolve_guest(request, job_id):
    """Resolve a GuestClient from the X-Guest-Token header, scoped to job_id.

    Returns None if the header is missing, malformed, unknown, or belongs to a
    different job (never trust the token alone without cross-checking the job).
    """
    token = request.headers.get("X-Guest-Token")
    if not token:
        return None

    return resolve_guest_by_token(token, job_id=job_id)


def resolve_guest_by_token(token_value, job_id=None):
    """Resolve a GuestClient from a raw (optionally "Bearer "-prefixed) token value.

    Used both by the REST header path (with job_id, to cross-check the job) and the
    WebSocket first-message auth path (without job_id — the consumer checks the
    thread's guest_client_id itself).
    """
    try:
        token = uuid.UUID(_strip_bearer_prefix(token_value))
    except (ValueError, TypeError):
        return None

    queryset = GuestClient.objects.filter(token=token)
    if job_id is not None:
        queryset = queryset.filter(job_id=job_id)

    return queryset.first()
