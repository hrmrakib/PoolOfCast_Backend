import json
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q

from .models import DraftJob, Job, JobAIResult

logger = logging.getLogger(__name__)


def format_shoot_date_for_display(date_data):
    if not date_data:
        return ""

    dates = []
    try:
        parsed = json.loads(date_data)
    except (ValueError, TypeError):
        parsed = None

    if isinstance(parsed, list):
        dates = [str(d).strip() for d in parsed if str(d).strip()]
    elif parsed:
        dates = [str(parsed).strip()]
    else:
        dates = [p.strip() for p in str(date_data).split(",") if p.strip()]

    if dates:
        return f" for the shoot on {', '.join(dates)}"
    return ""


def resolve_job_and_shoot_date(user_id, job_id=None, session_id=None):
    job = None
    shoot_date_str = ""

    if job_id:
        job = Job.objects.filter(job_id=job_id, job_created_by_id=user_id).first()
        if job:
            ai_result = JobAIResult.objects.filter(job_id=int(job.job_id)).first()
            shoot_date_str = format_shoot_date_for_display(ai_result.shoot_date if ai_result else None)
    elif session_id:
        job = Job.objects.filter(
            session_id=session_id, job_created_by_id=user_id
        ).order_by("-created_at").first()
        draft = DraftJob.objects.filter(session_id=session_id).first()
        if draft:
            shoot_date_str = format_shoot_date_for_display(draft.shoot_date)

    return job, shoot_date_str


def resolve_job_display_name(job, session_id):
    if job:
        return job.title
    if session_id:
        draft = DraftJob.objects.filter(session_id=session_id).first()
        if draft and draft.title:
            return draft.title
    return "a new project"


def build_shortlist_filters(user_id, talent, job, session_id):
    filters = Q(user_id=user_id, talent=talent)
    if job:
        filters &= Q(job=job)
    elif session_id:
        filters &= Q(session_id=session_id, job__isnull=True)
    return filters


def _send_mail_safely(subject, message, recipient_email, context_label):
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send %s email to %s", context_label, recipient_email)


def send_shortlist_email(agent, talent, job_display_name, shoot_date_str):
    subject = f"Congratulations! {talent.name} has been shortlisted for {job_display_name}"
    message = (
        f"Dear {agent.full_name},\n\n"
        f"Congratulations! Your talent, {talent.name}, has been shortlisted for the project "
        f"'{job_display_name}'{shoot_date_str}.\n\n"
        "Please log in to your Pool of Cast portal to review the job specifics and prepare for "
        "any potential next steps.\n\n"
        "Best regards,\nThe Pool of Cast Team"
    )
    _send_mail_safely(subject, message, agent.email, "shortlist")


def send_booking_email(agent, talent, job_display_name, booking_dates_str, role_names):
    subject = f"Booking Confirmation: {talent.name} for {job_display_name}"
    if role_names:
        subject += f" ({', '.join(role_names)})"

    message = (
        f"Dear {agent.full_name},\n\n"
        f"This email serves as confirmation that your talent, {talent.name}, has been booked for "
        f"the project '{job_display_name}'.\n\n"
        f"Role(s): {', '.join(role_names) if role_names else 'Not specified'}\n"
        f"Shoot Date(s): {booking_dates_str}\n\n"
        "We look forward to a successful collaboration.\n\n"
        "Best regards,\nThe Pool of Cast Team"
    )
    _send_mail_safely(subject, message, agent.email, "booking")
