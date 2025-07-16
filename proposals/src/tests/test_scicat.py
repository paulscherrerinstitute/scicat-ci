from unittest.mock import ANY, patch

import pytest

import scicat


class TestSciCatAuth:

    scicat_auth = scicat.SciCatAuth("test_user", "test_password", "http://scicat")

    def test_init(self):
        assert self.scicat_auth.username == "test_user"
        assert self.scicat_auth.password == "test_password"
        assert self.scicat_auth.url == "http://scicat"

    @patch(
        "scicat.UserApi.user_login",
        return_value={"id": "test_token"},
        autospec=True,
    )
    def test__get_scicat_token(self, mock_user_login):
        access_token = self.scicat_auth._get_scicat_token()
        assert access_token == "test_token"
        mock_user_login.assert_called_once_with(
            ANY, {"username": "test_user", "password": "test_password"}
        )

    @patch(
        "scicat.SciCatAuth._get_scicat_token", return_value="test_token", autospec=True
    )
    def test__set_scicat_token(self, _):
        self.scicat_auth._set_scicat_token()
        assert scicat.Configuration().host == "http://scicat"
        assert (
            scicat.Configuration().api_client.default_headers["Authorization"]
            == "test_token"
        )

    @patch.object(scicat.SciCatAuth, "_set_scicat_token", autospec=True)
    def test_authenticate(self, mock_set_token):
        self.scicat_auth.authenticate()
        mock_set_token.assert_called_once()


class TestSciCatFromDuo:

    scicat_from_duo = scicat.SciCatFromDuo(
        {"proposal": "test_proposal"}, "test_accelerator"
    )

    def test_init(self):
        assert self.scicat_from_duo.duo_proposal == {"proposal": "test_proposal"}
        assert self.scicat_from_duo.accelerator == "test_accelerator"


class TestSciCatCreatorFromDuoMixin:

    scicat_creator = scicat.SciCatCreatorFromDuoMixin()

    @pytest.mark.parametrize(
        "duo_proposal, expected",
        [
            [{"pi_email": "pi", "email": "email"}, "pi"],
            [{"pi_email": "", "email": "email"}, "email"],
        ],
    )
    def test_principal_investigator(self, duo_proposal, expected):
        self.scicat_creator.duo_proposal = duo_proposal
        assert self.scicat_creator.principal_investigator == expected

    @pytest.mark.parametrize(
        "duo_proposal, expected",
        [
            [{"pgroup": "g1", "proposal": 123}, "g1"],
            [{"pgroup": "", "proposal": 123}, "p123"],
        ],
    )
    def test_owner_group(self, duo_proposal, expected):
        self.scicat_creator.duo_proposal = duo_proposal
        assert self.scicat_creator.owner_group == expected

    @pytest.mark.parametrize(
        "duo_proposal, expected",
        [
            [{"beamline": "px"}, ["slsmx"]],
            [{"beamline": "lx"}, ["slslx"]],
        ],
    )
    def test_access_groups(self, duo_proposal, expected):
        self.scicat_creator.duo_proposal = duo_proposal
        self.scicat_creator.accelerator = "sls"
        assert self.scicat_creator.access_groups == expected
