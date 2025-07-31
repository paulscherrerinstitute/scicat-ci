import datetime
import uuid
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from os import environ

import pytz
from dotenv import load_dotenv
from swagger_client import Configuration, PolicyApi, ProposalApi, UserApi
from swagger_client.rest import ApiException

from utils import log


class SciCatAuth:
    """
    Handles authentication with the SciCat API.

    Attributes:
        username (str): Username for SciCat.
        password (str): Password for SciCat.
        url (str): SciCat endpoint URL.
    """

    def __init__(self, username, password, url):
        self.username = username
        self.password = password
        self.url = url

    @classmethod
    def from_env(cls):
        """Creates a SciCatAuth instance from environment variables."""
        load_dotenv()
        log.info("Loading scicat env vars")
        return cls(
            environ["SCICAT_USERNAME"],
            environ["SCICAT_PASSWORD"],
            environ["SCICAT_ENDPOINT"],
        )

    def authenticate(self):
        """Authenticates with SciCat and sets the token in the API client."""
        self._set_scicat_token()

    def _get_scicat_token(self):
        """Retrieves the authentication token from SciCat."""
        credentials = {"username": self.username, "password": self.password}
        try:
            response = UserApi().user_login(credentials)
            access_token = response["id"]
            return access_token
        except Exception as e:
            log.error("Login to data catalog did not succeed")
            raise e

    def _set_scicat_token(self):
        """Sets the SciCat token in the Swagger client configuration."""
        Configuration().host = self.url
        access_token = self._get_scicat_token()
        log.info("SciCat authentication successuful, setting access_token")
        Configuration().api_client.default_headers["Authorization"] = access_token


class SciCatFromDuo(metaclass=ABCMeta):
    """
    Abstract base class for creating SciCat entries from DUO proposals.

    Attributes:
        duo_proposal (dict): The DUO proposal data.
        accelerator (str): The accelerator identifier.
    """

    def __init__(self, duo_proposal, accelerator):
        self.accelerator = accelerator
        self.duo_proposal = duo_proposal

    @abstractmethod
    def compose(self):
        """Composes the SciCat object from DUO proposal."""
        raise NotImplementedError

    @abstractmethod
    def create(self):
        """Creates the SciCat object in the SciCat database."""
        raise NotImplementedError


class SciCatCreatorFromDuoMixin:
    """Mixin for shared DUO to SciCat property mappings."""

    @property
    def principal_investigator(self):
        """Returns the principal investigator email."""
        row = self.duo_proposal
        return row["pi_email"] or row["email"]

    @property
    def owner_group(self):
        """Returns the owner group string."""
        row = self.duo_proposal
        return row["pgroup"] or f'p{row["proposal"]}'

    @property
    def access_groups(self):
        """Returns a list of access groups."""
        row = self.duo_proposal
        bl = row["beamline"].lower()
        if bl.startswith("px"):
            bl = "mx"
        return [f"{self.accelerator}{bl}"]


class SciCatPolicyFromDuo(SciCatFromDuo, SciCatCreatorFromDuoMixin):
    """Handles the creation of SciCat policy entries from DUO proposals."""

    def compose(self):
        """Composes the policy dictionary for SciCat."""
        log.info("Composing SciCat policy from duo proposal")
        policy = {
            "manager": [self.principal_investigator],
            "tapeRedundancy": "low",
            "autoArchive": False,
            "autoArchiveDelay": 0,
            "archiveEmailNotification": True,
            "archiveEmailsToBeNotified": [],
            "retrieveEmailNotification": True,
            "retrieveEmailsToBeNotified": [],
            "embargoPeriod": 3,
            "ownerGroup": self.owner_group,
            # TODO for SINQ (? still correct ?)
            # policy['ownerGroup'] = 'p'+row['proposal']
            # special mapping for MX needed
            "accessGroups": self.access_groups,
        }
        log.info("SciCat policy composed")
        return policy

    def create(self):
        """Creates the SciCat policy using the composed policy dictionary."""
        policy = self.compose()
        log.info(f"Create new policy for pgroup {policy}")
        PolicyApi().policy_create(data=policy)
        log.info("Policy created")


class SciCatMeasurementsFromDuoMixin:
    """Mixin for converting DUO proposal schedules to SciCat measurement periods."""

    _local = pytz.timezone("Europe/Amsterdam")
    _duo_facility_datetime_format = defaultdict(
        lambda: "%d/%m/%Y %H:%M:%S", {"sinq": "%d/%m/%Y", "smus": "%d/%m/%Y"}
    )

    @property
    def duo_facility_datetime_format(self):
        """Returns the datetime format for the DUO facility."""
        return self._duo_facility_datetime_format[self.duo_facility]

    def compose_measurement_period(self, schedule):
        """Composes a measurement period dict from schedule.

        Args:
            schedule (dict): Schedule with 'start' and 'end' keys.

        Returns:
            dict: SciCat-formatted measurement period.
        """
        row = self.duo_proposal
        return {
            "id": uuid.uuid4().hex,
            "instrument": f'/PSI/{self.accelerator.upper()}/{row["beamline"].upper()}',
            "start": self._datetime_to_utc(schedule["start"]),
            "end": self._datetime_to_utc(schedule["end"]),
            "comment": "",
        }

    def _datetime_to_utc(self, schedule_date):
        """Converts a local datetime string to UTC ISO format.

        Args:
            schedule_date (str): The date string to convert.

        Returns:
            str: ISO 8601 formatted UTC datetime.
        """
        date_naive = datetime.datetime.strptime(
            schedule_date, self.duo_facility_datetime_format
        )
        local_date = self._local.localize(date_naive, is_dst=True)
        utc_date = local_date.astimezone(pytz.utc)
        return utc_date.isoformat("T")

    @property
    def measurement_period_list(self):
        """Generates a list of measurement periods from the proposal schedule."""
        log.info("Extracting measurement periods from proposal")
        row = self.duo_proposal
        measurement_periods = []
        schedules = row["schedule"]
        for schedule in schedules:
            mp = self.compose_measurement_period(schedule)
            measurement_periods.append(mp)
        log.info("Measurement periods from proposal extracted")
        return measurement_periods

    def keep_new_measurements(self, measurements):
        """Filters out measurement periods already present in SciCat.

        Args:
            measurements (list): Existing SciCat measurement periods.

        Returns:
            list[dict]: New measurement periods not in existing ones.
        """
        log.info("Excluding already existing proposals")
        existing_measurements_dict = {
            f"{m.instrument}_{m.start}_{m.end}": m for m in measurements
        }
        new_entries = []
        for new_entry in self.measurement_period_list:
            if (
                f"{new_entry['instrument']}_{new_entry['start']}_{new_entry['end']}"
                in existing_measurements_dict
            ):
                log.info("This entry exists already, nothing appended")
                continue
            log.info(f"Merge calendar entry to existing proposal data {new_entry}")
            new_entries.append(new_entry)
        log.info("Existing proposals excluded")
        return new_entries


class SciCatProposalFromDuo(
    SciCatFromDuo, SciCatCreatorFromDuoMixin, SciCatMeasurementsFromDuoMixin
):
    """
    Handles creation and update of SciCat proposals from DUO proposals.

    Attributes:
        duo_proposal (dict): DUO proposal data.
        accelerator (str): Accelerator ID.
        duo_facility (str): DUO facility identifier.
    """

    class ProposalNotFoundException(Exception):
        """Raised when a SciCat proposal is not found."""

        pass

    def __init__(self, duo_proposal, accelerator, duo_facility):
        super().__init__(duo_proposal, accelerator)
        self.duo_facility = duo_facility

    def compose(self):
        """Composes the SciCat proposal dictionary from DUO data."""
        log.info("Composing SciCat proposal from duo proposal")
        row = self.duo_proposal
        if not row["email"]:
            log.warning(f"Empty email: {row}")
        proposal = {
            "proposalId": f'20.500.11935/{row["proposal"]}',
            "pi_email": self.principal_investigator,
            "pi_firstname": row["pi_firstname"],
            "pi_lastname": row["pi_lastname"],
            "email": row["email"],
            "firstname": row["firstname"],
            "lastname": row["lastname"],
            "title": row["title"],
            "abstract": row["abstract"],
            "ownerGroup": self.owner_group,
            "accessGroups": self.access_groups,
            "MeasurementPeriodList": self.measurement_period_list,
        }
        log.info("SciCat proposal composed")
        return proposal

    def create(self):
        """Creates a new SciCat proposal."""
        proposal = self.compose()
        log.info(f"Creating new proposal {proposal}")
        ProposalApi().proposal_create(data=proposal)
        log.info("Proposal created")

    def _update(self):
        """Updates an existing SciCat proposal by appending new measurement periods."""
        proposal = self.compose()
        pid = proposal["proposalId"]
        log.info(f"Checking if proposal {pid} exists in SciCat")
        existing_proposal = ProposalApi().proposal_find_by_id(pid)
        existing_measurements = existing_proposal.measurement_period_list
        new_entries = self.keep_new_measurements(existing_measurements)
        if len(new_entries) == 0:
            return
        patch = {"MeasurementPeriodList": new_entries}
        log.info(f"Modifying proposal, patch object: {patch}")
        ProposalApi().proposal_prototype_patch_attributes(pid, data=patch)
        log.info("Proposal modified")

    def update(self):
        """Public method to update a proposal; raises if not found."""
        try:
            self._update()
        except ApiException as e:
            if e.status == 404:
                log.info("Proposal does not exist in SciCat")
                raise self.ProposalNotFoundException
            raise e
