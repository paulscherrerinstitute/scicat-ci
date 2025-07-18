#!/usr/bin/python
"""Tool that synchronizes the proposal data for a given beamline and year
"""
import datetime
import os

from dotenv import load_dotenv
from swagger_client.rest import ApiException

from proposals import ProposalsFromFacility, ProposalsFromPgroups
from scicat import SciCatAuth, SciCatPolicyFromDuo, SciCatProposalFromDuo
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

    policy = SciCatPolicyFromDuo(row, accelerator)

    proposal = SciCatProposalFromDuo(row, accelerator, DUO_FACILITY)

    create_or_update_proposal(policy, proposal)


def create_or_update_proposal(policy, proposal):
    try:
        try:
            # check for existence of Proposal data and merge schedules into it
            proposal.update()
        except ApiException as e:
            if e.status != 404:
                raise e
            # create new proposal
            proposal.create()
            policy.create()

    except ApiException as e:
        log.error(e)


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
