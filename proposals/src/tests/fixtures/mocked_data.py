from unittest.mock import ANY, Mock


class FixturesCommon:

    scicat_proposal = {
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

    @staticmethod
    def measurement_period_list(ids=[ANY, ANY]):
        return [
            {
                "id": ids[0],
                "instrument": "/PSI/SLS/PX",
                "start": "2022-12-31T23:00:00+00:00",
                "end": "2023-01-01T23:00:00+00:00",
                "comment": "",
            },
            {
                "id": ids[1],
                "instrument": "/PSI/SLS/PX",
                "start": "2023-12-31T23:00:00+00:00",
                "end": "2024-01-01T23:00:00+00:00",
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

    expeted_measurement_periods = [
        FixturesCommon.measurement_period_list(["to_include_new_from_duo", None])[0]
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
