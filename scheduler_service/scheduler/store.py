import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import Client, create_client

from .config import SchedulerConfig
from .models import JobStatus, RecurringJob, ScheduledJob

logger = logging.getLogger(__name__)


class SchedulerStore:
    def __init__(self, config: SchedulerConfig, client: Optional[Client] = None):
        self.config = config
        if client is not None:
            self._client = client
        else:
            self._client = create_client(
                config.supabase_url, config.supabase_service_role_key
            )
        self._jobs_table = config.jobs_table
        self._recurring_table = config.recurring_jobs_table

    def enqueue(self, job: ScheduledJob) -> ScheduledJob:
        try:
            result = self._client.table(self._jobs_table).insert(job.to_row()).execute()
            row = result.data[0]
            job.id = row["id"]
            logger.info("job_enqueued", job_id=job.id, job_type=job.job_type)
            return job
        except Exception as e:
            logger.error("enqueue_failed", job_type=job.job_type, error=str(e))
            raise

    def claim_due_jobs(self, limit: int = 20) -> list[ScheduledJob]:
        now = datetime.now(timezone.utc)
        claim_stale_cutoff = now - timedelta(minutes=self.config.job_claim_timeout_minutes)

        try:
            result = self._client.rpc(
                "claim_jobs",
                {
                    "p_table": self._jobs_table,
                    "p_limit": limit,
                    "p_now": now.isoformat(),
                    "p_stale_cutoff": claim_stale_cutoff.isoformat(),
                },
            ).execute()
            
            jobs = [ScheduledJob.from_row(row) for row in result.data]
            if jobs:
                logger.debug("jobs_claimed", count=len(jobs))
            return jobs
        except Exception as e:
            logger.error("claim_jobs_failed", error=str(e))
            raise

    def mark_succeeded(self, job: ScheduledJob) -> None:
        job.status = JobStatus.SUCCEEDED
        job.completed_at = datetime.now(timezone.utc)
        try:
            self._update_job(job)
            logger.info("job_succeeded", job_id=job.id)
        except Exception as e:
            logger.error("mark_succeeded_failed", job_id=job.id, error=str(e))
            raise

    def mark_failed(self, job: ScheduledJob, error: str, next_run_at: Optional[datetime]) -> None:
        job.attempt_count += 1
        job.last_error = error[:2000]
        job.claimed_at = None

        if next_run_at is not None and job.attempt_count < job.max_retries:
            job.status = JobStatus.PENDING
            job.run_at = next_run_at
            logger.info("job_failed_retrying", job_id=job.id, next_run=next_run_at)
        else:
            job.status = JobStatus.DEAD_LETTERED
            logger.warning("job_dead_lettered", job_id=job.id, error=error)

        try:
            self._update_job(job)
        except Exception as e:
            logger.error("mark_failed_update_failed", job_id=job.id, error=str(e))
            raise

    def _update_job(self, job: ScheduledJob) -> None:
        self._client.table(self._jobs_table).update(job.to_row()).eq("id", job.id).execute()

    def register_recurring(self, recurring: RecurringJob) -> RecurringJob:
        try:
            result = (
                self._client.table(self._recurring_table)
                .upsert(recurring.to_row(), on_conflict="job_type")
                .execute()
            )
            row = result.data[0]
            recurring.id = row["id"]
            logger.info("recurring_job_registered", job_type=recurring.job_type)
            return recurring
        except Exception as e:
            logger.error("register_recurring_failed", job_type=recurring.job_type, error=str(e))
            raise

    def advance_recurring(self, recurring: RecurringJob) -> None:
        now = datetime.now(timezone.utc)
        recurring.last_run_at = now
        recurring.next_run_at = now + timedelta(seconds=recurring.interval_seconds)
        try:
            self._client.table(self._recurring_table).update(
                recurring.to_row()
            ).eq("id", recurring.id).execute()
        except Exception as e:
            logger.error("advance_recurring_failed", job_id=recurring.id, error=str(e))
            raise
