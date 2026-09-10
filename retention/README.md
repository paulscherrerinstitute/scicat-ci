# A cronjob that expires and submits deletion for datasets marked for deletion

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Workflow

1. In the frontend, a user selects datasets and clicks "mark for deletion".
   This creates a SciCat job with `type`: `markedForDeletion` and
   `datasetList`: the selected datasets.
2. A RabbitMQ listener picks up the job on creation: it flags each dataset
   as `markedForDeletion`, and records on the job itself the grace period
   (e.g. 3 months) and an initial check-in timestamp — the baseline the
   first check-in is measured from. Until that's recorded, the job simply
   isn't ready yet; that isn't treated as an error.
3. This service runs periodically (e.g. daily) and re-confirms every
   `markedForDeletion` job whose next check-in is due — once every
   retention step (currently 1 month), regardless of the job's own grace
   period: a job with a 1-year grace period is still re-checked monthly
   throughout the year, not just once at the end.
4. Once a job's full grace period has elapsed, it checks which of its
   datasets are still marked for deletion — a dataset may have been
   restored in the meantime (e.g. by a future `revertDeletion` job type).
   Whatever is still marked gets submitted as a new `delete` job. Either
   way, the original job is marked expired so it's never picked up again —
   even if nothing ended up marked, meaning no `delete` job was submitted.

`datasetList` is never modified once a job is created — it's a snapshot of
what was originally marked. Whether a dataset is still eligible for deletion
is decided fresh, right before submitting the `delete` job, rather than
tracked on the job over time. That keeps a future `revertDeletion` simple
too: restoring a dataset only ever touches the dataset itself, never any
`markedForDeletion` job.

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
