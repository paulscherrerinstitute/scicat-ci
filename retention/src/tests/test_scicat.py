import json
import os
from unittest.mock import ANY, Mock, call, patch

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

    @staticmethod
    def _notification(owner_group, pids, expired):
        return {
            "type": "notification",
            "datasetList": [{"pid": pid, "files": []} for pid in pids],
            "jobParams": {
                "ownerGroup": owner_group,
                "markedForDeletionJobId": FixturesJobs.job_id,
                "expiryDate": (
                    FixturesJobs.creation_time + relativedelta(months=3)
                ).isoformat(),
                "expired": expired,
            },
        }

    @patch("scicat.JobsApi.jobs_controller_create_v3", autospec=True)
    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        side_effect=FixturesJobs.dataset_pages({"pid1": "group1", "pid2": "group1"}),
    )
    def test_advance_first_check_in(self, _, mock_update, mock_create):
        job = scicat.MarkedForDeletionJob(FixturesJobs.raw_job())
        now = FixturesJobs.creation_time
        job.advance(now)
        mock_create.assert_called_once_with(
            ANY, self._notification("group1", ["pid1", "pid2"], expired=False)
        )
        mock_update.assert_called_once_with(
            ANY,
            FixturesJobs.job_id,
            {
                "jobResultObject": {
                    "retentionTime": {"value": 3, "unit": "M"},
                    "lastVerifiedAt": now.isoformat(),
                    "verifiedAt": [now.isoformat()],
                },
            },
        )

    @patch("scicat.JobsApi.jobs_controller_create_v3", autospec=True)
    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        side_effect=FixturesJobs.dataset_pages({"pid1": "group1", "pid2": "group2"}),
    )
    def test_advance_not_expired(self, mock_find_datasets, mock_update, mock_create):
        previous = FixturesJobs.creation_time.isoformat()
        job = scicat.MarkedForDeletionJob(
            FixturesJobs.raw_job(
                job_result_object={
                    "retentionTime": {"value": 3, "unit": "M"},
                    "lastVerifiedAt": previous,
                    "verifiedAt": [previous],
                }
            )
        )
        now = FixturesJobs.creation_time + relativedelta(months=1)
        job.advance(now)
        _, kwargs = mock_find_datasets.call_args_list[0]
        assert json.loads(kwargs["filter"]) == {
            "where": {"pid": {"$in": ["pid1", "pid2"]}},
            "fields": ["pid", "ownerGroup"],
            "limits": {"skip": 0, "limit": 100},
        }
        assert mock_create.call_args_list == [
            call(ANY, self._notification("group1", ["pid1"], expired=False)),
            call(ANY, self._notification("group2", ["pid2"], expired=False)),
        ]
        mock_update.assert_called_once_with(
            ANY,
            FixturesJobs.job_id,
            {
                "jobResultObject": {
                    "retentionTime": {"value": 3, "unit": "M"},
                    "lastVerifiedAt": now.isoformat(),
                    "verifiedAt": [previous, now.isoformat()],
                },
            },
        )

    @staticmethod
    def _delete(pids):
        return {
            "type": "delete",
            "datasetList": [{"pid": pid, "files": []} for pid in pids],
        }

    # At expiry the datasets query runs twice: first for the owner groups to
    # notify, then for the datasets still marked for deletion.
    @patch("scicat.JobsApi.jobs_controller_create_v3", autospec=True)
    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        side_effect=FixturesJobs.dataset_pages({"pid1": "group1", "pid2": "group1"})
        + FixturesJobs.dataset_pages({"pid1": "group1", "pid2": "group1"}),
    )
    def test_advance_expires(self, mock_find_datasets, mock_update, mock_create):
        job = scicat.MarkedForDeletionJob(FixturesJobs.raw_job())
        now = FixturesJobs.creation_time + relativedelta(months=3)
        job.advance(now)
        assert mock_create.call_args_list == [
            call(ANY, self._notification("group1", ["pid1", "pid2"], expired=True)),
            call(ANY, self._delete(["pid1", "pid2"])),
        ]
        _, kwargs = mock_find_datasets.call_args_list[2]
        assert json.loads(kwargs["filter"]) == {
            "where": {
                "pid": {"$in": ["pid1", "pid2"]},
                "datasetlifecycle.archiveStatusMessage": "markedForDeletion",
            },
            "fields": ["pid"],
            "limits": {"skip": 0, "limit": 100},
        }
        mock_update.assert_called_once_with(
            ANY,
            FixturesJobs.job_id,
            {
                "jobResultObject": {
                    "retentionTime": {"value": 3, "unit": "M"},
                    "lastVerifiedAt": now.isoformat(),
                    "verifiedAt": [now.isoformat()],
                },
                "jobStatusMessage": "retentionExpired",
            },
        )

    @patch("scicat.JobsApi.jobs_controller_create_v3", autospec=True)
    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        side_effect=FixturesJobs.dataset_pages({"pid1": "group1", "pid2": "group1"})
        + FixturesJobs.dataset_pages({"pid2": "group1"}),
    )
    def test_advance_expires_only_deletes_datasets_the_query_returns(
        self, _, mock_update, mock_create
    ):
        # pid1 is missing from the results — whether because it's no longer
        # markedForDeletion (restored) or gone entirely (deleted), the query
        # already excludes it; this service has no opinion on why.
        job = scicat.MarkedForDeletionJob(FixturesJobs.raw_job())
        job.advance(
            FixturesJobs.creation_time + relativedelta(months=3),
        )
        assert mock_create.call_args_list[-1] == call(ANY, self._delete(["pid2"]))

    @patch("scicat.JobsApi.jobs_controller_create_v3", autospec=True)
    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        side_effect=FixturesJobs.dataset_pages({"pid1": "group1", "pid2": "group1"})
        + [[]],
    )
    def test_advance_expires_skips_delete_job_when_none_still_marked(
        self, _, mock_update, mock_create
    ):
        job = scicat.MarkedForDeletionJob(FixturesJobs.raw_job())
        job.advance(
            FixturesJobs.creation_time + relativedelta(months=3),
        )
        assert mock_create.call_args_list == [
            call(ANY, self._notification("group1", ["pid1", "pid2"], expired=True)),
        ]
        assert mock_update.call_args[0][2]["jobStatusMessage"] == "retentionExpired"

    @patch("scicat.JobsApi.jobs_controller_create_v3", autospec=True)
    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        side_effect=FixturesJobs.dataset_pages({"pid1": "group1", "pid2": "group1"})
        + FixturesJobs.dataset_pages({"pid1": "group1", "pid2": "group1"}),
    )
    def test_advance_does_not_record_expiry_if_delete_job_fails(
        self, _, mock_update, mock_create
    ):
        mock_create.side_effect = [Mock(), Exception("boom")]
        job = scicat.MarkedForDeletionJob(FixturesJobs.raw_job())
        with pytest.raises(Exception):
            job.advance(
                FixturesJobs.creation_time + relativedelta(months=3),
            )
        mock_update.assert_not_called()

    @patch("scicat.DATASETS_PAGE_LIMIT", 2)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        side_effect=FixturesJobs.dataset_pages(
            {"pid1": "group1", "pid2": "group1"}, {"pid3": "group1"}
        ),
    )
    def test_still_marked_pids_paginates_across_multiple_pages(
        self, mock_find_datasets
    ):
        job = scicat.MarkedForDeletionJob(
            FixturesJobs.raw_job(dataset_pids=["pid1", "pid2", "pid3"])
        )

        assert job._still_marked_pids() == ["pid1", "pid2", "pid3"]
        skips = [
            json.loads(kwargs["filter"])["limits"]["skip"]
            for _, kwargs in mock_find_datasets.call_args_list
        ]
        assert skips == [0, 2, 4]

    @patch("scicat.JobsApi.jobs_controller_create_v3", autospec=True)
    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        side_effect=FixturesJobs.dataset_pages({"pid1": "group1"}),
    )
    def test_advance_skips_missing_datasets(self, _, mock_update, mock_create):
        job = scicat.MarkedForDeletionJob(FixturesJobs.raw_job())
        job.advance(FixturesJobs.creation_time)
        mock_create.assert_called_once_with(
            ANY, self._notification("group1", ["pid1"], expired=False)
        )
        mock_update.assert_called_once()

    @patch("scicat.JobsApi.jobs_controller_create_v3", autospec=True)
    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        side_effect=FixturesJobs.dataset_pages({"pid1": "group1", "pid2": "group1"}),
    )
    def test_advance_does_not_record_check_in_if_notification_fails(
        self, _, mock_update, mock_create
    ):
        mock_create.side_effect = Exception("boom")
        job = scicat.MarkedForDeletionJob(FixturesJobs.raw_job())
        with pytest.raises(Exception):
            job.advance(FixturesJobs.creation_time)
        mock_update.assert_not_called()

    @patch("scicat.DATASETS_PAGE_LIMIT", 2)
    @patch("scicat.JobsApi.jobs_controller_create_v3", autospec=True)
    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        side_effect=FixturesJobs.dataset_pages(
            {"pid1": "group1", "pid2": "group2"}, {"pid3": "group1"}
        ),
    )
    def test_advance_paginates_datasets(
        self, mock_find_datasets, mock_update, mock_create
    ):
        job = scicat.MarkedForDeletionJob(
            FixturesJobs.raw_job(dataset_pids=["pid1", "pid2", "pid3"])
        )
        job.advance(FixturesJobs.creation_time)
        skips = [
            json.loads(kwargs["filter"])["limits"]["skip"]
            for _, kwargs in mock_find_datasets.call_args_list
        ]
        assert skips == [0, 2, 4]
        assert mock_create.call_args_list == [
            call(ANY, self._notification("group1", ["pid1", "pid3"], expired=False)),
            call(ANY, self._notification("group2", ["pid2"], expired=False)),
        ]

    @patch("scicat.DATASETS_MAX_ITERATIONS", 2)
    @patch("scicat.JobsApi.jobs_controller_create_v3", autospec=True)
    @patch("scicat.JobsApi.jobs_controller_update_v3", autospec=True)
    @patch(
        "scicat.DatasetsV4Api.datasets_v4_controller_find_all_v4",
        autospec=True,
        return_value=FixturesJobs.datasets({"pid1": "group1"}),
    )
    def test_advance_raises_after_max_dataset_pages(self, _, mock_update, mock_create):
        job = scicat.MarkedForDeletionJob(FixturesJobs.raw_job())
        with pytest.raises(RuntimeError):
            job.advance(FixturesJobs.creation_time)
        mock_create.assert_not_called()
        mock_update.assert_not_called()


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
                "or": [
                    {"jobResultObject.verifiedAt": None},
                    {
                        "jobResultObject.lastVerifiedAt": {
                            "lte": (now - relativedelta(months=1)).isoformat()
                        }
                    },
                ],
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
