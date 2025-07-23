#!/usr/bin/python
"""
Entry point for syncing DUO proposals into SciCat.

This script initializes the DuoSciCatOrchestrator and triggers the orchestration
process to ensure proposals and policies are synchronized from DUO into the SciCat
data catalog.

Usage:
    python main.py
"""

from orchestrator import DuoSciCatOrchestrator


def main():
    """
    Initializes and executes the DuoSciCatOrchestrator.

    This function loads configuration from the environment,
    prepares data sources, and triggers synchronization logic.
    """
    DuoSciCatOrchestrator().orchestrate()


if __name__ == "__main__":
    main()
