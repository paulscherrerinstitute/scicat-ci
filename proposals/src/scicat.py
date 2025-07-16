from abc import ABCMeta

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
        credentials = {}
        credentials["username"] = self.username
        credentials["password"] = self.password
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
        proposal = {}
        proposal["proposalId"] = f'20.500.11935/{row["proposal"]}'
        proposal["pi_email"] = self.principal_investigator
        proposal["pi_firstname"] = row["pi_firstname"]
        proposal["pi_lastname"] = row["pi_lastname"]
        proposal["email"] = row["email"]
        if row["email"] == "":
            log.warning(f"Empty email: {row}")

        proposal["firstname"] = row["firstname"]
        proposal["lastname"] = row["lastname"]
        proposal["title"] = row["title"]
        proposal["abstract"] = row["abstract"]
        proposal["ownerGroup"] = self.owner_group
        proposal["accessGroups"] = self.access_groups
        return proposal


class SciCatPolicyFromDuo(SciCatFromDuo, SciCatCreatorFromDuoMixin):

    def compose_policy(self):
        row = self.duo_proposal
        policy = {}
        policy["manager"] = [self.principal_investigator]
        policy["tapeRedundancy"] = "low"
        policy["autoArchive"] = False
        policy["autoArchiveDelay"] = 0
        policy["archiveEmailNotification"] = True
        policy["archiveEmailsToBeNotified"] = []
        policy["retrieveEmailNotification"] = True
        policy["retrieveEmailsToBeNotified"] = []
        policy["embargoPeriod"] = 3
        policy["ownerGroup"] = self.owner_group
        # TODO for SINQ (? still correct ?)
        # policy['ownerGroup'] = 'p'+row['proposal']
        # special mapping for MX needed
        bl = row["beamline"].lower()
        if bl.startswith("px"):
            bl = "mx"
        policy["accessGroups"] = self.access_groups
        return policy
