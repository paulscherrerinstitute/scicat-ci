import os
from abc import ABCMeta, abstractmethod
from datetime import datetime

from dotenv import load_dotenv

from proposals import ProposalsFromFacility, ProposalsFromPgroups
from scicat import SciCatAuth, SciCatPolicyFromDuo, SciCatProposalFromDuo
from utils import log


class Orchestrator(metaclass=ABCMeta):

    @abstractmethod
    def orchestrate(self):
        raise NotImplementedError


class DuoSciCatOrchestrator(Orchestrator):

    def __init__(self):
        load_dotenv()
        # duo config variables
        DUO_ENDPOINT = os.environ["DUO_ENDPOINT"]
        DUO_SECRET = os.environ["DUO_SECRET"]
        DUO_YEAR = os.environ["DUO_YEAR"]
        self.year = DUO_YEAR or datetime.now().year
        DUO_FACILITY = os.environ["DUO_FACILITY"]
        self.duo_facility = DUO_FACILITY

        self.scicat_instance = SciCatAuth.from_env()
        self.duo_instance = {"pgroups": ProposalsFromPgroups}.get(
            DUO_FACILITY, ProposalsFromFacility
        )(DUO_ENDPOINT, DUO_SECRET)

    @staticmethod
    def _upsert_policy_and_proposal(policy, proposal):
        try:
            # check for existence of Proposal data and merge schedules into it
            proposal.update()
        except SciCatProposalFromDuo.ProposalNotFoundException as e:
            log.error(e)
            # create new proposal
            proposal.create()
            policy.create()

    def _upsert_policy_and_proposal_from_duo(self, duo_proposal, accelerator):
        log.info(f"============= Input proposal: {duo_proposal['proposal']}")
        policy = SciCatPolicyFromDuo(duo_proposal, accelerator)
        proposal = SciCatProposalFromDuo(duo_proposal, accelerator, self.duo_facility)
        try:
            self._upsert_policy_and_proposal(policy, proposal)
        except Exception as e:
            log.error(e)

    def orchestrate(self):
        log.info(
            f"Fetching proposals for accelerator {self.duo_facility} and year {self.year}"
        )
        log.info(f"Connecting to scicat on {self.scicat_instance.url}")
        self.scicat_instance.authenticate()
        for proposal, facility in self.duo_instance.proposals(
            self.duo_facility, self.year
        ):
            self._upsert_policy_and_proposal_from_duo(proposal, facility)
