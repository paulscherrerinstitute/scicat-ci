import os
from copy import deepcopy
from importlib import reload
from unittest.mock import ANY, Mock, patch

import pytest

import main as m


@pytest.mark.parametrize(
    "row, expected",
    [
        [{"pi_email": "pi", "email": "email"}, "pi"],
        [{"pi_email": "", "email": "email"}, "email"],
    ],
)
def test_compose_principal_investigator(row, expected):
    pi = m.compose_principal_investigator(row)
    assert pi == expected


@pytest.mark.parametrize(
    "row, expected",
    [
        [
            {"pgroup": "abc", "proposal": "123", "beamline": "PX"},
            {"ownerGroup": "abc", "accessGroups": ["SLSmx"]},
        ],
        [
            {"pgroup": "", "proposal": "123", "beamline": "kl"},
            {"ownerGroup": "p123", "accessGroups": ["SLSkl"]},
        ],
    ],
)
def test_compose_policy(row, expected):
    policy = m.compose_policy(row, "SLS", "pi_email")
    static_properties = {
        "manager": ["pi_email"],
        "tapeRedundancy": "low",
        "autoArchive": False,
        "autoArchiveDelay": 0,
        "archiveEmailNotification": True,
        "archiveEmailsToBeNotified": [],
        "retrieveEmailNotification": True,
        "retrieveEmailsToBeNotified": [],
        "embargoPeriod": 3,
    }
    assert policy == {**static_properties, **expected}


def test_compose_proposal():
    row = {
        "proposal": "123",
        "pi_firstname": "John",
        "pi_lastname": "Doe",
        "email": "",
        "firstname": "Jane",
        "lastname": "Smith",
        "title": "Test Proposal",
        "abstract": "This is a test proposal.",
    }
    proposal = m.compose_proposal(
        row, "pi_email", {"ownerGroup": "test_group", "accessGroups": ["test_access"]}
    )
    assert proposal == {
        "proposalId": "20.500.11935/123",
        "pi_email": "pi_email",
        "pi_firstname": "John",
        "pi_lastname": "Doe",
        "email": "",
        "firstname": "Jane",
        "lastname": "Smith",
        "title": "Test Proposal",
        "abstract": "This is a test proposal.",
        "ownerGroup": "test_group",
        "accessGroups": ["test_access"],
    }


@pytest.mark.parametrize(
    "duo_facility, schedule, expected",
    [
        [
            "sls",
            {"start": "01/01/2023 01:00:00", "end": "02/01/2023 01:00:00"},
            {"start": "2023-01-01T00:00:00+00:00", "end": "2023-01-02T00:00:00+00:00"},
        ],
        [
            "sinq",
            {"start": "01/01/2023", "end": "02/01/2023"},
            {"start": "2022-12-31T23:00:00+00:00", "end": "2023-01-01T23:00:00+00:00"},
        ],
        [
            "smus",
            {"start": "01/01/2023", "end": "02/01/2023"},
            {"start": "2022-12-31T23:00:00+00:00", "end": "2023-01-01T23:00:00+00:00"},
        ],
    ],
)
def test_compose_measurement_period(duo_facility, schedule, expected):

    with patch.dict(os.environ, {"DUO_FACILITY": duo_facility}):
        reload(m)
        row = {
            "beamline": "PX",
        }
        accelerator = "SLS"
        mp = m.compose_measurement_period(row, accelerator, schedule)
        assert mp == {"id": ANY, "instrument": "/PSI/SLS/PX", **expected, "comment": ""}


def test_compose_measurement_periods():
    accelerator = "SLS"
    row = {
        "beamline": "PX",
        "schedule": [
            {"start": "01/01/2023", "end": "02/01/2023"},
            {"start": "01/01/2024", "end": "02/01/2024"},
        ],
    }
    measurement_periods = m.compose_measurement_periods(row, accelerator)
    assert measurement_periods == [
        {
            "id": ANY,
            "instrument": "/PSI/SLS/PX",
            "start": "2022-12-31T23:00:00+00:00",
            "end": "2023-01-01T23:00:00+00:00",
            "comment": "",
        },
        {
            "id": ANY,
            "instrument": "/PSI/SLS/PX",
            "start": "2023-12-31T23:00:00+00:00",
            "end": "2024-01-01T23:00:00+00:00",
            "comment": "",
        },
    ]


@patch(
    "main.swagger_client.UserApi.user_login",
    return_value={"id": "test_token"},
    autospec=True,
)
def test__get_scicat_token(_):
    access_token = m._get_scicat_token()
    assert access_token == "test_token"


@patch.dict(os.environ, {"SCICAT_ENDPOINT": "http://scicat"})
def test__set_scicat_token():
    reload(m)
    with patch("main._get_scicat_token", return_value="test_token", autospec=True):
        m._set_scicat_token()
        assert m.Configuration().host == "http://scicat"
        assert (
            m.Configuration().api_client.default_headers["Authorization"]
            == "test_token"
        )


class TestCreateOrUpdateProposal:

    proposal = {
        "proposalId": "20.500.11935/123",
        "pi_email": "pi_email",
        "pi_firstname": "John",
        "pi_lastname": "Doe",
        "email": "",
        "firstname": "Jane",
        "lastname": "Smith",
        "title": "Test Proposal",
        "abstract": "This is a test proposal.",
        "ownerGroup": "test_group",
        "accessGroups": ["test_access"],
    }

    policy = {
        "manager": ["pi_email"],
        "tapeRedundancy": "low",
        "autoArchive": False,
        "autoArchiveDelay": 0,
        "archiveEmailNotification": True,
        "archiveEmailsToBeNotified": [],
        "retrieveEmailNotification": True,
        "retrieveEmailsToBeNotified": [],
        "embargoPeriod": 3,
        "ownerGroup": "abc",
        "accessGroups": ["SLSmx"],
    }

    measurement_periods = [
        {
            "id": "to_include_new_from_duo",
            "instrument": "/PSI/SLS/PX",
            "start": "2024-12-31T23:00:00+00:00",
            "end": "2025-01-01T23:00:00+00:00",
            "comment": "",
        },
        {
            "id": "to_exclude_on_update_because_789_scicat",
            "instrument": "/PSI/SLS/PX",
            "start": "2023-12-31T23:00:00+00:00",
            "end": "2024-01-01T23:00:00+00:00",
            "comment": "",
        },
    ]

    class MockProposalApi:

        def __init__(self, exists=True):
            self.proposal_exists_get_proposalsid_exists = Mock(
                return_value=Mock(exists=exists)
            )
            self.proposal_find_by_id = Mock(side_effect=self._proposal_find_by_id)
            self.proposal_create = Mock()
            self.proposal_prototype_patch_attributes = Mock()

        def _proposal_find_by_id(self, proposal_id):
            return Mock(
                measurement_period_list=[
                    Mock(
                        id=789,
                        instrument="/PSI/SLS/PX",
                        start="2023-12-31T23:00:00+00:00",
                        end="2024-01-01T23:00:00+00:00",
                        comment="",
                    ),
                    Mock(
                        id=000,
                        instrument="/PSI/SLS/PX",
                        start="2021-12-31T23:00:00+00:00",
                        end="2022-01-01T23:00:00+00:00",
                        comment="",
                    ),
                ]
            )

    def test_update_existing_proposal(self):
        mock_proposal = self.MockProposalApi()
        with patch("main.swagger_client.ProposalApi", return_value=mock_proposal):
            proposal = deepcopy(self.proposal)

            m.create_or_update_proposal(self.policy, proposal, self.measurement_periods)
            expeted_measurement_periods = [
                {
                    "id": "to_include_new_from_duo",
                    "instrument": "/PSI/SLS/PX",
                    "start": "2024-12-31T23:00:00+00:00",
                    "end": "2025-01-01T23:00:00+00:00",
                    "comment": "",
                },
            ]
            mock_proposal.proposal_prototype_patch_attributes.assert_called_once_with(
                proposal["proposalId"],
                data={
                    "MeasurementPeriodList": expeted_measurement_periods,
                },
            )

    @patch(
        "main.swagger_client.PolicyApi.policy_create",
        autospec=True,
    )
    def test_create_new_proposal(self, mock_policy_create):
        mock_proposal = self.MockProposalApi(exists=False)
        with patch("main.swagger_client.ProposalApi", return_value=mock_proposal):
            proposal = deepcopy(self.proposal)
            m.create_or_update_proposal(self.policy, proposal, self.measurement_periods)
            mock_proposal.proposal_create.assert_called_once_with(
                data={
                    **self.proposal,
                    "MeasurementPeriodList": self.measurement_periods,
                }
            )
            mock_policy_create.assert_called_once_with(ANY, data=self.policy)
