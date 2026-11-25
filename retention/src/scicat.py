import json
import re
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
# Grace period, e.g. "3M", set by the client creating the job and restricted
# by the job config
PARAM_RETENTION_TIME = "retentionTime"

# When this service last processed a job: every check-in of a
# markedForDeletion job, the only notification of a revertMarkForDeletion one.
# The job config emails the submitter only before it is set.
RESULT_LAST_VERIFIED_AT = "lastVerifiedAt"
RESULT_VERIFIED_AT = "verifiedAt"
# When and why this service stopped following a markedForDeletion job, which
# is then never due again
RESULT_CLOSED_AT = "closedAt"
RESULT_CLOSED_REASON = "closedReason"
CLOSED_REASON_EXPIRED = "expired"
# All the job's datasets were reverted: none can be added back (a new mark is
# a new job)
CLOSED_REASON_ALL_REVERTED = "allReverted"

# A job's status is only set by whoever carries it out: Node-RED for
# markedForDeletion (datasets flagged) and revertMarkForDeletion (datasets
# restored) jobs. This service only records its own follow-up in
# jobResultObject.
STATUS_FINISHED_SUCCESSFUL = "finishedSuccessful"
STATUS_FINISHED_UNSUCCESSFUL = "finishedUnsuccessful"

# retentionTime suffix -> relativedelta keyword.
_RELATIVEDELTA_KWARG_BY_UNIT = {
    "Y": "years",
    "M": "months",
    "d": "days",
}


def _parse_retention(retention_time):
    """Validates e.g. "3M" and returns (3, "months")."""
    match = isinstance(retention_time, str) and re.fullmatch(
        rf"(\d+)([{''.join(_RELATIVEDELTA_KWARG_BY_UNIT)}])", retention_time
    )
    if not match:
        raise ValueError(f"Unrecognized retention time format: {retention_time!r}")
    return int(match[1]), _RELATIVEDELTA_KWARG_BY_UNIT[match[2]]


def retention_time_from_env(name):
    """Reads a grace period, e.g. "3M", from the env variable `name`, raising if malformed."""
    retention_time = environ[name]
    _parse_retention(retention_time)
    return retention_time


_RETENTION_STEP_DELTA = relativedelta(months=1)

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


_STILL_MARKED = {
    "datasetlifecycle.archiveStatusMessage": ARCHIVE_STATUS_MARKED_FOR_DELETION
}
_NOT_MARKED = {
    "datasetlifecycle.archiveStatusMessage": {"$ne": ARCHIVE_STATUS_MARKED_FOR_DELETION}
}


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


def _pids_by_owner_group(pids, where=None):
    """Returns {ownerGroup: [pid, ...]} for the given dataset pids matching `where`."""
    batches = _paginate(
        DatasetsV4Api().datasets_v4_controller_find_all_v4,
        {
            "where": {"pid": {"$in": pids}, **(where or {})},
            "fields": ["pid", "ownerGroup"],
        },
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
        log.warning(
            f"Datasets not found or not matching, not notified: {sorted(missing)}"
        )
    return dict(by_group)


def _submit_notifications(job_id, pids, job_params, where=None):
    """Submits one notification job per owner group of the given datasets matching `where`, returning how many."""
    pids_by_group = _pids_by_owner_group(pids, where)
    for owner_group, group_pids in pids_by_group.items():
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
    return len(pids_by_group)


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

    A dataset listed in a revertMarkForDeletion job created after this job
    is dropped from it for good, even if it is marked again later: the new
    markedForDeletion job handles it, with its own grace period. datasetList
    itself is never modified, for auditing.
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
        return self._job.job_params.get(PARAM_RETENTION_TIME)

    @property
    def retention_amount(self):
        """The grace period's numeric value, e.g. 3 for "3M"."""
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

    def _reverted_pids(self):
        """Returns the job's dataset pids listed by a revertMarkForDeletion job created after it."""
        own_pids = set(self.dataset_pids)
        reverts = RevertMarkForDeletionJobsRepository().jobs_listing_since(
            self.dataset_pids, self._job.creation_time
        )
        return {pid for revert in reverts for pid in revert.dataset_pids} & own_pids

    def _owned_pids(self):
        """Returns the job's dataset pids not reverted since the job was created."""
        reverted = self._reverted_pids()
        if reverted:
            log.info(f"Job {self.id} skips {len(reverted)} dataset(s) reverted since")
        return [pid for pid in self.dataset_pids if pid not in reverted]

    def _notify(self, pids, expired):
        """Submits one notification job per owner group of `pids` still marked for deletion, returning how many."""
        # Restored datasets (reverted) are no longer to be deleted: their
        # owners are not notified anymore, nor at all if none is left.
        return _submit_notifications(
            self.id,
            pids,
            {
                "markedForDeletionJobId": self.id,
                "expiryDate": self.expiry_date.isoformat(),
                "expired": expired,
                PARAM_DELETION_CODE: self.deletion_code,
            },
            where=_STILL_MARKED,
        )

    def _still_marked_pids(self, pids):
        """Returns the `pids` whose archiveStatusMessage is still markedForDeletion."""
        batches = _paginate(
            DatasetsV4Api().datasets_v4_controller_find_all_v4,
            {
                "where": {
                    "pid": {"$in": pids},
                    **_STILL_MARKED,
                },
                "fields": ["pid"],
            },
            DATASETS_PAGE_LIMIT,
            DATASETS_MAX_ITERATIONS,
            "datasets still marked for deletion",
        )
        return [dataset.pid for batch in batches for dataset in batch]

    def _submit_delete_job(self, owned_pids):
        """Submits a "delete" job for the `owned_pids` still marked for deletion, if any."""
        pids = self._still_marked_pids(owned_pids) if owned_pids else []
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
        owned_pids = self._owned_pids()
        # Notify (and submit the deletion) first: if it fails, the check-in is
        # not recorded and the job stays due for the next run. With nothing
        # left to notify (all reverted or none flagged), the check-in is
        # recorded as usual.
        if owned_pids:
            self._notify(owned_pids, expired)
        if expired:
            self._submit_delete_job(owned_pids)
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
        # All reverted takes precedence over expired: there is nothing to delete
        reason = (
            CLOSED_REASON_ALL_REVERTED
            if not owned_pids
            else CLOSED_REASON_EXPIRED if expired else None
        )
        if reason:
            patch["jobResultObject"][RESULT_CLOSED_AT] = now_iso
            patch["jobResultObject"][RESULT_CLOSED_REASON] = reason
            log.info(f"Job {self.id} closed: {reason}")
        else:
            log.info(f"Job {self.id} verification time updated, not yet expired")
        JobsApi().jobs_controller_update_v3(self.id, patch)


class MarkedForDeletionJobsRepository:
    """Fetches SciCat "markedForDeletion" jobs whose next check-in is due."""

    page_limit = 100
    max_iterations = 1000

    # jobParams.<param> rather than jobParams: datasetList maps to
    # jobParams.datasetList and projecting a path with its parent fails.
    fields = [
        "id",
        "datasetList",
        f"jobParams.{PARAM_DELETION_CODE}",
        f"jobParams.{PARAM_RETENTION_TIME}",
        "jobResultObject",
        "creationTime",
    ]

    def _due_jobs_filter(self, now):
        # Only jobs Node-RED finished, i.e. it is done flagging their
        # datasets: which ones are actually flagged is checked at every
        # check-in, so a partly or fully failed job is followed too. Such a
        # job is due when this service never checked it in (no verifiedAt
        # list yet) or when its last check-in is at least one retention step
        # old, until it is closed. A null match also covers missing fields.
        return {
            "where": {
                "type": JOB_TYPE_MARKED_FOR_DELETION,
                "jobStatusMessage": {
                    "inq": [STATUS_FINISHED_SUCCESSFUL, STATUS_FINISHED_UNSUCCESSFUL]
                },
                f"jobResultObject.{RESULT_CLOSED_AT}": None,
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
        """Notifies the owner groups of the restored datasets, then records the notification on the job."""
        # Notify first: if it fails, the notification is not recorded and the
        # job is picked up again on the next run. Only the datasets actually
        # restored, i.e. no longer marked, as a revert may partly fail: the
        # others stay protected, but are not cancelled. With none restored,
        # nothing is sent, but lastVerifiedAt is still recorded, so that the
        # job is processed only once.
        _submit_notifications(
            self.id,
            self.dataset_pids,
            {"revertMarkForDeletionJobId": self.id, "reverted": True},
            where=_NOT_MARKED,
        )
        patch = {
            "jobResultObject": {
                **(self._job.job_result_object or {}),
                RESULT_LAST_VERIFIED_AT: now.isoformat(),
            }
        }
        JobsApi().jobs_controller_update_v3(self.id, patch)
        log.info(f"Job {self.id} reverted mark for deletion notified")


class RevertMarkForDeletionJobsRepository:
    """
    Fetches SciCat "revertMarkForDeletion" jobs. Node-RED sets them
    finishedSuccessful once it restored their datasets, or
    finishedUnsuccessful if it failed for some or all of them.
    """

    page_limit = 100
    max_iterations = 1000

    fields = ["id", "datasetList", "jobResultObject"]

    def _unnotified_jobs_filter(self):
        # Only once Node-RED is done restoring, fully or partly: a pending
        # revert is notified on a later run. Not processed yet: a null match
        # also covers jobs without lastVerifiedAt.
        return {
            "where": {
                "type": JOB_TYPE_REVERT_MARK_FOR_DELETION,
                "jobStatusMessage": {
                    "inq": [STATUS_FINISHED_SUCCESSFUL, STATUS_FINISHED_UNSUCCESSFUL]
                },
                "datasetList": {"neq": []},
                f"jobResultObject.{RESULT_LAST_VERIFIED_AT}": None,
            },
            "fields": self.fields,
        }

    def jobs_listing_since(self, pids, since):
        """Yields revertMarkForDeletion jobs created after `since` listing any of `pids`, as RevertMarkForDeletionJob."""
        # Whatever their status: a pending or failed revert still keeps its
        # datasets from being deleted, as the owners asked to keep them.
        batches = _paginate(
            JobsApi().jobs_controller_find_all_v3,
            {
                "where": {
                    "type": JOB_TYPE_REVERT_MARK_FOR_DELETION,
                    "creationTime": {"gt": since.isoformat()},
                    "jobParams.datasetList.pid": {"inq": pids},
                },
                "fields": ["datasetList"],
            },
            self.page_limit,
            self.max_iterations,
            "revertMarkForDeletion jobs",
        )
        for batch in batches:
            for job in batch:
                yield RevertMarkForDeletionJob(job)

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
    """Fetches retrievable (archived, not deleted) datasets whose archiveRetentionTime has passed and are not marked for deletion yet."""

    page_limit = 100
    max_iterations = 1000

    def _expired_filter(self, now):
        # v3 rather than v4: only the v3 endpoint converts ISO strings to
        # dates, so archiveRetentionTime can be compared. Published datasets
        # cannot be marked for deletion. Only retrievable datasets are
        # considered: this excludes the ones not archived yet, and the deleted
        # ones, which keep their record and archiveRetentionTime. Like the
        # job config's psiStorage check, only PSI storage, empty or unset
        # (null also matches a missing field), else the job is rejected.
        return {
            "where": {
                "isPublished": False,
                "datasetlifecycle.retrievable": True,
                "datasetlifecycle.archiveRetentionTime": {"lte": now.isoformat()},
                "datasetlifecycle.archiveStatusMessage": {
                    "nin": [ARCHIVE_STATUS_MARKED_FOR_DELETION]
                },
                "datasetlifecycle.storageLocation": {"inq": ["PSI", "", None]},
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


def submit_expired_marked_for_deletion(owner_group, pids, retention_time):
    """Submits markedForDeletion jobs with deletionCode EXPIRED and the grace period retention_time, in chunks of MARK_MAX_DATASETS_PER_JOB."""
    for start in range(0, len(pids), MARK_MAX_DATASETS_PER_JOB):
        chunk = pids[start : start + MARK_MAX_DATASETS_PER_JOB]
        JobsApi().jobs_controller_create_v3(
            {
                "type": JOB_TYPE_MARKED_FOR_DELETION,
                "datasetList": [{"pid": pid, "files": []} for pid in chunk],
                "jobParams": {
                    "ownerGroup": owner_group,
                    PARAM_DELETION_CODE: DELETION_CODE_EXPIRED,
                    PARAM_RETENTION_TIME: retention_time,
                },
            }
        )
        log.info(
            f"Marked {len(chunk)} expired dataset(s) of {owner_group} for deletion"
        )
