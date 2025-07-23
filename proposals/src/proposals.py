import abc
from collections import defaultdict
from datetime import datetime
from itertools import product
from json import loads
from os import environ
from typing import Any, Dict, Generator, Tuple, Type, Union
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
        duo_endpoint: str,
        duo_secret: str,
        duo_facility: str,
        duo_year: Union[int, str] = datetime.now().year,
    ) -> None:
        self.duo_endpoint = duo_endpoint
        self.duo_secret = duo_secret
        self.duo_facility = duo_facility
        self.duo_year = duo_year

    @classmethod
    def from_env(cls) -> "Proposals":
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
    def proposals(self) -> Generator[Tuple[Dict[str, Any], str], None, None]:
        """
        Returns a generator of proposals with associated facility.

        Returns:
            Generator yielding tuples of (proposal, facility)
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def _type(self) -> str:
        """DUO endpoint resource type (e.g., proposals, pgroup)"""
        raise NotImplementedError

    @property
    def proposals_path(self) -> str:
        """
        Constructs the DUO proposals API path.

        Returns:
            str: API path to fetch proposals from.
        """
        return f"CalendarInfos/{self._type}"

    @retry
    def request(self, path: str = "") -> Any:
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

    def response(self, path: str = "") -> Any:
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

    def proposals(self) -> Generator[Tuple[Dict[str, Any], str], None, None]:
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._xname_name_map: Dict[str, Tuple[str, str]] = {}

    def _pgroups_with_no_proposal(self) -> Any:
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
    def xname_name_map(self) -> Dict[str, Tuple[str, str]]:
        """
        Maps xname to beamline and facility name.

        Returns:
            dict: A map of xname to (beamline name, facility name)
        """
        _xname_name_map = self._xname_name_map or {
            beamline["xname"]: (beamline["name"], facility["name"])
            for facility in self.response("CalendarInfos/facilities")
            for beamline in facility["beamlines"]
        }
        self._xname_name_map = _xname_name_map
        return _xname_name_map

    def _pgroup_no_proposal_formatter(self, p_group: str) -> Tuple[Dict[str, Any], str]:
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
        p_group_response = self.response(f"{self.proposals_path}/{p_group}")["group"]
        try:
            p_group_response["owner"]
        except KeyError as e:
            log.warning("Missing owner")
            raise MissingOwnerError from e
        beamline, facility = self.xname_name_map[p_group_response["xname"]]
        proposal = {
            "proposal": p_group_response["name"],
            "email": p_group_response["owner"]["email"],
            "pi_email": "",
            "pgroup": p_group_response["name"],
            "beamline": beamline,
            "pi_firstname": p_group_response["owner"]["firstname"],
            "pi_lastname": p_group_response["owner"]["lastname"],
            "firstname": p_group_response["owner"]["firstname"],
            "lastname": p_group_response["owner"]["lastname"],
            "title": "",
            "abstract": "",
            "schedule": [
                {"start": "01/01/1960 01:00:00", "end": "31/12/2100 01:00:00"}
            ],
        }
        log.info("Pgroup with no proposal composed")
        return proposal, facility

    def proposals(self) -> Generator[Tuple[Dict[str, Any], str], None, None]:
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

    _env_to_proposal_class: Dict[str, Type[Proposals]] = defaultdict(
        lambda: ProposalsFromFacility, {"pgroups": ProposalsFromPgroups}
    )

    def __new__(cls, duo_facility: str) -> "ProposalsFactory":
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
    def from_env(cls) -> type[Proposals]:
        """
        Reads environment variables and returns the appropriate Proposals subclass.

        Returns:
            Type[Proposals]: A subclass of Proposals
        """
        load_dotenv()
        duo_facility = environ["DUO_FACILITY"]
        return cls(duo_facility)
