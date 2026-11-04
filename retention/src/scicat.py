import json
from collections import defaultdict
from os import environ

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from scicat_sdk_py import AuthApi, Configuration, DatasetsV4Api, JobsApi

from utils import log

JOB_TYPE = "markedForDeletion"
NOTIFICATION_JOB_TYPE = "notification"

RESULT_RETENTION_TIME = "retentionTime"
RESULT_LAST_VERIFIED_AT = "lastVerifiedAt"
RESULT_VERIFIED_AT = "verifiedAt"

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

DATASETS_PAGE_LIMIT = 100
DATASETS_MAX_ITERATIONS = 1000


def _paginate(find_all, filter_, page_limit, max_iterations, description):
    """Yields pages from `find_all`, walking `limits.skip` until a page is empty."""
    filter_ = {**filter_, "limits": {"skip": 0, "limit": page_limit}}
    for _ in range(max_iterations):
        batch = find_all(filter=json.dumps(filter_))
        if not batch:
            return
        yield batch
        filter_["limits"]["skip"] += page_limit
    raise RuntimeError(f"Exceeded maximum pages while fetching {description}")


def _pids_by_owner_group(pids):
    """Returns {ownerGroup: [pid, ...]} for the given dataset pids."""
    batches = _paginate(
        DatasetsV4Api().datasets_v4_controller_find_all_v4,
        {"where": {"pid": {"$in": pids}}, "fields": ["pid", "ownerGroup"]},
        DATASETS_PAGE_LIMIT,
        DATASETS_MAX_ITERATIONS,
        "datasets",
    )
    by_group = defaultdict(list)
    for batch in batches:
        for dataset in batch:
            by_group[dataset.owner_group].append(dataset.pid)
    missing = set(pids) - {pid for group in by_group.values() for pid in group}
    if missing:
        log.warning(f"Datasets not found, not notified: {sorted(missing)}")
    return dict(by_group)


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

    Every check-in notifies the datasets' owner groups through one
    "notification" job per group, then records the check-in on this job.
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

    def _notify(self, expired):
        """Submits one notification job per owner group of the job's datasets."""
        for owner_group, pids in _pids_by_owner_group(self.dataset_pids).items():
            JobsApi().jobs_controller_create_v3(
                {
                    "type": NOTIFICATION_JOB_TYPE,
                    "datasetList": [{"pid": pid, "files": []} for pid in pids],
                    "jobParams": {
                        "ownerGroup": owner_group,
                        "markedForDeletionJobId": self.id,
                        "expiryDate": self.expiry_date.isoformat(),
                        "expired": expired,
                    },
                }
            )
            log.info(
                f"Job {self.id} notified {owner_group} about {len(pids)} dataset(s)"
            )

    def advance(self, now):
        """Notifies the owner groups, then records the check-in and whether the grace period has elapsed."""
        expired = now >= self.expiry_date
        # Notify first: if it fails, the check-in is not recorded and the job
        # stays due for the next run.
        self._notify(expired)
        now_iso = now.isoformat()
        job_result_object = self._job.job_result_object
        patch = {
            "jobResultObject": {
                **job_result_object,
                RESULT_LAST_VERIFIED_AT: now_iso,
                RESULT_VERIFIED_AT: [
                    *job_result_object.get(RESULT_VERIFIED_AT, []),
                    now_iso,
                ],
            }
        }
        if expired:
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
        # A job is due when this service never checked it in (no verifiedAt
        # list yet, i.e. right after marking) or when its last check-in is at
        # least one retention step old. A null match also covers missing fields.
        return {
            "where": {
                "type": JOB_TYPE,
                "jobStatusMessage": {"neq": STATUS_RETENTION_EXPIRED},
                "datasetList": {"neq": []},
                "or": [
                    {f"jobResultObject.{RESULT_VERIFIED_AT}": None},
                    {
                        f"jobResultObject.{RESULT_LAST_VERIFIED_AT}": {
                            "lte": (now - _RETENTION_STEP_DELTA).isoformat()
                        }
                    },
                ],
            },
            "fields": self.fields,
        }

    def due_jobs(self, now):
        """Yields markedForDeletion jobs due for a check-in, as MarkedForDeletionJob."""
        log.info("Fetching markedForDeletion jobs due for a check-in")
        batches = _paginate(
            JobsApi().jobs_controller_find_all_v3,
            self._due_jobs_filter(now),
            self.page_limit,
            self.max_iterations,
            "due markedForDeletion jobs",
        )
        for batch in batches:
            for job in batch:
                yield MarkedForDeletionJob(job)
