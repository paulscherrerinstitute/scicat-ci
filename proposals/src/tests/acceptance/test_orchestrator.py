import os
from unittest.mock import ANY, Mock, patch

import pytest
from scicat_sdk_py.exceptions import NotFoundException

import orchestrator

from ..fixtures.mocked_data import (
    FixturesFromSciCatAPI,
    FixturesProposalsFromFacility,
    FixturesProposalsFromPgroups,
)


class TestDuoSciCatOrchestratorFromFacility:

    proposal_class = "ProposalsFromFacility"
    fixture_class = FixturesProposalsFromFacility

    def _proposal_response(self, *args):
        return [FixturesProposalsFromFacility.duo_proposal]

    @pytest.fixture
    @staticmethod
    def patch_scicat_auth():
        with patch("orchestrator.SciCatAuth.authenticate", autospec=True):
            yield

    class MockProposalApi:

        measurement_period_list = FixturesFromSciCatAPI.measurement_periods

        def __init__(self, exists=True):
            find_by_id_result = [
                {"side_effect": NotFoundException},
                {
                    "return_value": Mock(
                        measurement_period_list=self.measurement_period_list
                    )
                },
            ]
            self.proposals_controller_find_by_id_v3 = Mock(**find_by_id_result[exists])
            self.proposals_controller_create_v3 = Mock()
            self.proposals_controller_update_v3 = Mock()

    @pytest.fixture
    def patch_proposal_response(self):
        with patch(
            f"proposals.{self.proposal_class}.response",
            side_effect=self._proposal_response,
            autospec=True,
        ):
            yield

    @pytest.fixture
    def patch_env_facility_pgroups(self):
        with patch.dict(os.environ, {"DUO_FACILITY": self.fixture_class.duo_facility}):
            yield

    @pytest.fixture(autouse=True)
    def _setup_patches(
        self, patch_env_facility_pgroups, patch_scicat_auth, patch_proposal_response
    ):
        self.orchestrator = orchestrator.DuoSciCatOrchestrator()

    @patch(
        "scicat.PoliciesApi.policies_controller_create_v3",
        autospec=True,
    )
    def test_create_proposals_from_duo_to_scicat(self, mock_policy_create):
        mock_proposal = self.MockProposalApi(exists=False)
        with patch("scicat.ProposalsApi", return_value=mock_proposal, autospec=True):
            self.orchestrator.orchestrate()
            mock_proposal.proposals_controller_create_v3.assert_called_once_with(
                self.fixture_class.expected_scicat_proposal,
            )
            mock_policy_create.assert_called_once_with(ANY, self.fixture_class.policy)

    def test_update_proposals_from_duo_to_scicat(self):
        mock_proposal = self.MockProposalApi()
        with patch("scicat.ProposalsApi", return_value=mock_proposal, autospec=True):
            self.orchestrator.orchestrate()
            mock_proposal.proposals_controller_update_v3.assert_called_once_with(
                self.fixture_class.scicat_proposal["proposalId"],
                {
                    "MeasurementPeriodList": self.fixture_class.expected_measurement_periods,
                },
            )


class TestDuoSciCatOrchestratorFromPgroups(TestDuoSciCatOrchestratorFromFacility):

    proposal_class = "ProposalsFromPgroups"
    fixture_class = FixturesProposalsFromPgroups

    @staticmethod
    def _proposal_response(self, path=None):
        if path == "CalendarInfos/facilities":
            return FixturesProposalsFromPgroups.calendar_infos_facilities
        if path == "PGroupAttributes/listProposalAssignments?withoutproposal=true":
            return FixturesProposalsFromPgroups._pgroups_with_no_proposal
        return FixturesProposalsFromPgroups._pgroup_no_proposal_formatter
