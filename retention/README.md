# A cronjob that expires and submits deletion for datasets marked for deletion

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Workflow

1. A SciCat job with `type`: `markedForDeletion`, `datasetList`: the
   datasets, `jobParams.deletionCode`: the reason and
   `jobParams.retentionTime`: the grace period (e.g. `3M`, a number and a unit
   among `Y`, `M`, `d`, restricted to the allowed
   values by the job config) is created, either:
   - from the frontend or the API, when a user marks datasets, or
   - by the `mark-expired` command (see [Commands](#commands)), with
     `deletionCode` `EXPIRED` and `retentionTime` `EXPIRED_RETENTION_TIME`, for
     the datasets whose `datasetlifecycle.archiveRetentionTime` has passed.
2. A RabbitMQ listener (Node-RED) picks up the job on creation and flags
   each dataset as `markedForDeletion`.
3. This service runs periodically (e.g. daily) and re-confirms every
   `markedForDeletion` job whose next check-in is due — once every
   retention step (currently 1 month), regardless of the job's own grace
   period: a job with a 1-year grace period is still re-checked monthly
   throughout the year, not just once at the end. A job this service never
   checked in is due right away. The grace period is counted from the job's
   creation. Every check-in submits one `notification`
   job per owner group of the datasets; Node-RED emails the group members.
4. Once a job's full grace period has elapsed, it checks which of its
   datasets are still marked for deletion — a dataset may have been
   restored in the meantime (by a `revertMarkForDeletion` job).
   Whatever is still marked gets submitted as a new `delete` job, with the
   original job's `jobParams.deletionCode` (the reason of the deletion, also
   shown in every notification). The code is required when the job is
   created, so a job without one is reported as an error on every run. The
   original job is then marked expired so it's never picked up again — even
   if nothing ended up marked, meaning no `delete` job was submitted.
5. In the same run, every `revertMarkForDeletion` job not notified yet
   submits one `notification` job per owner group of its datasets (with
   `jobParams.reverted`), then records `jobResultObject.notifiedAt` so it's
   notified only once. The two steps are independent: a failure in one does
   not prevent the other.

`datasetList` is never modified once a job is created — it's a snapshot of
what was originally marked. Whether a dataset is still eligible for deletion
is decided fresh, right before submitting the `delete` job, rather than
tracked on the job over time. That keeps `revertMarkForDeletion` simple
too: restoring a dataset only ever touches the dataset itself, never any
`markedForDeletion` job.

## Commands

The same image runs two independent commands, each meant as its own cronjob:

- `python main.py retention` (the default): checks in the due
  `markedForDeletion` jobs (steps 3 and 4) and notifies the
  `revertMarkForDeletion` jobs (step 5).
- `python main.py mark-expired`: submits one `markedForDeletion` job per owner
  group (split above 1000 datasets) for the unpublished datasets whose archive
  retention time has passed and that are not marked for deletion yet. It only
  submits the jobs: everything after is the same as for a job from the
  frontend or the API.

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
- EXPIRED_RETENTION_TIME: grace period of the datasets marked by `mark-expired`, e.g. `3M`
  (`mark-expired` only), one of the values allowed by the job config

```bash
IMAGE_NAME=<IMAGE_NAME>
docker build -t $IMAGE_NAME .
docker run -e "SCICAT_ENDPOINT=<SCICAT_ENDPOINT>" -e "SCICAT_USERNAME=<SCICAT_USERNAME>" \
-e "SCICAT_PASSWORD=<SCICAT_PASSWORD>" \
-e "EXPIRED_RETENTION_TIME=<EXPIRED_RETENTION_TIME>" \
$IMAGE_NAME python main.py [retention|mark-expired]
```
