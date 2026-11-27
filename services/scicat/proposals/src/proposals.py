import abc
from collections import defaultdict
from datetime import datetime
from itertools import product
from json import loads
from os import environ
from urllib import request as ur

from dotenv import load_dotenv

from utils import log, retry


class Proposals(metaclass=abc.ABCMeta):
    """
    Abstract base class for fetching DUO proposals data.

    Attributes:
        duo_endpoint (str): The DUO API endpoint.
        duo_secret (str): Secret for authenticating with DUO.
        duo_facility (str): Facility identifier (e.g., SLS, SINQ).
        duo_year (Union[int, str]): Target year to fetch proposals for.
    """

    def __init__(
        self,
        duo_endpoint,
        duo_secret,
        duo_facility,
        duo_year=datetime.now().year,
    ):
        self.duo_endpoint = duo_endpoint
        self.duo_secret = duo_secret
        self.duo_facility = duo_facility
        self.duo_year = duo_year

    @classmethod
    def from_env(cls):
        """
        Instantiates a Proposals subclass using environment variables.

        Returns:
            Proposals: An instance of a subclass.
        """
        load_dotenv()
        log.info(f"Creating {cls.__name__} from env")
        return cls(
            environ["DUO_ENDPOINT"],
            environ["DUO_SECRET"],
            environ["DUO_FACILITY"],
            environ.get("DUO_YEAR", datetime.now().year),
        )

    @abc.abstractmethod
    def proposals(self):
        """
        Returns a generator of proposals with associated facility.

        Returns:
            Generator yielding tuples of (proposal, facility)
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def _type(self):
        """DUO endpoint resource type (e.g., proposals, pgroup)"""
        raise NotImplementedError

    @property
    def proposals_path(self):
        """
        Constructs the DUO proposals API path.

        Returns:
            str: API path to fetch proposals from.
        """
        return f"CalendarInfos/{self._type}"

    @retry
    def request(self, path=""):
        """
        Sends a request to the DUO API.

        Args:
            path (str): The API path to request.

        Returns:
            HTTPResponse: A response object.
        """
        _request = ur.Request(
            f"{self.duo_endpoint}/{path}",
            headers={"Cookie": f"SECRET={self.duo_secret}"},
        )
        return ur.urlopen(_request)

    def response(self, path=""):
        """
        Reads and parses JSON response from DUO.

        Args:
            path (str): The path to request.

        Returns:
            Any: Parsed JSON response.
        """
        with self.request(path) as f:
            response = f.read().decode("utf-8")
        return loads(response)


class ProposalsFromFacility(Proposals):
    """
    Fetches DUO proposals by facility.
    """

    _type = "proposals"

    def proposals(self):
        """
        Retrieves proposals grouped by facility.

        Returns:
            Generator yielding tuples of (proposal, facility)
        """
        facility = self.duo_facility
        log.info(
            f"Fetching duo proposals for {self.__class__.__name__}: {facility}, {self.duo_year}"
        )
        return product(
            self.response(f"{self.proposals_path}/{facility}?year={self.duo_year}"),
            [facility],
        )


class ProposalsFromPgroups(Proposals):
    """
    Fetches DUO proposals from pgroups that have no proposal assigned.
    """

    _type = "pgroup"

    _duo_date_format = "%Y-%m-%d"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._xname_name_map = {}

    def _pgroups_with_no_proposal(self):
        """
        Fetches pgroups without proposals.

        Returns:
            Any: List of pgroups.
        """
        log.info("Fetching pgroups with no proposals")
        return self.response(
            "PGroupAttributes/listProposalAssignments?withoutproposal=true"
        )

    @property
    def xname_name_map(self):
        """
        Maps xnames to their facility and a list of beamline-date tuples.

        Returns:
            dict: {xname: ([(name, datetime), ...], facility_name)}
        """
        if self._xname_name_map:
            return self._xname_name_map
        _xname_name_map = {}
        for facility in self.response("CalendarInfos/facilities"):
            facility_name = facility["name"]
            for beamline in facility["beamlines"]:
                mapping_key = beamline["xname"]
                try:
                    beamline_date = datetime.strptime(
                        beamline["created"], self._duo_date_format
                    )
                except ValueError:
                    beamline_date = datetime.min
                beamline_tuple = (
                    beamline["name"],
                    beamline_date,
                )
                if mapping_key in _xname_name_map:
                    _xname_name_map[mapping_key][0].append(beamline_tuple)
                else:
                    _xname_name_map[mapping_key] = (
                        [beamline_tuple],
                        facility_name,
                    )
        self._xname_name_map = _xname_name_map
        return _xname_name_map

    def _pgroup_no_proposal_formatter(self, p_group):
        """
        Converts a pgroup into a proposal-compatible structure.

        Args:
            p_group (str): The pgroup ID.

        Returns:
            tuple: A tuple of (proposal, facility)

        Raises:
            MissingOwnerError: If no owner info is available.
        """
        log.info(f"Processing {p_group} with no proposal")
        p_group = self.response(f"{self.proposals_path}/{p_group}")["group"]
        try:
            p_group["owner"]
        except KeyError as e:
            log.warning("Missing owner")
            raise MissingOwnerError from e
        beamlines, facility = self.xname_name_map[p_group["xname"]]
        beamline = self.find_relevant_beamline(p_group["created"], beamlines)
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
        log.info("Pgroup with no proposal composed")
        return proposal, facility

    def find_relevant_beamline(self, p_group_created, beamlines):
        """
        Finds the latest beamline created on or before p_group_created.

        Args:
            p_group_created (str): Creation date string.
            beamlines (list): List of (name, datetime) tuples.

        Returns:
            str: Best match beamline name or first entry as fallback.
        """
        beamline = beamlines[0][0] if beamlines else ""
        try:
            created_date = datetime.strptime(p_group_created, self._duo_date_format)
        except ValueError:
            return beamline
        max_beamline_date = datetime.min
        for name, beamline_date in beamlines:
            if max_beamline_date < beamline_date <= created_date:
                beamline = name
                max_beamline_date = beamline_date
        return beamline

    def proposals(self):
        """
        Iterates over pgroups and yields valid proposals.

        Returns:
            Generator yielding tuples of (proposal, facility)
        """
        for p_group in self._pgroups_with_no_proposal():
            try:
                yield self._pgroup_no_proposal_formatter(p_group["g"])
            except MissingOwnerError:
                continue


class MissingOwnerError(Exception):
    """
    Raised when a pgroup has no owner information.
    """

    pass


class ProposalsFactory:
    """
    Factory class that selects the appropriate Proposals subclass based on environment configuration.
    """

    _env_to_proposal_class = defaultdict(
        lambda: ProposalsFromFacility, {"pgroups": ProposalsFromPgroups}
    )

    def __new__(cls, duo_facility):
        """
        Selects a proposal class implementation based on the DUO facility.

        Args:
            duo_facility (str): DUO facility identifier.

        Returns:
            Type[Proposals]: A class inheriting from Proposals.
        """
        log.info(f"Selecting proposal class with {duo_facility}")
        proposal_class = cls._env_to_proposal_class[duo_facility]
        log.info(f"Proposal class {proposal_class} selected")
        return proposal_class

    @classmethod
    def from_env(cls):
        """
        Reads environment variables and returns the appropriate Proposals subclass.

        Returns:
            Type[Proposals]: A subclass of Proposals
        """
        load_dotenv()
        duo_facility = environ["DUO_FACILITY"]
        return cls(duo_facility)
