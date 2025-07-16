#!/usr/bin/python
"""Tool that synchronizes the proposal data for a given beamline and year
"""
import datetime
import os

import swagger_client
from dotenv import load_dotenv
from swagger_client.rest import ApiException

from proposals import ProposalsFromFacility, ProposalsFromPgroups
from scicat import (
    SciCatAuth,
    SciCatMeasurementsFromDuo,
    SciCatPolicyFromDuo,
    SciCatProposalFromDuo,
)
from utils import log

load_dotenv()

# scicat config variables
SCICAT_ENDPOINT = os.environ["SCICAT_ENDPOINT"]
SCICAT_USERNAME = os.environ["SCICAT_USERNAME"]
SCICAT_PASSWORD = os.environ["SCICAT_PASSWORD"]

# duo config variables
DUO_ENDPOINT = os.environ["DUO_ENDPOINT"]
DUO_SECRET = os.environ["DUO_SECRET"]
DUO_YEAR = os.environ["DUO_YEAR"]
DUO_FACILITY = os.environ["DUO_FACILITY"]
PROPOSALS = {"pgroups": ProposalsFromPgroups}.get(DUO_FACILITY, ProposalsFromFacility)(
    DUO_ENDPOINT, DUO_SECRET
)


def fill_proposal(row, accelerator):
    log.info(f"============= Input proposal: {row['proposal']}")

    policy = SciCatPolicyFromDuo(row, accelerator).compose()

    proposal = SciCatProposalFromDuo(row, accelerator).compose()

    measurement_periods = SciCatMeasurementsFromDuo(
        DUO_FACILITY, row, accelerator
    ).compose()

    create_or_update_proposal(policy, proposal, measurement_periods)


def create_or_update_proposal(policy, proposal, measurement_periods):
    try:
        # check for existence of Proposal data and merge schedules into it
        pid = proposal["proposalId"]
        try:
            existing_proposal = swagger_client.ProposalApi().proposal_find_by_id(pid)
            # check if this is a new entry
            ml = existing_proposal.measurement_period_list
            # to avoid problems with Dates: convert Dates back to strings
            new_entries = compose_new_measurement_periods(measurement_periods, pid, ml)
            if len(new_entries) == 0:
                return
            patch = {"MeasurementPeriodList": new_entries}
            log.info(f"Modified proposal, patch object: {patch}")
            # the following call appends to the existing array
            swagger_client.ProposalApi().proposal_prototype_patch_attributes(
                pid, data=patch
            )
        except ApiException as e:
            if e.status != 404:
                raise e
            # create new proposal
            proposal["MeasurementPeriodList"] = measurement_periods
            log.info(f"Create new proposal {proposal}")
            swagger_client.ProposalApi().proposal_create(data=proposal)
            log.info(f"Create new policy for pgroup {policy}")
            swagger_client.PolicyApi().policy_create(data=policy)

    except ApiException as e:
        log.error(e)


def compose_new_measurement_periods(measurement_periods, pid, ml):
    existing_measurements_dict = {f"{m.instrument}_{m.start}_{m.end}": m for m in ml}
    new_entries = []
    for new_entry in measurement_periods:
        if (
            f"{new_entry['instrument']}_{new_entry['start']}_{new_entry['end']}"
            in existing_measurements_dict
        ):
            log.info("This entry exists already, nothing appended")
            continue
        log.info(f"Merge calendar entry to existing proposal data {pid}, {new_entry}")
        new_entries.append(new_entry)
    return new_entries


def main() -> None:
    year = DUO_YEAR or datetime.datetime.now().year
    log.info(f"Fetching proposals for accelerator {DUO_FACILITY} and year {year}")
    log.info(f"Connecting to scicat on {SCICAT_ENDPOINT}")

    SciCatAuth(SCICAT_USERNAME, SCICAT_PASSWORD, SCICAT_ENDPOINT).authenticate()

    # read proposal data from DUO

    for proposal, facility in PROPOSALS.proposals(DUO_FACILITY, year):
        fill_proposal(proposal, facility)


if __name__ == "__main__":
    main()
