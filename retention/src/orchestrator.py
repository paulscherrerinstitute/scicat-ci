from datetime import datetime, timezone

from scicat import (
    MarkedForDeletionJobsRepository,
    RevertMarkForDeletionJobsRepository,
    SciCatAuth,
)
from utils import log


class RetentionOrchestrator:
    """
    Notifies the owner groups of "markedForDeletion" jobs due for a check-in
    and records the check-in, until their grace period expires. Then notifies
    the owner groups of "revertMarkForDeletion" jobs, once per job.

    Which jobs are due is decided by the database query itself.
    """

    def __init__(self):
        self.scicat_instance = SciCatAuth.from_env()
        self.jobs = MarkedForDeletionJobsRepository()
        self.reverts = RevertMarkForDeletionJobsRepository()

    def orchestrate(self):
        """Checks in every due markedForDeletion job, then notifies every new revertMarkForDeletion job."""
        log.info("==== Retention check started ====")
        log.info(f"Connecting to scicat on {self.scicat_instance.url}")
        self.scicat_instance.authenticate()
        now = datetime.now(timezone.utc)
        # Each step is isolated: a failure in one does not prevent the other
        for step in (self._check_in_marked_jobs, self._notify_reverts):
            try:
                step(now)
            except Exception as e:
                log.error(f"Failed {step.__name__}: {e}")
        log.info("==== Retention check finished ====")

    def _check_in_marked_jobs(self, now):
        processed = 0
        for job in self.jobs.due_jobs(now):
            processed += 1
            try:
                job.advance(now)
            except Exception as e:
                log.error(f"Failed to process job {job.id}: {e}")
        log.info(f"{processed} job(s) due for a check-in")

    def _notify_reverts(self, now):
        processed = 0
        for job in self.reverts.unnotified_jobs():
            processed += 1
            try:
                job.notify(now)
            except Exception as e:
                log.error(f"Failed to notify revert job {job.id}: {e}")
        log.info(f"{processed} revert job(s) notified")
