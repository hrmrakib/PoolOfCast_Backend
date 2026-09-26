import json
from .models import Job, JobAIResult

def get_jobs_for_agent(agent_id: int):
    ai_results = JobAIResult.objects.exclude(suggested_talents__isnull=True)
    agent_id = str(agent_id).strip()

    matched_job_ids = set()
    for result in ai_results:
        raw_talents = result.suggested_talents
        if not raw_talents:
            continue

        try:
            if isinstance(raw_talents, str):
                talents = json.loads(raw_talents)
            else:
                talents = raw_talents

            if isinstance(talents, dict):
                talents = [talents]
            if not isinstance(talents, list):
                continue

            has_agent_talent = any(
                isinstance(t, dict) and str(t.get("agent_id", "")).strip() == agent_id
                for t in talents
            )
            if has_agent_talent and result.job_id is not None:
                matched_job_ids.add(str(result.job_id))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    return Job.objects.filter(job_id__in=list(matched_job_ids))
