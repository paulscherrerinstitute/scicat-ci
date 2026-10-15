import json
import os
from unittest.mock import ANY, Mock, patch

import pytest
from dateutil.relativedelta import relativedelta

import scicat

from .fixtures.mocked_data import FixturesJobs


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


class TestMarkedForDeletionJob:

    def test_id(self):
        job = scicat.MarkedForDeletionJob(FixturesJobs.raw_job())
        assert job.id == FixturesJobs.job_id

    def test_dataset_pids(self):
        job = scicat.MarkedForDeletionJob(FixturesJobs.raw_job())
        assert job.dataset_pids == FixturesJobs.dataset_pids

    @pytest.mark.parametrize(
        "retention_time, expected",
        [
            [{"value": 3, "unit": "M"}, 3],
            [{"value": 6, "unit": "d"}, 6],
            [{"value": 2, "unit": "h"}, 2],
            [{"value": 10, "unit": "m"}, 10],  # lowercase m is minutes, not months
            [{"value": 45, "unit": "s"}, 45],
            [{"value": 1, "unit": "Y"}, 1],
        ],
    )
    def test_retention_amount_reads_the_unit_from_the_object(
        self, retention_time, expected
    ):
        job = scicat.MarkedForDeletionJob(
            FixturesJobs.raw_job(job_result_object={"retentionTime": retention_time})
        )
        assert job.retention_amount == expected

    @pytest.mark.parametrize(
        "retention_time",
        [
            None,
            {},
            "3M",
            {"value": 3},
            {"unit": "M"},
            {"value": "3", "unit": "M"},
            {"value": 3, "unit": "X"},
            {"value": True, "unit": "M"},
        ],
    )
    def test_retention_amount_rejects_malformed_retention_time(self, retention_time):
        job = scicat.MarkedForDeletionJob(
            FixturesJobs.raw_job(job_result_object={"retentionTime": retention_time})
        )
        with pytest.raises(ValueError):
            job.retention_amount

    def test_expiry_date_uses_the_retention_time_unit(self):
        job = scicat.MarkedForDeletionJob(
            FixturesJobs.raw_job(
                job_result_object={"retentionTime": {"value": 1, "unit": "Y"}}
            )
        )
        assert job.expiry_date == FixturesJobs.creation_time + relativedelta(years=1)

    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    def test_advance_not_expired(self, mock_update):
        job = scicat.MarkedForDeletionJob(
            FixturesJobs.raw_job(
                job_result_object={"retentionTime": {"value": 3, "unit": "M"}}
            )
        )
        now = FixturesJobs.creation_time + relativedelta(months=1)
        job.advance(now)
        mock_update.assert_called_once_with(
            ANY,
            FixturesJobs.job_id,
            {
                "jobResultObject": {
                    "retentionTime": {"value": 3, "unit": "M"},
                    "lastVerifiedAt": now.isoformat(),
                },
            },
        )

    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    def test_advance_expires(self, mock_update):
        job = scicat.MarkedForDeletionJob(
            FixturesJobs.raw_job(
                job_result_object={"retentionTime": {"value": 3, "unit": "M"}}
            )
        )
        now = FixturesJobs.creation_time + relativedelta(months=3)
        job.advance(now)
        mock_update.assert_called_once_with(
            ANY,
            FixturesJobs.job_id,
            {
                "jobResultObject": {
                    "retentionTime": {"value": 3, "unit": "M"},
                    "lastVerifiedAt": now.isoformat(),
                },
                "jobStatusMessage": "retentionExpired",
            },
        )


class TestMarkedForDeletionJobsRepository:

    @patch("scicat.JobsApi.jobs_controller_find_all_v3", autospec=True)
    def test_due_jobs(self, mock_find_all):
        raw_job = FixturesJobs.raw_job()
        mock_find_all.side_effect = [[raw_job], []]
        now = FixturesJobs.creation_time + relativedelta(months=2)

        jobs = list(scicat.MarkedForDeletionJobsRepository().due_jobs(now))

        assert len(jobs) == 1
        assert isinstance(jobs[0], scicat.MarkedForDeletionJob)
        assert jobs[0].id == FixturesJobs.job_id

        _, kwargs = mock_find_all.call_args_list[0]
        assert json.loads(kwargs["filter"]) == {
            "where": {
                "type": "markedForDeletion",
                "jobStatusMessage": {"neq": "retentionExpired"},
                "datasetList": {"neq": []},
                "jobResultObject.lastVerifiedAt": {
                    "lte": (now - relativedelta(months=1)).isoformat()
                },
            },
            "fields": ["id", "datasetList", "jobResultObject", "creationTime"],
            "limits": {"skip": 0, "limit": 100},
        }

    @patch("scicat.JobsApi.jobs_controller_find_all_v3", autospec=True)
    def test_due_jobs_paginates_across_multiple_pages(self, mock_find_all):
        page1 = [
            FixturesJobs.raw_job(job_id="job1"),
            FixturesJobs.raw_job(job_id="job2"),
        ]
        page2 = [FixturesJobs.raw_job(job_id="job3")]
        mock_find_all.side_effect = [page1, page2, []]
        now = FixturesJobs.creation_time + relativedelta(months=2)

        repository = scicat.MarkedForDeletionJobsRepository()
        repository.page_limit = 2
        jobs = repository.due_jobs(now)

        assert [job.id for job in jobs] == ["job1", "job2", "job3"]
        assert mock_find_all.call_count == 3
        skips = [
            json.loads(kwargs["filter"])["limits"]["skip"]
            for _, kwargs in mock_find_all.call_args_list
        ]
        assert skips == [0, 2, 4]

    @patch("scicat.JobsApi.jobs_controller_find_all_v3", autospec=True)
    def test_due_jobs_fetches_pages_lazily(self, mock_find_all):
        page1 = [
            FixturesJobs.raw_job(job_id="job1"),
            FixturesJobs.raw_job(job_id="job2"),
        ]
        page2 = [FixturesJobs.raw_job(job_id="job3")]
        mock_find_all.side_effect = [page1, page2, []]
        now = FixturesJobs.creation_time + relativedelta(months=2)

        repository = scicat.MarkedForDeletionJobsRepository()
        repository.page_limit = 2
        jobs = repository.due_jobs(now)

        assert next(jobs).id == "job1"
        assert mock_find_all.call_count == 1
        assert next(jobs).id == "job2"
        assert mock_find_all.call_count == 1
        assert next(jobs).id == "job3"
        assert mock_find_all.call_count == 2

    @patch("scicat.JobsApi.jobs_controller_find_all_v3", autospec=True)
    def test_due_jobs_raises_after_max_iterations(self, mock_find_all):
        mock_find_all.return_value = [FixturesJobs.raw_job()]
        now = FixturesJobs.creation_time + relativedelta(months=2)

        repository = scicat.MarkedForDeletionJobsRepository()
        repository.max_iterations = 3

        with pytest.raises(RuntimeError):
            list(repository.due_jobs(now))
        assert mock_find_all.call_count == 3
