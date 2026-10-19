#!/usr/bin/python
"""
Entry point for the dataset retention cronjobs.

Commands:
    retention     checks SciCat jobs of type "markedForDeletion" and advances
                  their retention countdown, one step towards the eventual
                  hard deletion of the underlying datasets, and notifies the
                  "revertMarkForDeletion" jobs (default)
    mark-expired  submits "markedForDeletion" jobs, with deletionCode EXPIRED,
                  for the datasets whose archive retention time has passed

Usage:
    python main.py [retention|mark-expired]
"""

import argparse

from orchestrator import MarkExpiredOrchestrator, RetentionOrchestrator


def main(argv=None):
    """Initializes and runs the orchestrator of the given command."""
    orchestrators = {
        "retention": RetentionOrchestrator,
        "mark-expired": MarkExpiredOrchestrator,
    }
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "command", nargs="?", default="retention", choices=orchestrators
    )
    args = parser.parse_args(argv)
    orchestrators[args.command]().orchestrate()


if __name__ == "__main__":
    main()
