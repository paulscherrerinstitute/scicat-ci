import json
from os import environ

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from scicat_sdk_py import AuthApi, Configuration, JobsApi

from utils import log

JOB_TYPE = "markedForDeletion"

RESULT_RETENTION_TIME = "retentionTime"
RESULT_LAST_VERIFIED_AT = "lastVerifiedAt"

STATUS_RETENTION_EXPIRED = "retentionExpired"

# retentionTime suffix -> relativedelta keyword, following the same calendar
# (upper) vs clock (lower) case convention as ISO 8601 durations.
_RELATIVEDELTA_KWARG_BY_UNIT = {
    "Y": "years",
    "M": "months",
    "d": "days",
    "h": "hours",
    "m": "minutes",
    "s": "seconds",
}


def _parse_retention(retention_time):
    """Validates e.g. {"value": 3, "unit": "M"} and returns (3, "months")."""
    try:
        amount = retention_time["value"]
        unit = retention_time["unit"]
    except (TypeError, KeyError) as e:
        raise ValueError(
            f"Unrecognized retention time format: {retention_time!r}"
        ) from e
    kwarg = _RELATIVEDELTA_KWARG_BY_UNIT.get(unit)
    if kwarg is None or not isinstance(amount, int) or isinstance(amount, bool):
        raise ValueError(f"Unrecognized retention time format: {retention_time!r}")
    return amount, kwarg


_RETENTION_STEP = {"value": 1, "unit": "M"}
_RETENTION_STEP_DELTA = relativedelta(
    **{_RELATIVEDELTA_KWARG_BY_UNIT[_RETENTION_STEP["unit"]]: _RETENTION_STEP["value"]}
)


class SciCatAuth:
    """
    Handles authentication with the SciCat API.

    Attributes:
        username (str): Username for SciCat.
        password (str): Password for SciCat.
        url (str): SciCat endpoint URL.
    """

    def __init__(self, username, password, url):
        self.username = username
        self.password = password
        self.url = url

    @classmethod
    def from_env(cls):
        """Creates a SciCatAuth instance from environment variables."""
        load_dotenv()
        log.info("Loading scicat env vars")
        return cls(
            environ["SCICAT_USERNAME"],
            environ["SCICAT_PASSWORD"],
            environ["SCICAT_ENDPOINT"],
        )

    def authenticate(self):
        """Authenticates with SciCat and sets the token in the API client."""
        self._set_scicat_token()

    def _get_scicat_token(self):
        """Retrieves the authentication token from SciCat."""
        credentials = {"username": self.username, "password": self.password}
        try:
            response = AuthApi().auth_controller_login_v3(credentials)
            return response.access_token
        except Exception as e:
            log.error("Login to data catalog did not succeed")
            raise e

    def _set_scicat_token(self):
        """Sets the SciCat token in the Swagger client configuration."""
        scicat_config = Configuration(host=self.url)
        Configuration.set_default(scicat_config)
        access_token = self._get_scicat_token()
        log.info("SciCat authentication successful, setting access_token")
        Configuration.get_default().access_token = access_token


class MarkedForDeletionJob:
    """
    Wraps a "markedForDeletion" SciCat job and tracks its retention grace period.
    """

    def __init__(self, job):
        self._job = job

    @property
    def id(self):
        return self._job.id

    @property
    def dataset_pids(self):
        return [dataset.pid for dataset in self._job.dataset_list]

    @property
    def retention_time(self):
        return self._job.job_result_object.get(RESULT_RETENTION_TIME)

    @property
    def retention_amount(self):
        """The grace period's numeric value, e.g. 3 for {"value": 3, "unit": "M"}."""
        return _parse_retention(self.retention_time)[0]

    @property
    def _retention_unit(self):
        return _parse_retention(self.retention_time)[1]

    @property
    def expiry_date(self):
        """The date at which the full retentionTime grace period has elapsed."""
        return self._job.creation_time + relativedelta(
            **{self._retention_unit: self.retention_amount}
        )

    def advance(self, now):
        """Updates the job's verification time and checks whether its grace period has elapsed."""
        patch = {
            "jobResultObject": {
                **self._job.job_result_object,
                RESULT_LAST_VERIFIED_AT: now.isoformat(),
            }
        }
        if now >= self.expiry_date:
            patch["jobStatusMessage"] = STATUS_RETENTION_EXPIRED
            log.info(f"Job {self.id} retention expired, ready for deletion")
        else:
            log.info(f"Job {self.id} verification time updated, not yet expired")
        JobsApi().jobs_controller_update_v3(self.id, patch)


class MarkedForDeletionJobsRepository:
    """Fetches SciCat "markedForDeletion" jobs whose next check-in is due."""

    page_limit = 100
    max_iterations = 1000

    fields = ["id", "datasetList", "jobResultObject", "creationTime"]

    def _due_jobs_filter(self, now):
        # lastVerifiedAt is written by the marking agent at job creation (as
        # well as by this service on every check-in), so a due job is simply
        # one whose last check-in is at least one retention step old.
        return {
            "where": {
                "type": JOB_TYPE,
                "jobStatusMessage": {"neq": STATUS_RETENTION_EXPIRED},
                "datasetList": {"neq": []},
                f"jobResultObject.{RESULT_LAST_VERIFIED_AT}": {
                    "lte": (now - _RETENTION_STEP_DELTA).isoformat()
                },
            },
            "fields": self.fields,
        }

    def _due_jobs_batches(self, now):
        """Yields pages of due jobs, walking `limits.skip` until a page is empty."""
        filter_ = self._due_jobs_filter(now)
        filter_["limits"] = {"skip": 0, "limit": self.page_limit}
        for _ in range(self.max_iterations):
            batch = JobsApi().jobs_controller_find_all_v3(filter=json.dumps(filter_))
            if not batch:
                return
            yield batch
            filter_["limits"]["skip"] += self.page_limit
        raise RuntimeError(
            "Exceeded maximum pages while fetching due markedForDeletion jobs"
        )

    def due_jobs(self, now):
        """Yields markedForDeletion jobs due for a check-in, as MarkedForDeletionJob."""
        log.info("Fetching markedForDeletion jobs due for a check-in")
        for batch in self._due_jobs_batches(now):
            for job in batch:
                yield MarkedForDeletionJob(job)
