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
