import datetime
import os
from unittest.mock import ANY, Mock, patch

import pytest
from scicat_sdk_py.exceptions import NotFoundException

import scicat

from .fixtures.mocked_data import FixturesFromDuo, FixturesFromSciCatAPI


class TestSciCatAuth:

    scicat_auth = scicat.SciCatAuth("test_user", "test_password", "http://scicat")

    def test_init(self):
        assert self.scicat_auth.username == "test_user"
        assert self.scicat_auth.password == "test_password"
        assert self.scicat_auth.url == "http://scicat"

    @patch(
        "scicat.AuthApi.auth_controller_login_v3",
        return_value=Mock(access_token="test_token"),
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
        assert scicat.Configuration.get_default().host == "http://scicat"
        assert scicat.Configuration.get_default().access_token == "test_token"

    @patch.object(scicat.SciCatAuth, "_set_scicat_token", autospec=True)
    def test_authenticate(self, mock_set_token):
        self.scicat_auth.authenticate()
        mock_set_token.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "SCICAT_ENDPOINT": "http://scicat",
            "SCICAT_USERNAME": "test_user",
            "SCICAT_PASSWORD": "test_password",
        },
    )
    def test_from_env(self):
        scicat_instance = scicat.SciCatAuth.from_env()
        assert scicat_instance.__dict__ == {
            "password": "test_password",
            "username": "test_user",
            "url": "http://scicat",
        }


class TestSciCatFromDuo:

    class DummySciCatFromDuo(scicat.SciCatFromDuo):
        def compose(self):
            pass

        def create(self):
            pass

    scicat_from_duo = DummySciCatFromDuo(
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

    @pytest.mark.parametrize(
        "beamline_input, expected",
        [
            ["single_beamline", "single_beamline"],
            [("tuple_bl", "facility"), ("tuple_bl", "facility")],
            [[("skip", False), ("match", True), ("last", True)], "match"],
            [[("first", False), ("second", False), ("fallback", False)], "fallback"],
            [[("bl1", ""), ("bl2", "active")], "bl2"],
        ],
    )
    def test_beamline(self, beamline_input, expected):
        self.scicat_creator.duo_proposal = {"beamline": beamline_input}
        assert self.scicat_creator.beamline == expected


class TestSciCatPolicyFromDuo:

    scicat_policy = scicat.SciCatPolicyFromDuo(
        FixturesFromDuo.duo_proposal, FixturesFromDuo.accelerator
    )

    def test_compose(self):
        policy = self.scicat_policy.compose()
        assert policy == FixturesFromDuo.policy

    @patch("scicat.PoliciesApi.policies_controller_create_v3", autospec=True)
    def test_create(self, mock_policy_create):
        self.scicat_policy.create()
        mock_policy_create.assert_called_once_with(ANY, FixturesFromDuo.policy)


class TestSciCatProposalFromDuo:

    def setup_method(self):
        self.scicat_proposal = scicat.SciCatProposalFromDuo(
            FixturesFromDuo.duo_proposal,
            FixturesFromDuo.accelerator,
            FixturesFromDuo.duo_facility,
        )
        self.proposalId = FixturesFromDuo.scicat_proposal["proposalId"]

    @patch("scicat.log.info", autospec=True)
    def test_compose(self, mock_log_info):
        proposal = self.scicat_proposal.compose()
        assert proposal == FixturesFromDuo.expected_scicat_proposal
        call_count = mock_log_info.call_count
        proposal1 = self.scicat_proposal.compose()
        assert proposal1 == FixturesFromDuo.expected_scicat_proposal
        assert mock_log_info.call_count == call_count

    @patch("scicat.ProposalsApi.proposals_controller_create_v3", autospec=True)
    def test_create_proposal(self, mock_proposal_create):
        self.scicat_proposal.create()
        mock_proposal_create.assert_called_once_with(
            ANY, FixturesFromDuo.expected_scicat_proposal
        )

    @pytest.mark.parametrize(
        "measurement_periods, expected",
        [
            [
                FixturesFromSciCatAPI.measurement_periods,
                FixturesFromSciCatAPI.expected_measurement_periods,
            ],
            [FixturesFromSciCatAPI.same_proposals_measurement_periods, False],
        ],
    )
    @patch("scicat.ProposalsApi.proposals_controller_update_v3", autospec=True)
    @patch(
        "scicat.ProposalsApi.proposals_controller_find_by_id_v3",
        autospec=True,
    )
    def test__update(
        self, mock_proposal_find, mock_proposal_patch, measurement_periods, expected
    ):
        mock_proposal_find.return_value = Mock(
            measurement_period_list=measurement_periods
        )
        self.scicat_proposal._update()
        mock_proposal_find.assert_called_once_with(ANY, self.proposalId)
        if not expected:
            mock_proposal_patch.assert_not_called()
            return
        mock_proposal_patch.assert_called_once_with(
            ANY,
            self.proposalId,
            {
                "MeasurementPeriodList": expected,
            },
        )

    @pytest.mark.parametrize(
        "result, expected",
        [
            [{"return_value": ""}, ""],
            [
                {"side_effect": NotFoundException},
                scicat.SciCatProposalFromDuo.ProposalNotFoundException,
            ],
            [{"side_effect": KeyError}, KeyError],
        ],
    )
    def test_update(self, result, expected):
        with patch(
            "scicat.SciCatProposalFromDuo._update", **result, autospec=True
        ) as mock_update:
            if "side_effect" in result:
                with pytest.raises(expected):
                    self.scicat_proposal.update()
            else:
                self.scicat_proposal.update()
            mock_update.assert_called_once()


class TestSciCatMeasurementsFromDuoMixin:

    def setup_method(self):
        scicat_measurements = scicat.SciCatMeasurementsFromDuoMixin()
        scicat_measurements.duo_facility = FixturesFromDuo.duo_facility
        scicat_measurements.duo_proposal = FixturesFromDuo.duo_proposal
        scicat_measurements.accelerator = FixturesFromDuo.accelerator
        scicat_measurements.beamline = "px"
        self.scicat_measurements = scicat_measurements

    def test_init(self):
        assert self.scicat_measurements.duo_proposal == FixturesFromDuo.duo_proposal
        assert self.scicat_measurements.accelerator == FixturesFromDuo.accelerator
        assert self.scicat_measurements.duo_facility == FixturesFromDuo.duo_facility

    @pytest.mark.parametrize(
        "duo_facility, expected",
        [
            ["sinq", "%d/%m/%Y"],
            ["smus", "%d/%m/%Y"],
            ["sls", "%d/%m/%Y %H:%M:%S"],
        ],
    )
    def test_duo_facility_datetime_format(self, duo_facility, expected):
        self.scicat_measurements.duo_facility = duo_facility
        assert self.scicat_measurements.duo_facility_datetime_format == expected

    @pytest.mark.parametrize(
        "duo_facility, schedule, expected",
        [
            [
                "sls",
                {"start": "01/01/2023 01:00:00", "end": "02/01/2023 01:00:00"},
                {
                    "start": "2023-01-01T00:00:00+00:00",
                    "end": "2023-01-02T00:00:00+00:00",
                },
            ],
            [
                "sinq",
                {"start": "01/01/2023", "end": "02/01/2023"},
                {
                    "start": "2022-12-31T23:00:00+00:00",
                    "end": "2023-01-01T23:00:00+00:00",
                },
            ],
            [
                "smus",
                {"start": "01/01/2023", "end": "02/01/2023"},
                {
                    "start": "2022-12-31T23:00:00+00:00",
                    "end": "2023-01-01T23:00:00+00:00",
                },
            ],
        ],
    )
    def test_compose_measurement_period(self, duo_facility, schedule, expected):
        self.scicat_measurements.duo_facility = duo_facility
        mp = self.scicat_measurements.compose_measurement_period(schedule)
        assert mp == {
            "id": ANY,
            "instrument": "/PSI/SLS/PX",
            **expected,
            "comment": "",
        }

    @patch("scicat.log.info", autospec=True)
    def test_measurement_period_list(self, mock_log_info):
        measurement_periods = self.scicat_measurements.measurement_period_list
        assert (
            measurement_periods
            == FixturesFromDuo.expected_scicat_proposal["MeasurementPeriodList"]
        )
        call_count = mock_log_info.call_count
        measurement_periods1 = self.scicat_measurements.measurement_period_list
        assert (
            measurement_periods1
            == FixturesFromDuo.expected_scicat_proposal["MeasurementPeriodList"]
        )
        assert mock_log_info.call_count == call_count

    @pytest.mark.parametrize(
        "duo_facility, test_date",
        [
            ["sinq", "01/01/2023"],
            ["smus", "01/01/2023"],
            ["sls", "01/01/2023 00:00:00"],
        ],
    )
    def test__datetime_to_utc(self, duo_facility, test_date):
        self.scicat_measurements.duo_facility = duo_facility
        utc_date = self.scicat_measurements._datetime_to_utc(test_date)
        assert utc_date == "2022-12-31T23:00:00+00:00"

    @pytest.mark.parametrize(
        "proposals, expected",
        [
            [FixturesFromSciCatAPI.same_proposals_measurement_periods, True],
            [[FixturesFromSciCatAPI.same_proposals_measurement_periods[0]], False],
            [
                FixturesFromSciCatAPI.same_proposals_measurement_periods
                + FixturesFromSciCatAPI.measurement_periods,
                False,
            ],
            [FixturesFromSciCatAPI.measurement_periods, False],
        ],
    )
    def test_is_same_measurements(self, proposals, expected):
        keep_proposals = self.scicat_measurements.is_same_measurements(proposals)
        assert keep_proposals == expected

    @pytest.mark.parametrize(
        "beamline_data, proposal_date, expected",
        [
            [["MS", "X06SA"], datetime.datetime(2025, 11, 30), True],
            [["MS"], datetime.datetime(2025, 12, 2), False],
            (("MS", "X06SA"), datetime.datetime(2025, 1, 1), False),
            ("MS", datetime.datetime(2025, 1, 1), False),
        ],
    )
    def test_keep_beamline(self, beamline_data, proposal_date, expected):
        self.scicat_measurements.duo_proposal = {"beamline": beamline_data}
        result = self.scicat_measurements.keep_beamline(proposal_date)
        assert result == expected
