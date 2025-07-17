import datetime
import uuid
from abc import ABCMeta
from collections import defaultdict

import pytz
from swagger_client import Configuration, UserApi

from utils import log


class SciCatAuth:

    def __init__(self, username, password, url):
        self.username = username
        self.password = password
        self.url = url

    def authenticate(self):
        self._set_scicat_token()

    def _get_scicat_token(self):
        credentials = {"username": self.username, "password": self.password}
        try:
            response = UserApi().user_login(credentials)
            access_token = response["id"]
            return access_token
        except Exception as e:
            log.error("Login to data catalog did not succeed")
            raise e

    def _set_scicat_token(
        self,
    ):
        Configuration().host = self.url
        access_token = self._get_scicat_token()
        Configuration().api_client.default_headers["Authorization"] = access_token


class SciCatFromDuo(metaclass=ABCMeta):
    def __init__(self, duo_proposal, accelerator):
        self.accelerator = accelerator
        self.duo_proposal = duo_proposal


class SciCatCreatorFromDuoMixin:

    @property
    def principal_investigator(self):
        row = self.duo_proposal
        return row["pi_email"] or row["email"]

    @property
    def owner_group(self):
        row = self.duo_proposal
        return row["pgroup"] or f'p{row["proposal"]}'

    @property
    def access_groups(self):
        row = self.duo_proposal
        bl = row["beamline"].lower()
        if bl.startswith("px"):
            bl = "mx"
        return [f"{self.accelerator}{bl}"]


class SciCatProposalFromDuo(SciCatFromDuo, SciCatCreatorFromDuoMixin):

    def compose_proposal(self):
        row = self.duo_proposal
        if not row["email"]:
            log.warning(f"Empty email: {row}")
        return {
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
        }


class SciCatPolicyFromDuo(SciCatFromDuo, SciCatCreatorFromDuoMixin):

    def compose_policy(self):
        return {
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


class SciCatMeasurementsFromDuo(SciCatFromDuo):

    _local = pytz.timezone("Europe/Amsterdam")
    _duo_facility_datetime_format = defaultdict(
        lambda: "%d/%m/%Y %H:%M:%S", {"sinq": "%d/%m/%Y", "smus": "%d/%m/%Y"}
    )

    def __init__(self, duo_facility, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duo_facility = duo_facility

    @property
    def duo_facility_datetime_format(self):
        return self._duo_facility_datetime_format[self.duo_facility]

    def compose_measurement_period(
        self,
        schedule,
    ):
        row = self.duo_proposal
        return {
            "id": uuid.uuid4().hex,
            "instrument": f'/PSI/{self.accelerator.upper()}/{row["beamline"].upper()}',
            "start": self._datetime_to_utc(schedule["start"]),
            "end": self._datetime_to_utc(schedule["end"]),
            "comment": "",
        }

    def _datetime_to_utc(self, schedule_date):
        # convert date to format according 5.6 internet date/time format in RFC 3339"
        # i.e. from "20/12/2013 07:00:00" to "2013-12-20T07:00:00+01:00"
        date_naive = datetime.datetime.strptime(
            schedule_date, self.duo_facility_datetime_format
        )
        local_date = self._local.localize(date_naive, is_dst=True)
        # no point to use local here, because this information get lost when data is stored
        utc_date = local_date.astimezone(pytz.utc)
        return utc_date.isoformat("T")

    def compose_measurement_periods(self):
        row = self.duo_proposal
        measurement_periods = []
        schedules = row["schedule"]
        for schedule in schedules:
            mp = self.compose_measurement_period(schedule)
            measurement_periods.append(mp)
        return measurement_periods
