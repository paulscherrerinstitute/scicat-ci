import os
from importlib import reload
from unittest.mock import ANY, Mock, patch

import pytest
from swagger_client.rest import ApiException

import main as m
from scicat import SciCatPolicyFromDuo, SciCatProposalFromDuo

from .fixtures.mocked_data import FixturesFromDuo, FixturesFromSciCatAPI


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


@patch("main.SciCatPolicyFromDuo")
@patch("main.SciCatProposalFromDuo")
@patch("main.create_or_update_proposal")
def test_fill_proposal(
    mock_create_or_update, mock_compose_proposal, mock_compose_policy
):
    row = {"proposal": "123"}
    accellerator = FixturesFromDuo.accelerator
    m.fill_proposal(row, accellerator)

    mock_compose_policy.assert_called_once_with(row, accellerator)

    mock_compose_proposal.assert_called_once_with(row, accellerator, m.DUO_FACILITY)

    mock_create_or_update.assert_called_once_with(
        mock_compose_policy.return_value,
        mock_compose_proposal.return_value,
    )


class TestCreateOrUpdateProposal:

    proposal_id = FixturesFromDuo.scicat_proposal["proposalId"]
    proposal_instance = SciCatProposalFromDuo(
        FixturesFromDuo.duo_proposal,
        FixturesFromDuo.accelerator,
        FixturesFromDuo.duo_facility,
    )

    policy = FixturesFromDuo.policy
    policy_instance = SciCatPolicyFromDuo(
        FixturesFromDuo.duo_proposal, FixturesFromDuo.accelerator
    )

    expeted_measurement_periods = FixturesFromSciCatAPI.expeted_measurement_periods

    class MockProposalApi:

        measurement_period_list = FixturesFromSciCatAPI.measurement_periods

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
        with patch("scicat.ProposalApi", return_value=mock_proposal):
            m.create_or_update_proposal(self.policy_instance, self.proposal_instance)
            mock_proposal.proposal_prototype_patch_attributes.assert_called_once_with(
                self.proposal_id,
                data={
                    "MeasurementPeriodList": self.expeted_measurement_periods,
                },
            )

    @patch(
        "scicat.PolicyApi.policy_create",
        autospec=True,
    )
    def test_create_new_proposal(self, mock_policy_create):
        mock_proposal = self.MockProposalApi(exists=False)
        with patch("scicat.ProposalApi", return_value=mock_proposal):
            m.create_or_update_proposal(self.policy_instance, self.proposal_instance)
            mock_proposal.proposal_create.assert_called_once_with(
                data=FixturesFromDuo.expected_scicat_proposal,
            )
            mock_policy_create.assert_called_once_with(ANY, data=self.policy)
