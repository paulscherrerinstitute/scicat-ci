import os
from copy import deepcopy
from importlib import reload
from unittest.mock import ANY, Mock, patch

import pytest
from swagger_client.rest import ApiException

import main as m


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
            expected_policy,
            {**expected_proposal, "MeasurementPeriodList": expected_measurement},
        )


@patch("main.SciCatPolicyFromDuo")
@patch("main.SciCatProposalFromDuo")
@patch("main.create_or_update_proposal")
def test_fill_proposal(
    mock_create_or_update, mock_compose_proposal, mock_compose_policy
):
    row = {"proposal": "123"}
    accellerator = "SLS"
    m.fill_proposal(row, accellerator)

    mock_compose_policy.assert_called_once_with(row, accellerator)
    mock_compose_policy_instance = mock_compose_policy.return_value
    mock_compose_policy_instance.compose.assert_called_once()

    mock_compose_proposal.assert_called_once_with(row, accellerator, m.DUO_FACILITY)
    mock_compose_proposal_instance = mock_compose_proposal.return_value
    mock_compose_proposal_instance.compose.assert_called_once()

    mock_create_or_update.assert_called_once_with(
        mock_compose_policy_instance.compose.return_value,
        mock_compose_proposal_instance.compose.return_value,
    )


class TestCreateOrUpdateProposal:

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
        "MeasurementPeriodList": measurement_periods,
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

    expeted_measurement_periods = [
        {
            "id": "to_include_new_from_duo",
            "instrument": "/PSI/SLS/PX",
            "start": "2024-12-31T23:00:00+00:00",
            "end": "2025-01-01T23:00:00+00:00",
            "comment": "",
        },
    ]

    class MockProposalApi:

        measurement_period_list = [
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

        def __init__(self, exists=True):
            find_by_id_result = [
                {"side_effect": ApiException(status=404)},
                {
                    "return_value": Mock(
                        measurement_period_list=self.measurement_period_list
                    )
                },
            ]
            self.proposal_find_by_id = Mock(**find_by_id_result[exists])
            self.proposal_create = Mock()
            self.proposal_prototype_patch_attributes = Mock()

    def test_update_existing_proposal(self):
        mock_proposal = self.MockProposalApi()
        with patch("main.swagger_client.ProposalApi", return_value=mock_proposal):
            proposal = deepcopy(self.proposal)

            m.create_or_update_proposal(self.policy, proposal)
            mock_proposal.proposal_prototype_patch_attributes.assert_called_once_with(
                proposal["proposalId"],
                data={
                    "MeasurementPeriodList": self.expeted_measurement_periods,
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
            m.create_or_update_proposal(self.policy, proposal)
            mock_proposal.proposal_create.assert_called_once_with(
                data=self.proposal,
            )
            mock_policy_create.assert_called_once_with(ANY, data=self.policy)

    def test_compose_new_measurement_periods(self):
        new_measures = m.compose_new_measurement_periods(
            self.measurement_periods,
            "p123",
            self.MockProposalApi.measurement_period_list,
        )
        assert new_measures == self.expeted_measurement_periods

    @patch("main.swagger_client.PolicyApi.policy_create")
    def test_create_policy(self, mock_policy_create):
        policy = {"policy": "policy"}
        m.create_policy(policy)
        mock_policy_create.assert_called_once_with(data=policy)

    @patch("main.swagger_client.ProposalApi.proposal_create")
    def test_create_proposal(self, mock_proposal_create):
        proposal = deepcopy(self.proposal)
        m.create_proposal(proposal)
        mock_proposal_create.assert_called_once_with(data=self.proposal)

    def test_update_proposal(self):
        mock_proposal = self.MockProposalApi()
        with patch("main.swagger_client.ProposalApi", return_value=mock_proposal):
            proposal = deepcopy(self.proposal)
            m.update_proposal(self.proposal)
            mock_proposal.proposal_find_by_id.assert_called_once_with(
                proposal["proposalId"]
            )
            mock_proposal.proposal_prototype_patch_attributes.assert_called_once_with(
                proposal["proposalId"],
                data={
                    "MeasurementPeriodList": self.expeted_measurement_periods,
                },
            )
