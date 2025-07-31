from abc import ABCMeta, abstractmethod

from proposals import ProposalsFactory
from scicat import SciCatAuth, SciCatPolicyFromDuo, SciCatProposalFromDuo
from utils import log


class Orchestrator(metaclass=ABCMeta):
    """
    Abstract base class for orchestrator implementations.

    Defines the required interface for any concrete orchestrator.
    """

    @abstractmethod
    def orchestrate(self):
        """
        Executes the orchestration logic.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError


class DuoSciCatOrchestrator(Orchestrator):
    """
    Orchestrates the synchronization between DUO proposals and SciCat.

    Attributes:
        scicat_instance (SciCatAuth): Instance used to authenticate with SciCat.
        duo_facility (str): The DUO facility code (e.g., SINQ, SLS).
        duo_instance: Instance of proposals interface loaded from environment.
        year (str): Year of DUO proposals to be processed.
    """

    def __init__(self):
        """
        Initializes the orchestrator, loading environment configuration for SciCat and DUO.
        """
        self.scicat_instance = SciCatAuth.from_env()
        duo_instance = ProposalsFactory.from_env().from_env()
        self.duo_facility = duo_instance.duo_facility
        self.duo_instance = duo_instance
        self.year = duo_instance.duo_year

    @staticmethod
    def _upsert_policy_and_proposal(policy, proposal):
        """
        Creates or updates SciCat proposal and policy based on DUO input.

        Args:
            policy (SciCatPolicyFromDuo): Policy object derived from DUO proposal.
            proposal (SciCatProposalFromDuo): Proposal object derived from DUO proposal.
        """
        try:
            # check for existence of Proposal data and merge schedules into it
            proposal.update()
        except SciCatProposalFromDuo.ProposalNotFoundException as e:
            log.warning(e)
            # create new proposal
            proposal.create()
            policy.create()

    def _upsert_policy_and_proposal_from_duo(self, duo_proposal, accelerator):
        """
        Converts a DUO proposal into SciCat entries and upserts them.

        Args:
            duo_proposal (dict): Raw DUO proposal data.
            accelerator (str): Accelerator (e.g., SLS, SINQ).
        """
        log.info(f"============= Input proposal: {duo_proposal['proposal']}")
        policy = SciCatPolicyFromDuo(duo_proposal, accelerator)
        proposal = SciCatProposalFromDuo(duo_proposal, accelerator, self.duo_facility)
        try:
            self._upsert_policy_and_proposal(policy, proposal)
        except Exception as e:
            log.error(e)

    def orchestrate(self):
        """
        Coordinates the synchronization of all DUO proposals into SciCat.
        """
        log.info("==== DUO sync started ====")
        log.info(
            f"Fetching proposals for accelerator {self.duo_facility} and year {self.year}"
        )
        log.info(f"Connecting to scicat on {self.scicat_instance.url}")
        self.scicat_instance.authenticate()
        for proposal, facility in self.duo_instance.proposals():
            self._upsert_policy_and_proposal_from_duo(proposal, facility)
