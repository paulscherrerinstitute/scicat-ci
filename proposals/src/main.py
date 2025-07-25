#!/usr/bin/python
"""Tool that synchronizes the proposal data for a given beamline and year
"""

from orchestrator import DuoSciCatOrchestrator


def main() -> None:
    DuoSciCatOrchestrator().orchestrate()


if __name__ == "__main__":
    main()
