# A cronjob re-confirming datasets marked for deletion until their retention period expires

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Workflow

1. In the frontend, a user selects datasets and clicks "mark for deletion".
   This creates a SciCat job with `type`: `markedForDeletion` and
   `datasetList`: the selected datasets.
2. A RabbitMQ listener picks up the job on creation: it patches each dataset,
   setting `datasetlifecycle.archiveStatusMessage` to `markedForDeletion`,
   and writes onto the job itself both the grace period as
   `jobResultObject.retentionTime`, e.g. `{"value": 3, "unit": "M"}` for 3
   months (`unit` follows the same calendar (uppercase `Y`/`M`) vs. clock
   (lowercase `d`/`h`/`m`/`s`) convention ISO 8601 durations use), and an
   initial `jobResultObject.lastVerifiedAt` timestamp, the baseline the first
   check-in is measured from. Until `lastVerifiedAt` is set, this service's
   query simply never selects the job — not an error, just a job the
   listener hasn't processed yet.
3. This service runs periodically (e.g. daily, via a cronjob) and fetches
   every `markedForDeletion` job whose `datasetList` isn't empty and whose
   `lastVerifiedAt` is at least one retention step old — those conditions
   are `where` clauses in the query itself, not a check done after
   fetching. For each job returned, it records the check-in as
   `jobResultObject.lastVerifiedAt` (the only kind of field the v3 API lets
   be patched after creation, alongside `jobStatusMessage`). If the job's
   full `retentionTime` grace period has elapsed since `creationTime`, its
   `jobStatusMessage` is set to `retentionExpired` — the signal for
   whichever downstream process performs the actual deletion.

Check-ins happen once every retention step (currently 1 month), independently
of `retentionTime`'s own unit — a job with `retentionTime`
`{"value": 1, "unit": "Y"}` is still re-checked monthly throughout the year,
not just once at the end. Whether the job has actually expired is a separate
check against `creationTime + retentionTime` on every check-in.

**Not yet implemented:**

- Once a job's retention period has passed, submitting a new job of type
  `delete` for its remaining datasets — with one final safety check that
  filters out any dataset whose status isn't `markedForDeletion` — instead
  of just flagging the job as `retentionExpired`.
- Paginating `due_jobs()`. The jobs endpoint caps a single response at 100
  results, so once there are more due jobs than that in one run, this
  service silently only sees the first page. It needs a `skip`/`limit`
  iterator over the loopback filter's `limits`, yielding page by page (with
  a max-iterations safety cap) until an empty page comes back.

This first version simply lets every due job run its grace period out
unconditionally.

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

```bash
IMAGE_NAME=<IMAGE_NAME>
docker build -t $IMAGE_NAME .
docker run -e "SCICAT_ENDPOINT=<SCICAT_ENDPOINT>" -e "SCICAT_USERNAME=<SCICAT_USERNAME>" \
-e "SCICAT_PASSWORD=<SCICAT_PASSWORD>" \
$IMAGE_NAME python main.py
```
