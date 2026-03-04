from datetime import datetime
from unittest.mock import ANY, Mock


class FixturesCommon:

    scicat_proposal = {
        "proposalId": "20.500.11935/123",
        "pi_email": "pi_email",
        "pi_firstname": "John",
        "pi_lastname": "Doe",
        "email": "john@doe",
        "firstname": "John",
        "lastname": "Doe",
        "title": "Test Proposal",
        "abstract": "This is a test proposal.",
        "ownerGroup": "test_group",
        "accessGroups": ["slsmx"],
    }

    @staticmethod
    def measurement_period_list(ids=[ANY, ANY], measurements=None):
        _measurements = measurements or [
            {
                "start": "2022-12-31T23:00:00+00:00",
                "end": "2023-01-01T23:00:00+00:00",
            },
            {
                "start": "2023-12-31T23:00:00+00:00",
                "end": "2024-01-01T23:00:00+00:00",
            },
        ]
        return [
            {
                "id": ids[0],
                "instrument": "/PSI/SLS/PX",
                **_measurements[0],
                "comment": "",
            },
            {
                "id": ids[1],
                "instrument": "/PSI/SLS/PX",
                **_measurements[1],
                "comment": "",
            },
        ]

    policy = {
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


class FixturesFromDuo(FixturesCommon):

    accelerator = "sls"
    duo_facility = "sls"

    duo_proposal = {
        "proposal": "123",
        "pi_firstname": "John",
        "pi_lastname": "Doe",
        "email": "john@doe",
        "firstname": "John",
        "lastname": "Doe",
        "title": "Test Proposal",
        "abstract": "This is a test proposal.",
        "pgroup": "test_group",
        "beamline": "PX",
        "pi_email": "pi_email",
        "schedule": [
            {"start": "01/01/2023 00:00:00", "end": "02/01/2023 00:00:00"},
            {"start": "01/01/2024 00:00:00", "end": "02/01/2024 00:00:00"},
        ],
    }

    scicat_proposal = {
        **FixturesCommon.scicat_proposal,
        "MeasurementPeriodList": FixturesCommon.measurement_period_list(
            ["to_include_new_from_duo", "to_exclude_on_update_because_789_scicat"]
        ),
    }

    expected_scicat_proposal = {
        **FixturesCommon.scicat_proposal,
        "MeasurementPeriodList": FixturesCommon.measurement_period_list(),
    }


class FixturesFromSciCatAPI(FixturesCommon):

    # this is the result from the first schedule from duo proposal.
    # The second schedule is excluded because == existing_measurment_periods[0]
    new_measurment_period = FixturesCommon.measurement_period_list([ANY, None])[0]

    existing_measurment_periods = [
        FixturesCommon.measurement_period_list([None, 789])[1],
        {
            "id": 0,
            "instrument": "/PSI/SLS/PX",
            "start": "2021-12-31T23:00:00+00:00",
            "end": "2022-01-01T23:00:00+00:00",
            "comment": "",
        },
    ]

    @staticmethod
    def measurement_periods_mock(measurement_periods):
        return list(
            map(
                lambda x: Mock(
                    **{
                        **x,
                        "start": datetime.fromisoformat(x["start"]),
                        "end": datetime.fromisoformat(x["end"]),
                    }
                ),
                measurement_periods,
            )
        )

    measurement_periods = measurement_periods_mock(existing_measurment_periods)

    same_proposals_measurement_periods = measurement_periods_mock(
        FixturesCommon.measurement_period_list()
    )

    expected_measurement_periods = FixturesCommon.measurement_period_list()


class FixturesProposalsFromFacility(FixturesFromDuo, FixturesFromSciCatAPI):
    pass


class FixturesProposalsFromPgroups(FixturesCommon):

    duo_facility = "pgroups"

    calendar_infos_facilities = [
        {
            "name": FixturesFromDuo.duo_facility,
            "beamlines": [
                {
                    "name": "PX",
                    "xname": "xbeam1",
                    "active": True,
                },
            ],
        },
    ]

    _pgroups_with_no_proposal = [
        {"g": "123", "p": []},
    ]

    _pgroup_no_proposal_formatter = {
        "group": {
            "name": "123",
            "xname": "xbeam1",
            "comments": "",
            "owner": {
                "firstname": "John",
                "lastname": "Doe",
                "email": "john@doe",
            },
        },
    }

    _duo_measurement = {
        "id": ANY,
        "instrument": "/PSI/SLS/PX",
        "comment": "",
        "start": "1960-01-01T00:00:00+00:00",
        "end": "2100-12-31T00:00:00+00:00",
    }

    expected_measurement_periods = [
        _duo_measurement,
    ]

    expected_scicat_proposal = {
        **FixturesCommon.scicat_proposal,
        "title": "20.500.11935/123",
        "pi_email": "john@doe",
        "abstract": "",
        "ownerGroup": "123",
        "MeasurementPeriodList": [_duo_measurement],
    }

    policy = {
        **FixturesCommon.policy,
        "manager": ["john@doe"],
        "ownerGroup": "123",
    }
