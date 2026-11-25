# A cronjob that expires and submits deletion for datasets marked for deletion

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Workflow

In short, each part has a single role:

1. A job (`markedForDeletion` or `revertMarkForDeletion`) is submitted. The
   backend only validates it and publishes it on RabbitMQ.
2. A RabbitMQ listener (Node-RED) changes the datasets' lifecycle, right
   after the job is created: it flags them as `markedForDeletion`, or
   restores them on a revert. It then sets the job's status, telling
   whether that worked (see [Job statuses](#job-statuses)).
3. This cronjob decides when to email: on its schedule it reads the job and
   dataset state, and submits `notification` jobs (and the `delete` job at
   the end of the grace period). It never sends emails itself.
4. Node-RED picks up each `notification` job, looks up the owner group's
   emails and completes the job, which makes scicat-backend send the email.

So nothing is emailed when a job is created, only later on the cronjob's
schedule.

In detail:

1. A SciCat job with `type`: `markedForDeletion`, `datasetList`: the
   datasets, `jobParams.deletionCode`: the reason and
   `jobParams.retentionTime`: the grace period (e.g. `3M`, a number and a
   unit among `Y`, `M`, `d`, restricted to the allowed values by the job
   config) is created, either:
   - from the frontend or the API, when a user marks datasets, or
   - by the `mark-expired` command (see [Commands](#commands)), with
     `deletionCode` `EXPIRED` and `retentionTime` `EXPIRED_RETENTION_TIME`,
     for the datasets whose `datasetlifecycle.archiveRetentionTime` has
     passed.
2. A RabbitMQ listener (Node-RED) picks up the job on creation, flags each
   dataset as `markedForDeletion`, then sets the job `finishedSuccessful`
   (or `finishedUnsuccessful` if some or all could not be flagged).
3. This service runs periodically (e.g. daily) and re-confirms every
   `markedForDeletion` job whose next check-in is due — once every
   retention step (currently 1 month), regardless of the job's own grace
   period: a job with a 1-year grace period is still re-checked monthly
   throughout the year, not just once at the end. Only jobs Node-RED has
   finished are checked in, whether it succeeded or not, since which
   datasets are actually flagged is checked anyway; a job this service never
   checked in is due right away. The grace period is counted from the job's
   creation. The check-ins are recorded in `jobResultObject` (`verifiedAt`,
   `lastVerifiedAt`). Every check-in notifies the owner groups of the
   datasets the job still handles (see
   [Datasets of a job](#datasets-of-a-job) and
   [Notifications](#notifications)).
4. Once a job's full grace period has elapsed, it checks which of its
   datasets it still handles — a dataset may have been restored in the
   meantime (by a `revertMarkForDeletion` job), and possibly marked again
   by a later job (see [Datasets of a job](#datasets-of-a-job)).
   Whatever it still handles gets submitted as a new `delete` job, with the
   original job's `jobParams.deletionCode` (the reason of the deletion, also
   shown in every notification). The code is required when the job is
   created, so a job without one is reported as an error on every run. The
   original job is then closed, with `jobResultObject.closedAt` and
   `closedReason` `expired`, so it's never picked up again — even if nothing
   ended up marked, meaning no `delete` job was submitted.
5. In the same run, every `revertMarkForDeletion` job not notified yet,
   that Node-RED is done with (`finishedSuccessful` or
   `finishedUnsuccessful`), submits one `notification` job per owner group
   of its datasets actually restored, i.e. no longer marked (with
   `jobParams.reverted`), then records `jobResultObject.notifiedAt` so it's
   notified only once. The two steps are independent: a failure in one does
   not prevent the other.

### Datasets of a job

`datasetList` is never modified once a job is created — it's a snapshot of
what was originally marked, kept for auditing. Which of its datasets the job
still handles is decided fresh, at every check-in (for the notification) and
right before submitting the `delete` job, rather than tracked on the job over
time. A dataset is handled only if:

- it is still marked for deletion (`archiveStatusMessage`), and
- no `revertMarkForDeletion` job created after the job lists it, whatever
  its status: a pending or failed revert also keeps the dataset from being
  deleted, as its owners asked to keep it. A revert drops the dataset from
  the job for good: if it is marked again later, the new job handles it,
  with its own grace period, so the earlier job neither notifies about it
  nor deletes it.

Once all its datasets were reverted, the job is closed, with
`jobResultObject.closedAt` and `closedReason` `allReverted` (rather than
`expired`, when both apply), and never picked up again: none of its datasets
can come back, since marking them again creates a new job.

That keeps `revertMarkForDeletion` simple too: restoring a dataset only ever
touches the dataset itself, never any `markedForDeletion` job.

### Job statuses

A job's status is only set by whoever carries it out, and says whether that
worked. This cronjob never sets a status: it records its own follow-up in
`jobResultObject`. Every job starts with the backend's default status,
`jobSubmitted`. Then, by job type:

- `markedForDeletion`, set by Node-RED:
  - `jobSubmitted`: the datasets are not flagged yet. Not checked in.
  - `finishedSuccessful`: all the datasets were flagged.
  - `finishedUnsuccessful`: some or all could not be flagged.

  Both finished statuses are checked in, until this cronjob closes the job
  (`jobResultObject.closedAt`, `closedReason`).
- `revertMarkForDeletion`, set by Node-RED:
  - `jobSubmitted`: the datasets are not restored yet.
  - `finishedSuccessful`: all the datasets were restored.
  - `finishedUnsuccessful`: some or all could not be restored.

  Once finished either way, on its next run this cronjob emails the owner
  groups of the datasets actually restored ("Deletion cancelled"), checked
  on the datasets themselves (no longer marked), and writes the time to
  `jobResultObject.notifiedAt`, so that it never emails them again for this
  job, even if none was restored.

  Whatever its status, a revert keeps its datasets from being deleted (see
  [Datasets of a job](#datasets-of-a-job)). The datasets it could not
  restore stay flagged, but no job deletes them; a new revert can restore
  them.
- `notification`, set by Node-RED:
  - `finishedSuccessful`: the `contactEmails` were looked up, and this
    update makes scicat-backend send the email.
  - `finishedUnsuccessful`: the lookup or the email failed, no email sent.
- `delete`: submitted by this cronjob with `jobSubmitted`, then updated by
  the archive system as it processes the deletion.

With the status of a `markedForDeletion` or `revertMarkForDeletion` job,
Node-RED also records in its `jobResultObject`:

- `datasetsTotal`: how many datasets the job lists.
- `datasetsFailed`: how many of them could not be flagged, or restored.
- `result`: one entry per dataset, in the same layout as retrieve jobs
  (`datasetId`): `{datasetId, status: "updated"}`, or
  `{datasetId, status: "failed", error}`. The failed ones can be submitted
  again in a new job.

The submitter of a `markedForDeletion`, `revertMarkForDeletion` or `delete`
job (its `contactEmail`, by default the submitting user's email) is emailed
when the job is submitted, and once it is finished, successfully or not. The
email's dataset table then has a Result column, from `result`, and a failure
says how many datasets could not be processed.

## Commands

The same image runs two independent commands, each meant as its own cronjob:

- `python main.py retention` (the default): checks in the due
  `markedForDeletion` jobs (steps 3 and 4) and notifies the
  `revertMarkForDeletion` jobs (step 5).
- `python main.py mark-expired`: submits one `markedForDeletion` job per
  owner group (split above 1000 datasets) for the unpublished, retrievable
  datasets (i.e. archived and not deleted) on PSI storage whose archive
  retention time has passed and that are not marked for deletion yet. It
  only submits the jobs: everything after is the same as for a job from the
  frontend or the API.

## Notifications

Every notification is a `notification` job, one per owner group of the
datasets concerned. Node-RED updates the job with the group's
`contactEmails`, and scicat-backend sends the email. They are sent:

- **Datasets scheduled for deletion**, with the expiry date and the deletion
  code: at every check-in of a `markedForDeletion` job before its grace
  period has elapsed, for the datasets it still handles (see
  [Datasets of a job](#datasets-of-a-job)).
- **Retention period expired** (`jobParams.expired`): at the check-in at
  which its grace period has elapsed, for the datasets it still handles, the
  same ones as the `delete` job.
- **Deletion cancelled** (`jobParams.reverted`): once per
  `revertMarkForDeletion` job, at the first run after Node-RED is done with
  it, for the job's datasets actually restored (no longer marked). Its
  datasets that could not be restored are kept, but not reported here.

Also:

- A `markedForDeletion` check-in with no dataset left to handle (all
  reverted, or none flagged) sends no notification, and is recorded as
  usual. With all reverted, the job is also closed (see
  [Datasets of a job](#datasets-of-a-job)).
- If submitting a notification fails, the check-in (or `notifiedAt` for a
  revert) is not recorded, so the job is retried on the next run.
- Nothing is sent when a `markedForDeletion` job is created, nor for the
  `delete` job: the first email comes with the first check-in.

## Getting started

The easiest way to set up a dev environment is to use the provided compose file.

```bash
docker-compose -f docker-compose.dev.yml up --build
```

## Docker

Variables to be supplied for docker run:

- SCICAT_ENDPOINT
- SCICAT_USERNAME
- SCICAT_PASSWORD
- EXPIRED_RETENTION_TIME (`mark-expired` only): grace period of the datasets
  marked by `mark-expired`, e.g. `3M`, one of the values allowed by the job
  config

```bash
IMAGE_NAME=<IMAGE_NAME>
docker build -t $IMAGE_NAME .
docker run -e "SCICAT_ENDPOINT=<SCICAT_ENDPOINT>" \
  -e "SCICAT_USERNAME=<SCICAT_USERNAME>" \
  -e "SCICAT_PASSWORD=<SCICAT_PASSWORD>" \
  -e "EXPIRED_RETENTION_TIME=<EXPIRED_RETENTION_TIME>" \
  $IMAGE_NAME python main.py [retention|mark-expired]
```
