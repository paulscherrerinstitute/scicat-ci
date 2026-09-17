#!/usr/bin/python
"""
Entry point for the dataset retention cronjob.

This script checks SciCat jobs of type "markedForDeletion" and advances (or
cancels) their retention countdown, one step towards the eventual hard
deletion of the underlying datasets.

Usage:
    python main.py
"""

from orchestrator import RetentionOrchestrator


def main():
    """Initializes and runs the RetentionOrchestrator."""
    RetentionOrchestrator().orchestrate()


if __name__ == "__main__":
    main()
