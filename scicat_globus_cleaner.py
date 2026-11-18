#!/usr/bin/env python3
"""Report SciCat size / archivable / retrievable for datasets found on a Globus collection.

Each subdirectory of e.g. $GLOBUS_PSI_QA:/archive/20-500-11935/ is a dataset UUID; the
SciCat PID is "<prefix with dots>/<uuid>", e.g. 20.500.11935/07e6926a-....

Requirements: `globus` CLI (logged in), `requests`.

Usage:
    export SCICAT_BACKEND=https://dacat-qa.psi.ch   # SciCat backend base URL
    export SCICAT_TOKEN=...                         # SciCat access token, or:
    export SCICAT_SERVICE_USER_USERNAME=...         # SciCat functional account
    export SCICAT_SERVICE_USER_PASSWORD=...
    python scicat_globus_cleaner.py --collection "$GLOBUS_PSI_QA"
    python scicat_globus_cleaner.py -F csv -o out.csv

Cleanup:
    --clean selects every dataset with retrievable == true and archiveStatus ==
    datasetOnArchiveDisk (with -i, each one is confirmed after its info row is written).
    Once all datasets are processed, the selected directories are deleted recursively in a
    single non-blocking Globus task (`globus delete -r --batch`). The task ID is printed to
    stderr; check it with `globus task show TASK_ID` or `globus task wait TASK_ID`.
    Nothing is deleted if the script is interrupted before then.

    Safeguards for unattended runs (e.g. a Kubernetes CronJob):
    - If an earlier "SciCat cleanup" delete task is still ACTIVE, the run is skipped (exit 0).
      If one is INACTIVE (paused, e.g. expired credentials), the script exits with an error,
      since it needs attention. Use --allow-concurrent to skip this check.
    - --max-datasets / --max-size abort the run (exit 1, nothing deleted) if the selection
      is larger than expected, e.g. because of bad SciCat data.
    - --ignore-missing (`globus delete -f`) doesn't fail on directories that are already gone.

    Exit codes: 0 success (or skipped), 1 error, 2 usage error.

    python scicat_globus_cleaner.py --clean -n  # show what would be deleted
    python scicat_globus_cleaner.py --clean -i  # ask interactively before deleting
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from urllib.parse import quote

import requests


def globus_ls(path, recursive=False):
    "Calls 'globus ls -l' at the requested path"
    cmd = ["globus", "ls", "-F", "json", "-l", path]
    if recursive:
        cmd[2:2] = ["-r", "--recursive-depth-limit", "1000"]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    #TODO warn if we hit the recursive depth limit
    return json.loads(out).get("DATA", [])


def globus_size(path):
    """Sum of file sizes under path (slow for large trees)."""
    return sum(e.get("size", 0) for e in globus_ls(path, recursive=True) if e.get("type") == "file")


def pid_prefix(path):
    # ".../archive/20-500-11935/" -> "20.500.11935"
    return path.rstrip("/").rsplit("/", 1)[-1].split(":")[-1].replace("-", ".")
def pid_to_path(pid):
    "Convert a PID to a file path. Replaces periods with hyphens."
    return pid.replace(".","-")
def path_to_pid(path):
    "Convert a path to a PID. Replaces hyphens with periods."
    return path.rstrip("/").rsplit("/", 1)[-1].split(":")[-1].replace("-", ".")

class SciCatError(Exception):
    "Fatal problem talking to SciCat (unreachable, bad credentials)"


TOKEN_HINT = "Get a new token (SCICAT_TOKEN / --token) or use --username/--password."


class SciCatSession(requests.Session):
    """requests.Session for SciCat using either a fixed token or username/password login.

    With username/password, a 401 response triggers one re-login and retry, so long runs
    survive token expiry."""

    def __init__(self, base_url, token=None, username=None, password=None):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.username, self.password = username, password
        self.logins = 0  # number of successful logins, used to detect re-logins
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        elif username and password:
            self.login()

    @property
    def can_login(self):
        return bool(self.username and self.password)

    def login(self):
        "Get a new token from /auth/login and use it for subsequent requests"
        url = f"{self.base_url}/api/v3/auth/login"
        try:
            r = super().request("POST", url, json={"username": self.username, "password": self.password},
                                headers={"Accept": "application/json"}, timeout=30)
        except requests.RequestException as e:
            raise SciCatError(f"Cannot reach SciCat at {self.base_url}: {e}") from e
        if r.status_code in (401, 403):
            raise SciCatError(f"SciCat login failed for user {self.username!r}: wrong username or password")
        if not r.ok:
            raise SciCatError(f"SciCat login failed: HTTP {r.status_code} {r.text[:200]}")
        try:
            token = r.json()["access_token"]
        except (ValueError, KeyError):
            raise SciCatError(f"Unexpected login response from {url}: {r.text[:200]}")
        self.headers["Authorization"] = f"Bearer {token}"
        self.logins += 1

    def request(self, method, url, *args, **kwargs):
        r = super().request(method, url, *args, **kwargs)
        if r.status_code == 401 and self.can_login:
            self.login()
            r = super().request(method, url, *args, **kwargs)
        return r


def check_scicat(session, base_url):
    """Check that SciCat is reachable and the token is valid. Returns the username.

    Raises SciCatError with a readable message otherwise."""
    url = f"{base_url.rstrip('/')}/api/v3/auth/whoami"
    try:
        r = session.get(url, timeout=30)
    except requests.RequestException as e:
        raise SciCatError(f"Cannot reach SciCat at {base_url}: {e}") from e
    if r.status_code in (401, 403):
        raise SciCatError(
            f"SciCat rejected the token (HTTP {r.status_code}): it is invalid or has expired. "
            + TOKEN_HINT)
    if not r.ok:
        raise SciCatError(f"Unexpected response from {url}: HTTP {r.status_code} {r.text[:200]}")
    try:
        user = r.json() or {}
    except ValueError:
        raise SciCatError(f"{url} did not return JSON; is {base_url} a SciCat backend?")
    if not user:
        raise SciCatError("SciCat did not recognise the token; it may have expired.")
    return user.get("username") or user.get("email") or "unknown user"


def get_dataset(session, base_url, pid):
    "Get a dataset from scicat. Returns None if not found."
    url = f"{base_url.rstrip('/')}/api/v4/datasets/{quote(pid, safe='')}"
    r = session.get(url, timeout=30)
    if r.status_code == 401:
        raise SciCatError("SciCat rejected the token (HTTP 401): it is invalid or has expired. "
                          + TOKEN_HINT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json() or None


class DelimitedWriter:
    "CSV/TSV output"
    delimiter = ","

    def __init__(self, out, cols):
        self.w = csv.DictWriter(out, fieldnames=cols, delimiter=self.delimiter, extrasaction="ignore")

    def header(self):
        self.w.writeheader()

    def row(self, row):
        self.w.writerow(row)

    def footer(self):
        pass


class TSVWriter(DelimitedWriter):
    delimiter = "\t"


class JSONWriter:
    "JSON array of objects, streamed one element at a time"

    def __init__(self, out, cols):
        self.out, self.cols, self.first = out, cols, True

    def header(self):
        self.out.write("[")

    def row(self, row):
        self.out.write("\n  " if self.first else ",\n  ")
        self.out.write(json.dumps({c: row.get(c) for c in self.cols}))
        self.first = False

    def footer(self):
        self.out.write("\n]\n" if not self.first else "]\n")


class MarkdownWriter:
    "GitHub-flavoured markdown table"

    def __init__(self, out, cols):
        self.out, self.cols = out, cols

    def header(self):
        self.out.write("| " + " | ".join(self.cols) + " |\n")
        self.out.write("|" + "|".join("---" for _ in self.cols) + "|\n")

    @staticmethod
    def _cell(v):
        if v is None:
            return ""
        return str(v).replace("|", "\\|").replace("\n", " ")

    def row(self, row):
        self.out.write("| " + " | ".join(self._cell(row.get(c)) for c in self.cols) + " |\n")

    def footer(self):
        pass


FORMATS = {"tsv": TSVWriter, "csv": DelimitedWriter, "json": JSONWriter, "md": MarkdownWriter}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pids", nargs="*", metavar="PID",
                    help="dataset PIDs to check (default: list all datasets under --prefix on Globus)")
    ap.add_argument("--path", default="/archive", help="Globus path to the dataset location")
    ap.add_argument("--collection", default=os.environ.get("GLOBUS_COLLECTION"), help="Globus collection id")
    ap.add_argument("--scicat-url", default=os.environ.get("SCICAT_BACKEND"))
    ap.add_argument("--token", default=os.environ.get("SCICAT_TOKEN"),
                    help="SciCat access token (default: $SCICAT_TOKEN). Takes precedence over --username")
    ap.add_argument("--username", default=os.environ.get("SCICAT_SERVICE_USER_USERNAME"),
                    help="SciCat username to log in with (default: $SCICAT_SERVICE_USER_USERNAME)")
    ap.add_argument("--password", default=os.environ.get("SCICAT_SERVICE_USER_PASSWORD"),
                    help="SciCat password (default: $SCICAT_SERVICE_USER_PASSWORD; "
                         "prefer the env var, command-line arguments are visible to other users)")
    ap.add_argument("--prefix", default="20.500.11935", help="PID prefix (ignored if PIDs are given)")
    ap.add_argument("--globus-size", action="store_true", help="calculate file sizes from Globus rather than SciCat (slow)")
    ap.add_argument("-F", "--format", choices=FORMATS, default="tsv",
                    help="output format (default: tsv)")
    ap.add_argument("-o", "--output", type=argparse.FileType("w"), default=sys.stdout,
                    help="write results to this file; '-' for stdout (default)")
    ap.add_argument("--clean", action="store_true",
                    help="delete Globus copies of datasets that are retrievable and on archive disk")
    ap.add_argument("-n", "--dry-run", action="store_true",
                    help="with --clean: pass --dry-run to globus delete; nothing is submitted")
    ap.add_argument("-i", "--interactive", action="store_true",
                    help="with --clean: confirm each deletion, and the final submission")
    ap.add_argument("--notify", metavar="EVENTS",
                    help="with --clean: passed to `globus delete --notify` "
                         "(comma-separated: on, off, succeeded, failed, inactive)")
    ap.add_argument("--ignore-missing", action="store_true",
                    help="with --clean: don't fail if a directory is already gone (globus delete -f)")
    ap.add_argument("--max-datasets", type=int, metavar="N",
                    help="with --clean: abort without deleting anything if more than N datasets are selected")
    ap.add_argument("--max-size", type=parse_size, metavar="SIZE",
                    help="with --clean: abort without deleting anything if the selection is larger than "
                         "SIZE (bytes, or with a unit, e.g. 500GiB, 2TB)")
    ap.add_argument("--allow-concurrent", action="store_true",
                    help="with --clean: run even if an earlier cleanup task is still running")
    args = ap.parse_args()
    clean_opts = ("dry_run", "interactive", "notify", "ignore_missing", "max_datasets", "max_size",
                  "allow_concurrent")
    if not args.clean and any(getattr(args, o) for o in clean_opts):
        ap.error("--" + "/--".join(o.replace("_", "-") for o in clean_opts) + " require --clean")
    if not args.scicat_url:
        ap.error("set --scicat-url or SCICAT_BACKEND")
    if not args.collection and (not args.pids or args.globus_size or args.clean):
        ap.error("set --collection or GLOBUS_COLLECTION")
    if not args.token and not (args.username and args.password):
        ap.error("set --token/SCICAT_TOKEN, or --username and --password "
                 "(SCICAT_SERVICE_USER_USERNAME / SCICAT_SERVICE_USER_PASSWORD)")


    if args.clean and not args.allow_concurrent:
        check_running_cleanups(args.dry_run)

    try:
        s = SciCatSession(args.scicat_url, args.token, args.username, args.password)
        check_scicat(s, args.scicat_url)
    except SciCatError as e:
        sys.exit(f"Error: {e}")

    # Globus base directory, e.g. COLLECTION:/archive
    base = "{collection}:{path}".format(collection=args.collection, path=args.path.rstrip("/"))
    if args.pids:
        datasets = ((pid, f"{base}/{pid_to_path(pid)}") for pid in args.pids)
    else:
        datasets = list_datasets(base, args.prefix)
    cols = ["pid", "size", "files", "archivable", "retrievable", "archiveStatus", "retrieveStatus"]
    if args.globus_size:
        cols.append("globus_size")
    cols.append("error")

    out = args.output
    cleaner = Cleaner(args) if args.clean else None
    try:
        w = FORMATS[args.format](out, cols)
        w.header()
        out.flush()
        try:
            for row in iter_rows(s, args, datasets):
                w.row(row)
                out.flush()
                if cleaner:
                    cleaner.process(row)
        except SciCatError as e:
            error = e
        else:
            error = None
        w.footer()  # keep partial output well-formed (e.g. JSON)
        out.flush()
    finally:
        if out is not sys.stdout:
            out.close()
    if error:
        msg = f"Error: {error}"
        if cleaner and cleaner.paths:
            msg += "\nAborted before submitting the delete task; nothing was deleted."
        sys.exit(msg)
    if cleaner:
        cleaner.submit(args.collection)


def list_datasets(base, prefix):
    "Yield (pid, globus_path) for each dataset directory under base/prefix on Globus"
    path = f"{base}/{pid_to_path(prefix)}"
    for entry in globus_ls(path):
        if entry.get("type") != "dir":
            continue
        uuid = entry["name"].rstrip("/")
        yield f"{prefix}/{uuid}", f"{path}/{uuid}"


def iter_rows(s, args, datasets):
    "Yield one result row per (pid, globus_path) pair"
    for pid, ds_path in datasets:
        row = {"pid": pid}
        try:
            ds = get_dataset(s, args.scicat_url, pid)
        except requests.RequestException as e:
            ds, row["error"] = None, str(e)
        if ds is None and "error" not in row:
            # Distinguish a missing dataset from credentials expiring mid-run
            # (expired tokens can give 404 rather than 401)
            logins = s.logins
            check_scicat(s, args.scicat_url)
            if s.logins != logins:  # re-logged in; the 404 may have been the old token
                ds = get_dataset(s, args.scicat_url, pid)
            if ds is None:
                row["error"] = "not found in SciCat"
        if ds is not None:
            lc = ds.get("datasetlifecycle") or {}
            row.update(
                size=ds.get("size"),
                files=ds.get("numberOfFiles"),
                archivable=lc.get("archivable"),
                retrievable=lc.get("retrievable"),
                archiveStatus=lc.get("archiveStatusMessage"),
                retrieveStatus=lc.get("retrieveStatusMessage"),
            )
        if args.globus_size:
            try:
                row["globus_size"] = globus_size(f"{ds_path}/")
            except subprocess.CalledProcessError as e:
                row["globus_size"] = None
                row["error"] = (row.get("error", "") + " globus: " + e.stderr.strip()).strip()
        row["_path"] = ds_path
        yield row


def human_size(n):
    "Format a byte count with binary units, e.g. 1536 -> '1.5 KiB'"
    if n is None:
        return "unknown size"
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(n) < 1024 or unit == "PiB":
            break
        n /= 1024
    return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"


UNITS = {"": 1, "b": 1,
         "k": 1000, "kb": 1000, "m": 1000**2, "mb": 1000**2, "g": 1000**3, "gb": 1000**3,
         "t": 1000**4, "tb": 1000**4, "p": 1000**5, "pb": 1000**5,
         "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4, "pib": 1024**5}


def parse_size(text):
    "Parse '1234', '500GiB', '2 TB' etc. into bytes (for argparse)"
    m = re.fullmatch(r"\s*([0-9.]+)\s*([a-zA-Z]*)\s*", text)
    if not m or m.group(2).lower() not in UNITS:
        raise argparse.ArgumentTypeError(f"invalid size {text!r}; use e.g. 500GiB or 2TB")
    return int(float(m.group(1)) * UNITS[m.group(2).lower()])


CLEANUP_LABEL = "SciCat cleanup"


def check_running_cleanups(dry_run=False):
    """Exit if an earlier cleanup delete task (by this Globus identity) hasn't finished.

    ACTIVE tasks: skip this run (exit 0). INACTIVE tasks: exit 1, they need attention."""
    cmd = ["globus", "task", "list", "--filter-type", "DELETE",
           "--filter-status", "ACTIVE", "--filter-status", "INACTIVE",
           "--filter-label", f"{CLEANUP_LABEL}*", "--inexact", "--limit", "100", "-F", "json"]
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        tasks = json.loads(res.stdout).get("DATA", [])
    except subprocess.CalledProcessError as e:
        sys.exit(f"Error: could not list Globus tasks: {e.stderr.strip()}")
    except ValueError as e:
        sys.exit(f"Error: unexpected output from globus task list: {e}")
    if not tasks:
        return
    desc = "\n".join(f"  {t['task_id']}  {t['status']}  {t.get('label')}" for t in tasks)
    if dry_run:
        sys.stderr.write(f"Warning: earlier cleanup task(s) not finished; a real run would stop here:\n{desc}\n")
    elif any(t["status"] == "INACTIVE" for t in tasks):
        sys.exit(f"Error: earlier cleanup task(s) are paused and need attention "
                 f"(see `globus task pause-info TASK_ID`):\n{desc}")
    else:
        sys.stderr.write(f"Earlier cleanup task(s) still running; skipping this run:\n{desc}\n")
        sys.exit(0)


def should_clean(row):
    "Only delete datasets that SciCat says are safely archived"
    return row.get("retrievable") is True and row.get("archiveStatus") == "datasetOnArchiveDisk"


def confirm(prompt):
    "Ask on the terminal; returns 'y', 'n', 'a' (all remaining) or 'q' (quit)"
    while True:
        sys.stderr.write(f"{prompt} [y/n/a/q] ")
        sys.stderr.flush()
        ans = sys.stdin.readline()
        if not ans:  # EOF
            return "q"
        ans = ans.strip().lower()[:1]
        if ans in ("y", "n", "a", "q"):
            return ans


def globus_delete(collection, paths, label, dry_run=False, notify=None, ignore_missing=False):
    """Submit one non-blocking recursive delete task for all paths on collection.

    Returns the task ID (or None for dry runs)."""
    cmd = ["globus", "delete", "-r", "--no-enable-globs", "--batch", "-", "--label", label,
           "-F", "json", collection]
    if dry_run:
        cmd.insert(2, "--dry-run")
    if notify:
        cmd[2:2] = ["--notify", notify]
    if ignore_missing:
        cmd.insert(2, "--ignore-missing")
    batch = "".join(f"{p}\n" for p in paths)
    res = subprocess.run(cmd, check=True, capture_output=True, text=True, input=batch)
    if dry_run:
        sys.stderr.write(res.stdout)
        return None
    return json.loads(res.stdout)["task_id"]


class Cleaner:
    "Select datasets to delete one at a time, then submit them as a single Globus task"

    def __init__(self, args):
        self.dry_run = args.dry_run
        self.notify = args.notify
        self.ignore_missing = args.ignore_missing
        self.max_datasets = args.max_datasets
        self.max_size = args.max_size
        self.interactive = args.interactive
        self.ask = args.interactive
        self.quit = False
        self.paths = []  # paths within the collection
        self.size = 0

    def process(self, row):
        "Returns the action taken: keep, skipped or selected"
        if not should_clean(row):
            return "keep"
        if self.quit:
            return "skipped"
        ds_path = row["_path"]
        ans = confirm(f"Delete {ds_path} ({human_size(row.get('size'))})?") if self.ask else "y"
        if ans == "a":
            self.ask, ans = False, "y"
        if ans == "q":
            self.quit, ans = True, "n"
        if ans == "n":
            return "skipped"
        self.paths.append(ds_path.split(":", 1)[1])
        self.size += row.get("size") or 0
        return "selected"

    def submit(self, collection):
        "Submit the delete task. Returns the task ID, or None if nothing was submitted."
        n = len(self.paths)
        if not n:
            sys.stderr.write("No datasets selected for deletion.\n")
            return None
        summary = f"{n} dataset{'s' if n != 1 else ''} ({human_size(self.size)})"
        too_many = []
        if self.max_datasets is not None and n > self.max_datasets:
            too_many.append(f"more than --max-datasets {self.max_datasets}")
        if self.max_size is not None and self.size > self.max_size:
            too_many.append(f"more than --max-size {human_size(self.max_size)}")
        if too_many:
            msg = (f"Selected {summary}, {' and '.join(too_many)}. Nothing was deleted. "
                   "If this is expected, run again with a higher limit.")
            if self.dry_run:
                sys.stderr.write(f"Warning: {msg}\n")
            else:
                sys.exit(f"Error: {msg}")
        if self.interactive and not self.dry_run:
            if confirm(f"Submit one delete task for {summary}?") not in ("y", "a"):
                sys.stderr.write("Nothing deleted.\n")
                return None
        try:
            task_id = globus_delete(collection, self.paths, f"{CLEANUP_LABEL} of {n} datasets",
                                    self.dry_run, self.notify, self.ignore_missing)
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"globus delete failed: {e.stderr.strip()}\n")
            sys.exit(1)
        if self.dry_run:
            sys.stderr.write(f"Dry run: would delete {summary}.\n")
        else:
            sys.stderr.write(f"Submitted delete task {task_id} for {summary}.\n"
                             f"Check with: globus task show {task_id}\n")
        return task_id


if __name__ == "__main__":
    main()
