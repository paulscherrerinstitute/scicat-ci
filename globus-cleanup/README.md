# Globus Cleanup

Script to manage and release storage of datasets transferred by the globus-proxy.

Reports SciCat archive status for datasets stored on a Globus collection, and deletes the
Globus copies of datasets that SciCat reports as safely archived
(`retrievable == true` and `archiveStatusMessage == datasetOnArchiveDisk`).

See `python scicat_globus_cleaner.py --help` for all options.

## Authentication

This requires a globus service user with read and delete permissions. It also needs a
scicat functional account which can read all datasets. Currently credentials are shared
with the globus-proxy (`pass development/scicat/globus_proxy/env`).

## Interactive use

The `scicat_globus_cleaner.py` script can be run directly. It requires the [globus
cli](https://docs.globus.org/cli/) be installed.

```sh
pip install -r requirements.txt

# Set env vars. Some vars need to be renamed from the versions in pass.
eval `pass development/scicat/globus_proxy/env`
export GLOBUS_CLI_CLIENT_ID=$GLOBUS_CLIENT_ID
export GLOBUS_CLI_CLIENT_SECRET=$GLOBUS_CLIENT_SECRET
export SCICAT_SERVICE_USER_USERNAME SCICAT_SERVICE_USER_PASSWORD
export SCICAT_BACKEND=https://scicat.development.psi.ch
export GLOBUS_COLLECTION=...

python scicat_globus_cleaner.py                # report only
python scicat_globus_cleaner.py --clean -n     # show what would be deleted
python scicat_globus_cleaner.py --clean -i     # confirm each deletion
```

## Docker use

```sh
docker build -t globus-cleanup .

# Takes required variariables from the shell
docker run -it --rm --env-file .env globus-cleaner

# Or, you can mount /app/.env inside the container
pass development/scicat/globus_proxy/env > globus_proxy.env
docker run -it --rm -v $PWD/globus_proxy.env:/app/.env -e SCICAT_BACKEND -e GLOBUS_COLLECTION globus-cleaner
```

## Safeguards

- **One cleanup at a time.** If an earlier `SciCat cleanup` delete task is still `ACTIVE`,
  the run is skipped (exit 0). If one is `INACTIVE` (paused, e.g. expired credentials or
  permission problems) the job fails, since it won't finish on its own.
- **Limits.** `--max-datasets` / `--max-size` make the job fail without deleting anything
  if the selection is unexpectedly large (e.g. bad SciCat data). A large backlog needs
  to be cleared once by hand with higher limits.
- **No retries.** `backoffLimit: 0`; a failed run shows up as a failed Job.

The dataset table goes to stdout and the Globus task ID to stderr; both appear in
`kubectl logs`. Check the deletion with `globus task show <TASK_ID>`.
