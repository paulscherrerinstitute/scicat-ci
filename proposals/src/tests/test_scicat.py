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

    class DummySciCatFromDuo(scicat.SciCatFromDuo):
        def compose(self):
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


class TestSciCatPolicyFromDuo:

    static_properties = {
        "tapeRedundancy": "low",
        "autoArchive": False,
        "autoArchiveDelay": 0,
        "archiveEmailNotification": True,
        "archiveEmailsToBeNotified": [],
        "retrieveEmailNotification": True,
        "retrieveEmailsToBeNotified": [],
        "embargoPeriod": 3,
    }

    scicat_policy = scicat.SciCatPolicyFromDuo(
        {"pgroup": "abc", "proposal": "123", "beamline": "PX", "pi_email": "pi_email"},
        "sls",
    )

    def test_compose(self):
        policy = self.scicat_policy.compose()
        expected = {
            "manager": ["pi_email"],
            "ownerGroup": "abc",
            "accessGroups": ["slsmx"],
        }
        assert policy == {**self.static_properties, **expected}


class TestSciCatProposalFromDuo:

    scicat_proposal = scicat.SciCatProposalFromDuo(
        {
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
                {"start": "01/01/2023 00:00:00", "end": "02/01/2023 00:00:00"},
                {"start": "01/01/2024 00:00:00", "end": "02/01/2024 00:00:00"},
            ],
        },
        "test_accelerator",
        "test_duo_facility",
    )

    def test_compose(self):
        proposal = self.scicat_proposal.compose()
        expected = {
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
            "accessGroups": ["test_acceleratormx"],
            "MeasurementPeriodList": [
                {
                    "id": ANY,
                    "instrument": "/PSI/TEST_ACCELERATOR/PX",
                    "start": "2022-12-31T23:00:00+00:00",
                    "end": "2023-01-01T23:00:00+00:00",
                    "comment": "",
                },
                {
                    "id": ANY,
                    "instrument": "/PSI/TEST_ACCELERATOR/PX",
                    "start": "2023-12-31T23:00:00+00:00",
                    "end": "2024-01-01T23:00:00+00:00",
                    "comment": "",
                },
            ],
        }

        assert proposal == expected


class TestSciCatMeasurementsFromDuoMixin:

    scicat_measurements = scicat.SciCatMeasurementsFromDuoMixin()
    scicat_measurements.duo_facility = "test_duo_facility"
    scicat_measurements.duo_proposal = {
        "beamline": "px",
        "schedule": [
            {"start": "01/01/2023", "end": "02/01/2023"},
            {"start": "01/01/2024", "end": "02/01/2024"},
        ],
    }
    scicat_measurements.accelerator = "test_accelerator"

    def test_init(self):
        assert self.scicat_measurements.duo_proposal == {
            "beamline": "px",
            "schedule": [
                {"start": "01/01/2023", "end": "02/01/2023"},
                {"start": "01/01/2024", "end": "02/01/2024"},
            ],
        }

        assert self.scicat_measurements.accelerator == "test_accelerator"
        assert self.scicat_measurements.duo_facility == "test_duo_facility"

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
            "instrument": "/PSI/TEST_ACCELERATOR/PX",
            **expected,
            "comment": "",
        }

    def test_meausement_period_list(self):
        measurement_periods = self.scicat_measurements.meausement_period_list
        assert measurement_periods == [
            {
                "id": ANY,
                "instrument": "/PSI/TEST_ACCELERATOR/PX",
                "start": "2022-12-31T23:00:00+00:00",
                "end": "2023-01-01T23:00:00+00:00",
                "comment": "",
            },
            {
                "id": ANY,
                "instrument": "/PSI/TEST_ACCELERATOR/PX",
                "start": "2023-12-31T23:00:00+00:00",
                "end": "2024-01-01T23:00:00+00:00",
                "comment": "",
            },
        ]

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
