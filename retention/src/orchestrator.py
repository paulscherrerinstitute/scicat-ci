from datetime import datetime, timezone

from scicat import MarkedForDeletionJobsRepository, SciCatAuth
from utils import log


class RetentionOrchestrator:
    """
    Updates the verification time of "markedForDeletion" jobs due for a
    check-in, until their grace period expires.

    Which jobs are due is decided by the database query itself.
    """

    def __init__(self):
        self.scicat_instance = SciCatAuth.from_env()
        self.jobs = MarkedForDeletionJobsRepository()

    def orchestrate(self):
        """Updates every due markedForDeletion job's verification time."""
        log.info("==== Retention check started ====")
        log.info(f"Connecting to scicat on {self.scicat_instance.url}")
        self.scicat_instance.authenticate()
        now = datetime.now(timezone.utc)
        due_jobs = self.jobs.due_jobs(now)
        log.info(f"{len(due_jobs)} job(s) due for a check-in")
        for job in due_jobs:
            try:
                job.advance(now)
            except Exception as e:
                log.error(f"Failed to process job {job.id}: {e}")
        log.info("==== Retention check finished ====")
