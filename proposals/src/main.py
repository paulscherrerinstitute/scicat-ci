#!/usr/bin/python
"""Tool that synchronizes the proposal data for a given beamline and year
"""
import datetime
import os
import sys
import uuid
from collections import defaultdict

import pytz
import swagger_client
from dotenv import load_dotenv
from swagger_client.configuration import Configuration
from swagger_client.rest import ApiException

from proposals import ProposalsFromFacility, ProposalsFromPgroups

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
DUO_FACILITY_DATETIME_FORMAT = defaultdict(
    lambda: "%d/%m/%Y %H:%M:%S", {"sinq": "%d/%m/%Y", "smus": "%d/%m/%Y"}
)
PROPOSALS = {"pgroups": ProposalsFromPgroups}.get(DUO_FACILITY, ProposalsFromFacility)(
    DUO_ENDPOINT, DUO_SECRET
)

local = pytz.timezone("Europe/Amsterdam")


def fill_proposal(row, accelerator):
    print("============= Input proposal:", row["proposal"])

    principal_investigator = compose_principal_investigator(row)

    policy = compose_policy(row, accelerator, principal_investigator)

    # print("Policy:",policy)

    proposal = compose_proposal(row, principal_investigator, policy)

    measurement_periods = compose_measurement_periods(row, accelerator)

    # print("========= New measuring periods:",measurementPeriods)
    create_or_update_proposal(policy, proposal, measurement_periods)


def create_or_update_proposal(policy, proposal, measurement_periods):
    api = swagger_client.ProposalApi()
    try:
        # check for existence of Proposal data and merge schedules into it
        pid = proposal["proposalId"]
        res = api.proposal_exists_get_proposalsid_exists(pid)
        if res.exists:
            existing_proposal = api.proposal_find_by_id(pid)
            # check if this is a new entry
            ml = existing_proposal.measurement_period_list
            # to avoid problems with Dates: convert Dates back to strings
            existing_entries = []
            for entry in ml:
                existing_entry = {}
                print("entry.start:", entry.start)
                existing_entry["start"] = entry.start  # .isoformat("T")
                existing_entry["end"] = entry.end  # .isoformat("T")
                existing_entry["instrument"] = entry.instrument
                existing_entries.append(existing_entry)
            # now check which of new measurement periods are really new
            new_entries = []
            for new_entry in measurement_periods:
                is_new = True
                for entry in existing_entries:
                    if (
                        entry["start"] == new_entry["start"]
                        and entry["end"] == new_entry["end"]
                        and entry["instrument"] == new_entry["instrument"]
                    ):
                        print("This entry exists already, nothing appended")
                        is_new = False
                        break
                if is_new:
                    print(
                        "Merge calendar entry to existing proposal data", pid, new_entry
                    )
                    new_entries.append(new_entry)
            if len(new_entries) > 0:
                patch = {}
                patch["MeasurementPeriodList"] = new_entries
                print("Modified proposal, patch object:", patch)
                # the following call appends to the existing array
                swagger_client.ProposalApi().proposal_prototype_patch_attributes(
                    pid, data=patch
                )
        else:
            # create new proposal
            proposal["MeasurementPeriodList"] = measurement_periods
            print("Create new proposal", proposal)
            swagger_client.ProposalApi().proposal_create(data=proposal)
            print("Create new policy for pgroup ", policy)
            swagger_client.PolicyApi().policy_create(data=policy)
    except ApiException as e:
        print(e)


def compose_measurement_periods(row, accelerator):
    measurement_periods = []
    schedules = row["schedule"]
    for schedule in schedules:
        mp = compose_measurement_period(row, accelerator, schedule)
        measurement_periods.append(mp)
    return measurement_periods


def compose_measurement_period(row, accelerator, schedule):
    mp = {}
    mp["id"] = uuid.uuid4().hex
    mp["instrument"] = f'/PSI/{accelerator.upper()}/{row["beamline"].upper()}'
    # convert date to format according 5.6 internet date/time format in RFC 3339"
    # i.e. from "20/12/2013 07:00:00" to "2013-12-20T07:00:00+01:00"
    start_naive = datetime.datetime.strptime(
        schedule["start"], DUO_FACILITY_DATETIME_FORMAT[DUO_FACILITY]
    )
    local_start = local.localize(start_naive, is_dst=True)
    # no point to use local here, because this information get lost when data is stored
    utc_start = local_start.astimezone(pytz.utc)
    mp["start"] = utc_start.isoformat("T")
    # do not convert to string here for better comparison with existing entries
    # mp['start'] = utc_start

    end_naive = datetime.datetime.strptime(
        schedule["end"], DUO_FACILITY_DATETIME_FORMAT[DUO_FACILITY]
    )
    local_end = local.localize(end_naive, is_dst=True)
    utc_end = local_end.astimezone(pytz.utc)
    mp["end"] = utc_end.isoformat("T")
    # mp['end']=utc_end
    mp["comment"] = ""
    return mp


def compose_proposal(row, principal_investigator, policy):
    proposal = {}
    proposal["proposalId"] = f'20.500.11935/{row["proposal"]}'
    proposal["pi_email"] = principal_investigator
    proposal["pi_firstname"] = row["pi_firstname"]
    proposal["pi_lastname"] = row["pi_lastname"]
    proposal["email"] = row["email"]
    if row["email"] == "":
        print("Empty email:", row)

    proposal["firstname"] = row["firstname"]
    proposal["lastname"] = row["lastname"]
    proposal["title"] = row["title"]
    proposal["abstract"] = row["abstract"]
    proposal["ownerGroup"] = policy["ownerGroup"]
    proposal["accessGroups"] = policy["accessGroups"]
    return proposal


def compose_policy(row, accelerator, principal_investigator):
    policy = {}
    policy["manager"] = [principal_investigator]
    policy["tapeRedundancy"] = "low"
    policy["autoArchive"] = False
    policy["autoArchiveDelay"] = 0
    policy["archiveEmailNotification"] = True
    policy["archiveEmailsToBeNotified"] = []
    policy["retrieveEmailNotification"] = True
    policy["retrieveEmailsToBeNotified"] = []
    policy["embargoPeriod"] = 3
    policy["ownerGroup"] = row["pgroup"] or f'p{row["proposal"]}'
    # TODO for SINQ (? still correct ?)
    # policy['ownerGroup'] = 'p'+row['proposal']
    # special mapping for MX needed
    bl = row["beamline"].lower()
    if bl.startswith("px"):
        bl = "mx"
    policy["accessGroups"] = [f"{accelerator}{bl}"]
    return policy


def compose_principal_investigator(row):
    main_proposer_email = row["email"]
    if row["pi_email"] != "":
        principal_investigator = row["pi_email"]
    else:
        principal_investigator = main_proposer_email
    return principal_investigator


def _get_scicat_token() -> str:
    credentials = {}
    credentials["username"] = SCICAT_USERNAME
    credentials["password"] = SCICAT_PASSWORD
    try:
        response = swagger_client.UserApi().user_login(credentials)
        access_token = response["id"]
        print(access_token)
        return access_token
    except Exception:
        print("Login to data catalog did not succeed")
        sys.exit(1)


def _set_scicat_token():
    Configuration().host = SCICAT_ENDPOINT

    # set token for auth header - scicat
    access_token = _get_scicat_token()
    Configuration().api_client.default_headers["Authorization"] = access_token


def main() -> None:
    year = DUO_YEAR or datetime.datetime.now().year
    print("Fetching proposals for accelerator ", DUO_FACILITY, " and year ", year)
    print("Connecting to scicat on ", SCICAT_ENDPOINT)

    _set_scicat_token()

    # read proposal data from DUO

    for proposal, facility in PROPOSALS.proposals(DUO_FACILITY, year):
        fill_proposal(proposal, facility)


if __name__ == "__main__":
    main()
