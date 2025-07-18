import os
from copy import deepcopy
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

    proposal = FixturesFromDuo.scicat_proposal
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

    def _add_compose(self, scicat_return):
        return Mock(compose=Mock(return_value=scicat_return))

    def test_update_existing_proposal(self):
        mock_proposal = self.MockProposalApi()
        with patch("main.swagger_client.ProposalApi", return_value=mock_proposal):
            proposal = deepcopy(self.proposal)

            m.create_or_update_proposal(
                self._add_compose(self.policy), self._add_compose(proposal)
            )
            mock_proposal.proposal_prototype_patch_attributes.assert_called_once_with(
                proposal["proposalId"],
                data={
                    "MeasurementPeriodList": self.expeted_measurement_periods,
                },
            )

    @patch(
        "scicat.ProposalApi.proposal_create",
        autospec=True,
    )
    @patch(
        "scicat.PolicyApi.policy_create",
        autospec=True,
    )
    def test_create_new_proposal(self, mock_policy_create, mock_proposal_create):
        mock_proposal = self.MockProposalApi(exists=False)
        with patch("main.swagger_client.ProposalApi", return_value=mock_proposal):
            m.create_or_update_proposal(self.policy_instance, self.proposal_instance)
            mock_proposal_create.assert_called_once_with(
                ANY,
                data=FixturesFromDuo.expected_scicat_proposal,
            )
            mock_policy_create.assert_called_once_with(ANY, data=self.policy)

    def test_compose_new_measurement_periods(self):
        new_measures = m.compose_new_measurement_periods(
            self.proposal["MeasurementPeriodList"],
            "p123",
            self.MockProposalApi.measurement_period_list,
        )
        assert new_measures == self.expeted_measurement_periods

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
