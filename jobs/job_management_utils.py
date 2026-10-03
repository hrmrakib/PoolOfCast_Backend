import json
import logging
import re
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail

from .casting_requests_utils import parse_json_field
from .models import JobAIResult

logger = logging.getLogger(__name__)

CURRENCY_STRIP_TOKENS = [",", "$", "£", "€", "R", "USD", "EUR", "ZAR", "GBP"]
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def detect_currency(upper_value):
    if "€" in upper_value or "EUR" in upper_value:
        return "€"
    if "ZAR" in upper_value or upper_value.strip().startswith("R") or "R " in upper_value:
        return "R"
    if "£" in upper_value or "GBP" in upper_value:
        return "£"
    if "$" in upper_value or "USD" in upper_value:
        return "$"
    return "$"


def parse_budget(budget_range):
    upper_value = budget_range.upper()
    currency = detect_currency(upper_value)

    stripped = upper_value
    for token in CURRENCY_STRIP_TOKENS:
        stripped = stripped.replace(token, "")

    numbers = [Decimal(n) for n in NUMBER_RE.findall(stripped)]

    if not numbers:
        return None, None, currency
    if len(numbers) == 1:
        return numbers[0], numbers[0], currency

    first_two = numbers[:2]
    return min(first_two), max(first_two), currency


def _format_number(value):
    value = Decimal(value)
    if value == value.to_integral_value():
        return str(int(value))
    return f"{value:.2f}"


def format_budget(budget_min, budget_max, currency):
    if budget_min is None and budget_max is None:
        return None
    if budget_min == budget_max:
        return f"{_format_number(budget_min)}{currency}"
    return f"{_format_number(budget_min)}-{_format_number(budget_max)}{currency}"


def parse_roles_input(value):
    if value is None:
        return set()
    if isinstance(value, list):
        return {str(v).strip() for v in value if str(v).strip()}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, list):
            return {str(v).strip() for v in parsed if str(v).strip()}
        if isinstance(parsed, str):
            return {parsed.strip()} if parsed.strip() else set()
        return {p.strip() for p in value.split(",") if p.strip()}
    return set()


def build_job_response(job):
    ai_result = JobAIResult.objects.filter(job_id=int(job.job_id)).first()
    shoot_date = None
    if ai_result and ai_result.shoot_date:
        try:
            shoot_date = json.loads(ai_result.shoot_date)
        except (ValueError, TypeError):
            shoot_date = ai_result.shoot_date

    return {
        "job_id": job.job_id,
        "job_created_by_id": job.job_created_by_id,
        "session_id": job.session_id,
        "status": job.status,
        "title": job.title,
        "job_type": job.job_type,
        "description": job.description,
        "location": job.location,
        "casting_roles": parse_json_field(job.casting_roles, []),
        "job_photo": job.job_photo,
        "budget": format_budget(job.budget_min, job.budget_max, job.currency),
        "applicants_count": job.applicants_count,
        "shortlisted_count": job.shortlisted_count,
        "selftapes_count": job.selftapes_count,
        "ecastings_count": job.ecastings_count,
        "polas_count": job.polas_count,
        "shoot_date": shoot_date,
    }


def send_job_update_email(agent, job, change_str):
    subject = f"Update for Job: {job.title}"
    message = (
        f"Dear {agent.full_name},\n\n"
        f"Please note that the details for the job '{job.title}' have been updated.\n\n"
        f"The following fields were changed: {change_str}.\n\n"
        "Please log in to your portal to review the updated job details.\n\n"
        "Best regards,\nThe CastLink AI Team"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[agent.email],
            fail_silently=False,
        )
    except Exception:
        # Email delivery failures shouldn't roll back or fail an already-committed job edit.
        logger.exception("Failed to send job update email to %s for job %s", agent.email, job.job_id)
