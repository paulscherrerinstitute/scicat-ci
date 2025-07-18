import os
from unittest.mock import ANY, Mock, patch

import pytest
from swagger_client.rest import ApiException

import orchestrator
from scicat import SciCatPolicyFromDuo, SciCatProposalFromDuo

from .fixtures.mocked_data import FixturesFromDuo, FixturesFromSciCatAPI


class TestDuoSciCatOrchestrator:

    proposal_id = FixturesFromDuo.scicat_proposal["proposalId"]
    policy = FixturesFromDuo.policy
    expeted_measurement_periods = FixturesFromSciCatAPI.expeted_measurement_periods

    def setup_method(self):
        self.proposal_instance = SciCatProposalFromDuo(
            FixturesFromDuo.duo_proposal,
            FixturesFromDuo.accelerator,
            FixturesFromDuo.duo_facility,
        )

        self.policy_instance = SciCatPolicyFromDuo(
            FixturesFromDuo.duo_proposal, FixturesFromDuo.accelerator
        )

        self.env_patch = patch.dict(os.environ, {"DUO_FACILITY": "sls"})
        self.env_patch.start()

        self.orchestrator = orchestrator.DuoSciCatOrchestrator()

    def tear_down(self):
        self.env_patch.stop()

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

    def test_update__upsert_policy_and_proposal(self):
        mock_proposal = self.MockProposalApi()
        with patch("scicat.ProposalApi", return_value=mock_proposal):
            self.orchestrator._upsert_policy_and_proposal(
                self.policy_instance, self.proposal_instance
            )
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
    def test_create__upsert_policy_and_proposal(self, mock_policy_create):
        mock_proposal = self.MockProposalApi(exists=False)
        with patch("scicat.ProposalApi", return_value=mock_proposal):
            self.orchestrator._upsert_policy_and_proposal(
                self.policy_instance, self.proposal_instance
            )
            mock_proposal.proposal_create.assert_called_once_with(
                data=FixturesFromDuo.expected_scicat_proposal,
            )
            mock_policy_create.assert_called_once_with(ANY, data=self.policy)

    @pytest.mark.parametrize(
        "expected_exception",
        [
            True,
            False,
        ],
    )
    @patch("orchestrator.SciCatPolicyFromDuo")
    @patch("orchestrator.SciCatProposalFromDuo")
    @patch("orchestrator.log")
    def test__upsert_policy_and_proposal_from_duo(
        self, mock_log, mock_compose_proposal, mock_compose_policy, expected_exception
    ):
        row = {"proposal": "123"}
        accellerator = FixturesFromDuo.accelerator
        exception = Exception("_upsert_policy_and_proposal_from_duo exception")
        side_effect = {"side_effect": exception} if expected_exception else {}
        with patch(
            "orchestrator.DuoSciCatOrchestrator._upsert_policy_and_proposal",
            **side_effect
        ) as mock_create_or_update:
            self.orchestrator._upsert_policy_and_proposal_from_duo(row, accellerator)

            mock_compose_policy.assert_called_once_with(row, accellerator)

            mock_compose_proposal.assert_called_once_with(
                row, accellerator, self.orchestrator.duo_facility
            )

            mock_create_or_update.assert_called_once_with(
                mock_compose_policy.return_value,
                mock_compose_proposal.return_value,
            )
            assert mock_log.error.call_count == expected_exception
            if expected_exception:
                mock_log.error.assert_called_once_with(exception)

    @pytest.mark.parametrize(
        "duo_facility, expected",
        [
            ["sls", "ProposalsFromFacility"],
            ["pgroups", "ProposalsFromPgroups"],
        ],
    )
    def test_init(self, duo_facility, expected):
        with patch.dict(
            os.environ,
            {
                "DUO_FACILITY": duo_facility,
                "DUO_YEAR": "2023",
                "SCICAT_ENDPOINT": "http://scicat",
                "SCICAT_USERNAME": "test_user",
                "SCICAT_PASSWORD": "test_password",
                "DUO_SECRET": "test_duo_secret",
                "DUO_ENDPOINT": "test_duo_endpoint",
            },
        ):
            orchestrator_instance = orchestrator.DuoSciCatOrchestrator()
            assert orchestrator_instance.duo_instance.__class__.__name__ == expected
            assert (
                orchestrator_instance.duo_instance.__dict__.items()
                >= {
                    "duo_endpoint": "test_duo_endpoint",
                    "duo_secret": "test_duo_secret",
                }.items()
            )
            assert orchestrator_instance.duo_facility == duo_facility
            assert orchestrator_instance.year == "2023"
            assert orchestrator_instance.scicat_instance.__dict__ == {
                "password": "test_password",
                "username": "test_user",
                "url": "http://scicat",
            }

    @patch(
        "proposals.ProposalsFromFacility.proposals",
        return_value=iter([("proposal", "facility")]),
    )
    @patch("orchestrator.DuoSciCatOrchestrator._upsert_policy_and_proposal_from_duo")
    @patch("orchestrator.SciCatAuth.authenticate")
    def test_orchestrate(self, mock_scicat_auth, mock_duo_proposal, _):
        self.orchestrator.orchestrate()
        mock_scicat_auth.assert_called_once()
        mock_duo_proposal.assert_called_once_with("proposal", "facility")
