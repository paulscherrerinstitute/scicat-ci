import os
from copy import deepcopy
from importlib import reload
from unittest.mock import ANY, Mock, patch

import pytest

import main as m


@pytest.mark.parametrize(
    "row, expected",
    [
        [{"pgroup": "g1", "proposal": 123}, "g1"],
        [{"pgroup": "", "proposal": 123}, "p123"],
    ],
)
def test_compose_owner_group(row, expected):
    owner_group = m.compose_owner_group(row)
    assert owner_group == expected


@pytest.mark.parametrize(
    "row, expected",
    [
        [{"beamline": "px"}, ["slsmx"]],
        [{"beamline": "lx"}, ["slslx"]],
    ],
)
def test_compose_access_groups(row, expected):
    access_groups = m.compose_access_groups(row, "sls")
    assert access_groups == expected


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
    policy = m.compose_policy({**row, "pi_email": "pi_email"}, "SLS")
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
        "pgroup": "test_group",
        "beamline": "PX",
    }
    proposal = m.compose_proposal({**row, "pi_email": "pi_email"}, "sls")
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
        "accessGroups": ["slsmx"],
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


@pytest.mark.parametrize(
    "duo_facility, expected",
    [
        ["sls", "ProposalsFromFacility"],
        ["pgroups", "ProposalsFromPgroups"],
    ],
)
def test_main(duo_facility, expected):
    with patch.dict(
        os.environ,
        {
            "DUO_FACILITY": duo_facility,
            "DUO_YEAR": "2023",
            "SCICAT_ENDPOINT": "http://scicat",
            "SCICAT_USERNAME": "test_user",
            "SCICAT_PASSWORD": "test_password",
        },
    ):
        reload(m)
        assert m.PROPOSALS.__class__.__name__ == expected
        with patch(
            f"main.{expected}.proposals",
            return_value=iter([("proposal", "facility")]),
        ) as mock_proposals, patch("main.SciCatAuth") as mock_scicat_auth, patch(
            "main.fill_proposal"
        ) as mock_fill_proposal:
            m.main()
            mock_instance = mock_scicat_auth.return_value
            mock_scicat_auth.assert_called_once_with(
                "test_user", "test_password", "http://scicat"
            )
            mock_instance.authenticate.assert_called_once()
            mock_proposals.assert_called_once_with(duo_facility, "2023")
            mock_fill_proposal.assert_called_once_with("proposal", "facility")


def test_fill_proposal_acceptance():
    reload(m)
    row = {
        "proposal": "123",
        "pi_firstname": "John",
        "pi_lastname": "Doe",
        "email": "",
        "firstname": "Jane",
        "lastname": "Smith",
        "title": "Test Proposal",
        "abstract": "This is a test proposal.",
        "pgroup": "test_group",
        "beamline": "PX",
        "pi_email": "pi_email",
        "schedule": [
            {"start": "01/01/2023", "end": "02/01/2023"},
            {"start": "01/01/2024", "end": "02/01/2024"},
        ],
    }

    accelerator = "sls"
    expected_proposal = {
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
        "accessGroups": ["slsmx"],
    }
    expected_policy = {
        "tapeRedundancy": "low",
        "autoArchive": False,
        "autoArchiveDelay": 0,
        "archiveEmailNotification": True,
        "archiveEmailsToBeNotified": [],
        "retrieveEmailNotification": True,
        "retrieveEmailsToBeNotified": [],
        "embargoPeriod": 3,
        "manager": ["pi_email"],
        "ownerGroup": "test_group",
        "accessGroups": ["slsmx"],
    }
    expected_measurement = [
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
    with patch("main.create_or_update_proposal") as mock_create_or_update:
        m.fill_proposal(row, accelerator)
        mock_create_or_update.assert_called_once_with(
            expected_policy, expected_proposal, expected_measurement
        )


@patch("main.compose_policy")
@patch("main.compose_proposal")
@patch("main.compose_measurement_periods")
@patch("main.create_or_update_proposal")
def test_fill_proposal(
    mock_create_or_update, mock_compose_mp, mock_compose_proposal, mock_compose_policy
):
    row = {"proposal": "123"}
    accellerator = "SLS"
    m.fill_proposal(row, accellerator)
    mock_compose_policy.assert_called_once_with(row, accellerator)
    mock_compose_proposal.assert_called_once_with(row, accellerator)
    mock_compose_mp.assert_called_once_with(row, accellerator)
    mock_create_or_update.assert_called_once_with(
        mock_compose_policy.return_value,
        mock_compose_proposal.return_value,
        mock_compose_mp.return_value,
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
