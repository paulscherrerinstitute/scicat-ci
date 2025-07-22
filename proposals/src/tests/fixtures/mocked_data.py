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

    expected_measurement_periods = [
        FixturesCommon.measurement_period_list([ANY, None])[0]
    ]

    measurement_periods = [
        Mock(**FixturesCommon.measurement_period_list([None, 789])[1]),
        Mock(
            **{
                "id": 0,
                "instrument": "/PSI/SLS/PX",
                "start": "2021-12-31T23:00:00+00:00",
                "end": "2022-01-01T23:00:00+00:00",
                "comment": "",
            }
        ),
    ]


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

    expected_measurement_periods = [
        {
            "id": ANY,
            "instrument": "/PSI/SLS/PX",
            "comment": "",
            "start": "1960-01-01T00:00:00+00:00",
            "end": "2100-12-31T00:00:00+00:00",
        },
    ]

    expected_scicat_proposal = {
        **FixturesCommon.scicat_proposal,
        "title": "",
        "pi_email": "john@doe",
        "abstract": "",
        "ownerGroup": "123",
        "MeasurementPeriodList": expected_measurement_periods,
    }

    policy = {
        **FixturesCommon.policy,
        "manager": ["john@doe"],
        "ownerGroup": "123",
    }
