from datetime import datetime, timezone

from scicat import (
    ExpiredDatasetsRepository,
    MarkedForDeletionJobsRepository,
    RevertMarkForDeletionJobsRepository,
    SciCatAuth,
    retention_time_from_env,
    submit_expired_marked_for_deletion,
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


class MarkExpiredOrchestrator:
    """
    Marks for deletion, with deletionCode EXPIRED, the datasets whose archive
    retention time has passed: one "markedForDeletion" job per owner group.

    It only submits the jobs. What follows (flagging the datasets, the grace
    period, notifications, deletion) is the same as for any markedForDeletion
    job, whether submitted from here, the API or the frontend.
    """

    def __init__(self):
        self.scicat_instance = SciCatAuth.from_env()
        self.retention_time = retention_time_from_env("EXPIRED_RETENTION_TIME")
        self.datasets = ExpiredDatasetsRepository()

    def orchestrate(self):
        """Submits markedForDeletion jobs for every expired dataset not marked yet."""
        log.info("==== Mark expired datasets started ====")
        log.info(f"Connecting to scicat on {self.scicat_instance.url}")
        self.scicat_instance.authenticate()
        now = datetime.now(timezone.utc)
        pids_by_group = self.datasets.expired_pids_by_owner_group(now)
        for owner_group, pids in pids_by_group.items():
            try:
                submit_expired_marked_for_deletion(
                    owner_group, pids, self.retention_time
                )
            except Exception as e:
                log.error(f"Failed to mark expired datasets of {owner_group}: {e}")
        log.info(f"{len(pids_by_group)} owner group(s) with expired datasets")
        log.info("==== Mark expired datasets finished ====")
