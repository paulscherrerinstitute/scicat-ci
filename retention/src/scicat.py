import json
from collections import defaultdict
from os import environ

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from scicat_sdk_py import AuthApi, Configuration, DatasetsApi, DatasetsV4Api, JobsApi

from utils import log

JOB_TYPE_MARKED_FOR_DELETION = "markedForDeletion"
JOB_TYPE_NOTIFICATION = "notification"
JOB_TYPE_DELETE = "delete"
JOB_TYPE_REVERT_MARK_FOR_DELETION = "revertMarkForDeletion"
ARCHIVE_STATUS_MARKED_FOR_DELETION = "markedForDeletion"

PARAM_DELETION_CODE = "deletionCode"
DELETION_CODE_EXPIRED = "EXPIRED"

RESULT_RETENTION_TIME = "retentionTime"
RESULT_LAST_VERIFIED_AT = "lastVerifiedAt"
RESULT_VERIFIED_AT = "verifiedAt"
RESULT_NOTIFIED_AT = "notifiedAt"

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

# Maximum number of datasets in a single markedForDeletion job
MARK_MAX_DATASETS_PER_JOB = 1000

# The SDK's v3 dataset model rejects responses missing any of its required
# fields, so a v3 projection must keep all of them.
_DATASET_V3_FIELDS = [
    "pid",
    "ownerGroup",
    "owner",
    "contactEmail",
    "sourceFolder",
    "creationTime",
    "type",
    "createdBy",
    "updatedBy",
    "createdAt",
    "updatedAt",
]


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


def _submit_notifications(job_id, pids, job_params):
    """Submits one notification job per owner group of the given datasets."""
    for owner_group, group_pids in _pids_by_owner_group(pids).items():
        JobsApi().jobs_controller_create_v3(
            {
                "type": JOB_TYPE_NOTIFICATION,
                "datasetList": [{"pid": pid, "files": []} for pid in group_pids],
                "jobParams": {
                    "ownerGroup": owner_group,
                    **job_params,
                },
            }
        )
        log.info(
            f"Job {job_id} notified {owner_group} about {len(group_pids)} dataset(s)"
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
    def deletion_code(self):
        """Reason of the deletion, e.g. EXPIRED. Required on creation by the job config."""
        return self._job.job_params[PARAM_DELETION_CODE]

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
        _submit_notifications(
            self.id,
            self.dataset_pids,
            {
                "markedForDeletionJobId": self.id,
                "expiryDate": self.expiry_date.isoformat(),
                "expired": expired,
                PARAM_DELETION_CODE: self.deletion_code,
            },
        )

    def _still_marked_pids(self):
        """Returns the job's dataset pids whose archiveStatusMessage is still markedForDeletion."""
        batches = _paginate(
            DatasetsV4Api().datasets_v4_controller_find_all_v4,
            {
                "where": {
                    "pid": {"$in": self.dataset_pids},
                    "datasetlifecycle.archiveStatusMessage": ARCHIVE_STATUS_MARKED_FOR_DELETION,
                },
                "fields": ["pid"],
            },
            DATASETS_PAGE_LIMIT,
            DATASETS_MAX_ITERATIONS,
            "datasets still marked for deletion",
        )
        return [dataset.pid for batch in batches for dataset in batch]

    def _submit_delete_job(self):
        """Submits a "delete" job for the datasets still marked for deletion, if any."""
        pids = self._still_marked_pids()
        if not pids:
            log.info(
                f"Job {self.id} expired with no datasets still marked, nothing to delete"
            )
            return
        JobsApi().jobs_controller_create_v3(
            {
                "type": JOB_TYPE_DELETE,
                "datasetList": [{"pid": pid, "files": []} for pid in pids],
                "jobParams": {PARAM_DELETION_CODE: self.deletion_code},
            }
        )
        log.info(
            f"Job {self.id} expired, submitted delete job for {len(pids)} dataset(s)"
        )

    def advance(self, now):
        """Notifies the owner groups, then records the check-in and whether the grace period has elapsed."""
        expired = now >= self.expiry_date
        # Notify (and submit the deletion) first: if it fails, the check-in is
        # not recorded and the job stays due for the next run.
        self._notify(expired)
        if expired:
            self._submit_delete_job()
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

    # jobParams.deletionCode rather than jobParams: datasetList maps to
    # jobParams.datasetList and projecting a path with its parent fails.
    fields = [
        "id",
        "datasetList",
        f"jobParams.{PARAM_DELETION_CODE}",
        "jobResultObject",
        "creationTime",
    ]

    def _due_jobs_filter(self, now):
        # A job is due when this service never checked it in (no verifiedAt
        # list yet, i.e. right after marking) or when its last check-in is at
        # least one retention step old. A null match also covers missing fields.
        return {
            "where": {
                "type": JOB_TYPE_MARKED_FOR_DELETION,
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


class RevertMarkForDeletionJob:
    """
    Wraps a "revertMarkForDeletion" SciCat job, whose datasets are no longer
    to be deleted. Its owner groups are notified once, then the job records it.
    """

    def __init__(self, job):
        self._job = job

    @property
    def id(self):
        return self._job.id

    @property
    def dataset_pids(self):
        return [dataset.pid for dataset in self._job.dataset_list]

    def notify(self, now):
        """Notifies the owner groups, then records the notification on the job."""
        # Notify first: if it fails, the notification is not recorded and the
        # job is picked up again on the next run.
        _submit_notifications(
            self.id,
            self.dataset_pids,
            {"revertMarkForDeletionJobId": self.id, "reverted": True},
        )
        patch = {
            "jobResultObject": {
                **(self._job.job_result_object or {}),
                RESULT_NOTIFIED_AT: now.isoformat(),
            }
        }
        JobsApi().jobs_controller_update_v3(self.id, patch)
        log.info(f"Job {self.id} reverted mark for deletion notified")


class RevertMarkForDeletionJobsRepository:
    """Fetches SciCat "revertMarkForDeletion" jobs whose owner groups were not notified yet."""

    page_limit = 100
    max_iterations = 1000

    fields = ["id", "datasetList", "jobResultObject"]

    def _unnotified_jobs_filter(self):
        # A null match also covers jobs without notifiedAt
        return {
            "where": {
                "type": JOB_TYPE_REVERT_MARK_FOR_DELETION,
                "datasetList": {"neq": []},
                f"jobResultObject.{RESULT_NOTIFIED_AT}": None,
            },
            "fields": self.fields,
        }

    def unnotified_jobs(self):
        """Yields revertMarkForDeletion jobs not notified yet, as RevertMarkForDeletionJob."""
        log.info("Fetching revertMarkForDeletion jobs not notified yet")
        batches = _paginate(
            JobsApi().jobs_controller_find_all_v3,
            self._unnotified_jobs_filter(),
            self.page_limit,
            self.max_iterations,
            "revertMarkForDeletion jobs not notified yet",
        )
        for batch in batches:
            for job in batch:
                yield RevertMarkForDeletionJob(job)


class ExpiredDatasetsRepository:
    """Fetches datasets whose archiveRetentionTime has passed and are not marked for deletion yet."""

    page_limit = 100
    max_iterations = 1000

    def _expired_filter(self, now):
        # v3 rather than v4: only the v3 endpoint converts ISO strings to
        # dates, so archiveRetentionTime can be compared. Published datasets
        # cannot be marked for deletion.
        return {
            "where": {
                "isPublished": False,
                "datasetlifecycle.archiveRetentionTime": {"lte": now.isoformat()},
                "datasetlifecycle.archiveStatusMessage": {
                    "nin": [ARCHIVE_STATUS_MARKED_FOR_DELETION]
                },
            },
            "fields": _DATASET_V3_FIELDS,
        }

    def expired_pids_by_owner_group(self, now):
        """Returns {ownerGroup: [pid, ...]} of the datasets expired at `now`."""
        log.info("Fetching datasets whose archive retention time has passed")
        batches = _paginate(
            DatasetsApi().datasets_controller_find_all_v3,
            self._expired_filter(now),
            self.page_limit,
            self.max_iterations,
            "expired datasets",
        )
        # Collect every page before any job is created: marking changes the
        # datasets' archiveStatusMessage, which would shift later pages.
        by_group = defaultdict(list)
        for batch in batches:
            for dataset in batch:
                by_group[dataset.owner_group].append(dataset.pid)
        return dict(by_group)


def submit_expired_marked_for_deletion(owner_group, pids):
    """Submits markedForDeletion jobs with deletionCode EXPIRED, in chunks of MARK_MAX_DATASETS_PER_JOB."""
    for start in range(0, len(pids), MARK_MAX_DATASETS_PER_JOB):
        chunk = pids[start : start + MARK_MAX_DATASETS_PER_JOB]
        JobsApi().jobs_controller_create_v3(
            {
                "type": JOB_TYPE_MARKED_FOR_DELETION,
                "datasetList": [{"pid": pid, "files": []} for pid in chunk],
                "jobParams": {
                    "ownerGroup": owner_group,
                    PARAM_DELETION_CODE: DELETION_CODE_EXPIRED,
                },
            }
        )
        log.info(
            f"Marked {len(chunk)} expired dataset(s) of {owner_group} for deletion"
        )
