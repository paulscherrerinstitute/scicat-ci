#!/usr/bin/python
"""Tool that synchronizes the proposal data for a given beamline and year
"""
import datetime
import os
import uuid
from collections import defaultdict

import pytz
import swagger_client
from dotenv import load_dotenv
from swagger_client.configuration import Configuration
from swagger_client.rest import ApiException

from proposals import ProposalsFromFacility, ProposalsFromPgroups
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

    principal_investigator = compose_principal_investigator(row)

    policy = compose_policy(row, accelerator, principal_investigator)

    proposal = compose_proposal(row, principal_investigator, policy)

    measurement_periods = compose_measurement_periods(row, accelerator)

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
                log.info(f"entry.start: {entry.start}")
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
                        log.info("This entry exists already, nothing appended")
                        is_new = False
                        break
                if is_new:
                    log.info(
                        f"Merge calendar entry to existing proposal data {pid}, {new_entry}"
                    )
                    new_entries.append(new_entry)
            if len(new_entries) > 0:
                patch = {}
                patch["MeasurementPeriodList"] = new_entries
                log.info(f"Modified proposal, patch object: {patch}")
                # the following call appends to the existing array
                swagger_client.ProposalApi().proposal_prototype_patch_attributes(
                    pid, data=patch
                )
        else:
            # create new proposal
            proposal["MeasurementPeriodList"] = measurement_periods
            log.info(f"Create new proposal {proposal}")
            swagger_client.ProposalApi().proposal_create(data=proposal)
            log.info(f"Create new policy for pgroup {policy}")
            swagger_client.PolicyApi().policy_create(data=policy)
    except ApiException as e:
        log.error(e)


def compose_measurement_periods(row, accelerator):
    measurement_periods = []
    schedules = row["schedule"]
    for schedule in schedules:
        mp = compose_measurement_period(row, accelerator, schedule)
        measurement_periods.append(mp)
    return measurement_periods


def compose_measurement_period(
    row,
    accelerator,
    schedule,
    duo_facility=DUO_FACILITY,
):
    local = pytz.timezone("Europe/Amsterdam")
    duo_facility_datetime_format = defaultdict(
        lambda: "%d/%m/%Y %H:%M:%S", {"sinq": "%d/%m/%Y", "smus": "%d/%m/%Y"}
    )
    mp = {}
    mp["id"] = uuid.uuid4().hex
    mp["instrument"] = f'/PSI/{accelerator.upper()}/{row["beamline"].upper()}'
    # convert date to format according 5.6 internet date/time format in RFC 3339"
    # i.e. from "20/12/2013 07:00:00" to "2013-12-20T07:00:00+01:00"
    start_naive = datetime.datetime.strptime(
        schedule["start"], duo_facility_datetime_format[duo_facility]
    )
    local_start = local.localize(start_naive, is_dst=True)
    # no point to use local here, because this information get lost when data is stored
    utc_start = local_start.astimezone(pytz.utc)
    mp["start"] = utc_start.isoformat("T")
    # do not convert to string here for better comparison with existing entries
    # mp['start'] = utc_start

    end_naive = datetime.datetime.strptime(
        schedule["end"], duo_facility_datetime_format[duo_facility]
    )
    local_end = local.localize(end_naive, is_dst=True)
    utc_end = local_end.astimezone(pytz.utc)
    mp["end"] = utc_end.isoformat("T")
    # mp['end']=utc_end
    mp["comment"] = ""
    return mp


def compose_proposal(row, principal_investigator, accelerator):
    proposal = {}
    proposal["proposalId"] = f'20.500.11935/{row["proposal"]}'
    proposal["pi_email"] = principal_investigator
    proposal["pi_firstname"] = row["pi_firstname"]
    proposal["pi_lastname"] = row["pi_lastname"]
    proposal["email"] = row["email"]
    if row["email"] == "":
        log.warning(f"Empty email: {row}")

    proposal["firstname"] = row["firstname"]
    proposal["lastname"] = row["lastname"]
    proposal["title"] = row["title"]
    proposal["abstract"] = row["abstract"]
    proposal["ownerGroup"] = compose_owner_group(row)
    proposal["accessGroups"] = compose_access_groups(row, accelerator)
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
    policy["ownerGroup"] = compose_owner_group(row)
    # TODO for SINQ (? still correct ?)
    # policy['ownerGroup'] = 'p'+row['proposal']
    # special mapping for MX needed
    policy["accessGroups"] = compose_access_groups(row, accelerator)
    return policy


def compose_owner_group(row):
    return row["pgroup"] or f'p{row["proposal"]}'


def compose_access_groups(row, accelerator):
    bl = row["beamline"].lower()
    if bl.startswith("px"):
        bl = "mx"
    return [f"{accelerator}{bl}"]


def compose_principal_investigator(row):
    return row["pi_email"] or row["email"]


def _get_scicat_token(scicat_username, scicat_password) -> str:
    credentials = {}
    credentials["username"] = scicat_username
    credentials["password"] = scicat_password
    try:
        response = swagger_client.UserApi().user_login(credentials)
        access_token = response["id"]
        return access_token
    except Exception as e:
        log.error("Login to data catalog did not succeed")
        raise e


def _set_scicat_token(
    scicat_username=SCICAT_USERNAME,
    scicat_password=SCICAT_PASSWORD,
    scicat_endpoint=SCICAT_ENDPOINT,
):
    Configuration().host = scicat_endpoint

    # set token for auth header - scicat
    access_token = _get_scicat_token(scicat_username, scicat_password)
    Configuration().api_client.default_headers["Authorization"] = access_token


def main() -> None:
    year = DUO_YEAR or datetime.datetime.now().year
    log.info(f"Fetching proposals for accelerator {DUO_FACILITY} and year {year}")
    log.info(f"Connecting to scicat on {SCICAT_ENDPOINT}")

    _set_scicat_token()

    # read proposal data from DUO

    for proposal, facility in PROPOSALS.proposals(DUO_FACILITY, year):
        fill_proposal(proposal, facility)


if __name__ == "__main__":
    main()
