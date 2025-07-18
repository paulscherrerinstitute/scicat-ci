import abc
from collections import defaultdict
from itertools import product
from json import loads
from os import environ
from urllib import request as ur

from dotenv import load_dotenv

from utils import retry


class Proposals(metaclass=abc.ABCMeta):
    def __init__(self, duo_endpoint, duo_secret):
        self.duo_endpoint = duo_endpoint
        self.duo_secret = duo_secret

    @classmethod
    def from_env(cls):
        load_dotenv()
        return cls(environ["DUO_ENDPOINT"], environ["DUO_SECRET"])

    @abc.abstractmethod
    def proposals(self, *args, **kwargs):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def _type(self):
        raise NotImplementedError

    @property
    def proposals_path(self):
        return f"CalendarInfos/{self._type}"

    @retry
    def request(self, path=""):
        _request = ur.Request(
            f"{self.duo_endpoint}/{path}",
            headers={"Cookie": f"SECRET={self.duo_secret}"},
        )
        return ur.urlopen(_request)

    def response(self, path=""):
        with self.request(path) as f:
            response = f.read().decode("utf-8")
        return loads(response)


class ProposalsFromFacility(Proposals):
    _type = "proposals"

    def proposals(self, facility, year):
        return product(
            self.response(f"{self.proposals_path}/{facility}?year={year}"), [facility]
        )


class ProposalsFromPgroups(Proposals):
    _type = "pgroup"

    def __init__(self, duo_endpoint, duo_secret):
        super().__init__(duo_endpoint, duo_secret)
        self._xname_name_map = {}

    def _pgroups_with_no_proposal(self):
        return self.response(
            "PGroupAttributes/listProposalAssignments?withoutproposal=true"
        )

    @property
    def xname_name_map(self):
        _xname_name_map = self._xname_name_map or {
            beamline["xname"]: (beamline["name"], facility["name"])
            for facility in self.response("CalendarInfos/facilities")
            for beamline in facility["beamlines"]
        }
        self._xname_name_map = _xname_name_map
        return _xname_name_map

    def _pgroup_no_proposal_formatter(self, p_group):
        p_group = self.response(f"{self.proposals_path}/{p_group}")["group"]
        try:
            p_group["owner"]
        except KeyError as e:
            raise MissingOwnerError from e
        beamline, facility = self.xname_name_map[p_group["xname"]]
        proposal = {
            "proposal": p_group["name"],
            "email": p_group["owner"]["email"],
            "pi_email": "",
            "pgroup": p_group["name"],
            "beamline": beamline,
            "pi_firstname": p_group["owner"]["firstname"],
            "pi_lastname": p_group["owner"]["lastname"],
            "firstname": p_group["owner"]["firstname"],
            "lastname": p_group["owner"]["lastname"],
            "title": "",
            "abstract": "",
            "schedule": [
                {"start": "01/01/1960 01:00:00", "end": "31/12/2100 01:00:00"}
            ],
        }
        return proposal, facility

    def proposals(self, *args, **kwargs):
        for p_group in self._pgroups_with_no_proposal():
            try:
                yield self._pgroup_no_proposal_formatter(p_group["g"])
            except MissingOwnerError:
                continue


class MissingOwnerError(Exception):
    pass


class ProposalsFactory:

    _env_to_proposal_class = defaultdict(
        lambda: ProposalsFromFacility, {"pgroups": ProposalsFromPgroups}
    )

    def __new__(cls, duo_facility):
        return cls._env_to_proposal_class[duo_facility]

    @classmethod
    def from_env(cls):
        load_dotenv()
        duo_facility = environ["DUO_FACILITY"]
        return cls(duo_facility)
