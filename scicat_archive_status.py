#!/usr/bin/env python3
"""Report SciCat size / archivable / retrievable for datasets found on a Globus collection.

Each subdirectory of e.g. $GLOBUS_PSI_QA:/archive/20-500-11935/ is a dataset UUID; the
SciCat PID is "<prefix with dots>/<uuid>", e.g. 20.500.11935/07e6926a-....

Requirements: `globus` CLI (logged in), `requests`.

Usage:
    export SCICAT_BACKEND=https://dacat-qa.psi.ch      # SciCat backend base URL
    export SCICAT_TOKEN=...                         # SciCat access token
    python scicat_archive_status.py "$GLOBUS_PSI_QA:/archive/20-500-11935/"
    python scicat_archive_status.py "$GLOBUS_PSI_QA:/archive/20-500-11935/" --globus-size --csv out.csv
"""
import argparse
import csv
import json
import os
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

def get_dataset(session, base_url, pid):
    "Get a dataset from scicat"
    url = f"{base_url.rstrip('/')}/api/v4/datasets/{quote(pid, safe='')}"
    r = session.get(url, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json() or None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default="/archive", help="Globus path to the dataset location")
    ap.add_argument("--collection", default=os.environ.get("GLOBUS_COLLECTION"), help="Globus collection id")
    ap.add_argument("--scicat-url", default=os.environ.get("SCICAT_BACKEND"))
    ap.add_argument("--token", default=os.environ.get("SCICAT_TOKEN"))
    ap.add_argument("--prefix", default="20.500.11935", help="PID prefix")
    ap.add_argument("--globus-size", action="store_true", help="also sum file sizes on Globus")
    ap.add_argument("--csv", help="write results to this CSV file")
    args = ap.parse_args()
    if not args.scicat_url:
        ap.error("set --scicat-url or SCICAT_BACKEND")
    if not args.collection:
        ap.error("set --collection or GLOBUS_COLLECTION")
    if not args.token:
        ap.error("set --token or SCICAT_TOKEN")


    s = requests.Session()
    if args.token:
        s.headers["Authorization"] = f"Bearer {args.token}"

    # Construct path to the globus directory
    prefix = args.prefix
    path = "{collection}:{path}/{prefix}".format(
        collection=args.collection,
        path=args.path.rstrip("/"),
        prefix=pid_to_path(prefix),
    )
    cols = ["pid", "size", "files", "archivable", "retrievable", "archiveStatus", "retrieveStatus"]
    if args.globus_size:
        cols.append("globus_size")
    cols.append("error")

    out = open(args.csv, "w", newline="") if args.csv else sys.stdout
    try:
        w = csv.DictWriter(out, fieldnames=cols, delimiter="," if args.csv else "\t")
        w.writeheader()
        out.flush()
        for row in iter_rows(s, args, path, prefix):
            w.writerow(row)
            out.flush()
    finally:
        if out is not sys.stdout:
            out.close()


def iter_rows(s, args, path, prefix):
    "Yield one result row per dataset directory on Globus"
    for entry in globus_ls(path):
        if entry.get("type") != "dir":
            continue
        uuid = entry["name"].rstrip("/")
        pid = f"{prefix}/{uuid}"
        row = {"pid": pid}
        try:
            ds = get_dataset(s, args.scicat_url, pid)
        except requests.RequestException as e:
            ds, row["error"] = None, str(e)
        if ds is None:
            row.setdefault("error", "not found in SciCat")
        else:
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
                row["globus_size"] = globus_size(f"{path}/{uuid}/")
            except subprocess.CalledProcessError as e:
                row["globus_size"] = None
                row["error"] = (row.get("error", "") + " globus: " + e.stderr.strip()).strip()
        yield row


if __name__ == "__main__":
    main()
