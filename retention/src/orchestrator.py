from datetime import datetime, timezone
from os import environ

from scicat import MarkedForDeletionJobsRepository, SciCatAuth
from utils import log


class RetentionOrchestrator:
    """
    Notifies the owner groups of "markedForDeletion" jobs due for a check-in
    and records the check-in, until their grace period expires.

    Which jobs are due is decided by the database query itself.
    """

    def __init__(self):
        self.scicat_instance = SciCatAuth.from_env()
        self.contact_emails = self._contact_emails_from_env()
        self.jobs = MarkedForDeletionJobsRepository()

    @staticmethod
    def _contact_emails_from_env():
        """Recipients of every notification, from a comma-separated env var."""
        contact_emails = [
            email.strip()
            for email in environ["NOTIFICATION_CONTACT_EMAILS"].split(",")
            if email.strip()
        ]
        if not contact_emails:
            raise ValueError("NOTIFICATION_CONTACT_EMAILS is empty")
        return contact_emails

    def orchestrate(self):
        """Updates every due markedForDeletion job's verification time."""
        log.info("==== Retention check started ====")
        log.info(f"Connecting to scicat on {self.scicat_instance.url}")
        self.scicat_instance.authenticate()
        now = datetime.now(timezone.utc)
        processed = 0
        for job in self.jobs.due_jobs(now):
            processed += 1
            try:
                job.advance(now, self.contact_emails)
            except Exception as e:
                log.error(f"Failed to process job {job.id}: {e}")
        log.info(f"{processed} job(s) due for a check-in")
        log.info("==== Retention check finished ====")
