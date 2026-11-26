import os
from unittest.mock import ANY, Mock, call, patch

import pytest

import orchestrator


class TestRetentionOrchestrator:

    def setup_method(self):
        self.env_patch = patch.dict(
            os.environ,
            {
                "SCICAT_ENDPOINT": "http://scicat",
                "SCICAT_USERNAME": "test_user",
                "SCICAT_PASSWORD": "test_password",
            },
        )
        self.env_patch.start()
        self.orchestrator = orchestrator.RetentionOrchestrator()

    def teardown_method(self):
        self.env_patch.stop()

    @patch(
        "orchestrator.RevertMarkForDeletionJobsRepository.unnotified_jobs",
        autospec=True,
        return_value=[],
    )
    @patch("orchestrator.MarkedForDeletionJobsRepository.due_jobs", autospec=True)
    @patch("orchestrator.SciCatAuth.authenticate", autospec=True)
    def test_orchestrate_advances_every_due_job(
        self, mock_authenticate, mock_due_jobs, _
    ):
        job1, job2 = Mock(), Mock()
        mock_due_jobs.return_value = [job1, job2]

        self.orchestrator.orchestrate()

        mock_authenticate.assert_called_once()
        mock_due_jobs.assert_called_once_with(self.orchestrator.jobs, ANY)
        job1.advance.assert_called_once_with(ANY)
        job2.advance.assert_called_once_with(ANY)

    @patch(
        "orchestrator.RevertMarkForDeletionJobsRepository.unnotified_jobs",
        autospec=True,
    )
    @patch(
        "orchestrator.MarkedForDeletionJobsRepository.due_jobs",
        autospec=True,
        return_value=[],
    )
    @patch("orchestrator.SciCatAuth.authenticate", autospec=True)
    def test_orchestrate_notifies_every_unnotified_revert(
        self, _, __, mock_unnotified_jobs
    ):
        revert1, revert2 = Mock(), Mock()
        mock_unnotified_jobs.return_value = [revert1, revert2]

        self.orchestrator.orchestrate()

        revert1.notify.assert_called_once_with(ANY)
        revert2.notify.assert_called_once_with(ANY)

    @patch("orchestrator.log")
    @patch(
        "orchestrator.RevertMarkForDeletionJobsRepository.unnotified_jobs",
        autospec=True,
    )
    @patch("orchestrator.MarkedForDeletionJobsRepository.due_jobs", autospec=True)
    @patch("orchestrator.SciCatAuth.authenticate", autospec=True)
    def test_orchestrate_logs_and_continues_on_error(
        self, _, mock_due_jobs, mock_unnotified_jobs, mock_log
    ):
        failing_job = Mock(id="job1")
        failing_job.advance.side_effect = Exception("boom")
        other_job = Mock(id="job2")
        mock_due_jobs.return_value = [failing_job, other_job]
        failing_revert = Mock(id="revert1")
        failing_revert.notify.side_effect = Exception("boom")
        other_revert = Mock(id="revert2")
        mock_unnotified_jobs.return_value = [failing_revert, other_revert]

        self.orchestrator.orchestrate()

        other_job.advance.assert_called_once_with(ANY)
        other_revert.notify.assert_called_once_with(ANY)
        assert mock_log.error.call_count == 2

    @patch("orchestrator.log")
    @patch(
        "orchestrator.RevertMarkForDeletionJobsRepository.unnotified_jobs",
        autospec=True,
    )
    @patch(
        "orchestrator.MarkedForDeletionJobsRepository.due_jobs",
        autospec=True,
        side_effect=RuntimeError("query failed"),
    )
    @patch("orchestrator.SciCatAuth.authenticate", autospec=True)
    def test_orchestrate_notifies_reverts_even_if_check_in_fails(
        self, _, __, mock_unnotified_jobs, mock_log
    ):
        revert = Mock()
        mock_unnotified_jobs.return_value = [revert]

        self.orchestrator.orchestrate()

        revert.notify.assert_called_once_with(ANY)
        mock_log.error.assert_called_once()


class TestMarkExpiredOrchestrator:

    def setup_method(self):
        self.env_patch = patch.dict(
            os.environ,
            {
                "SCICAT_ENDPOINT": "http://scicat",
                "SCICAT_USERNAME": "test_user",
                "SCICAT_PASSWORD": "test_password",
                "EXPIRED_RETENTION_TIME": "3M",
            },
        )
        self.env_patch.start()
        self.orchestrator = orchestrator.MarkExpiredOrchestrator()

    def teardown_method(self):
        self.env_patch.stop()

    @patch("orchestrator.log")
    @patch("orchestrator.submit_expired_marked_for_deletion", autospec=True)
    @patch(
        "orchestrator.ExpiredDatasetsRepository.expired_pids_by_owner_group",
        autospec=True,
        return_value={"group1": ["pid1"], "group2": ["pid2"], "group3": ["pid3"]},
    )
    @patch("orchestrator.SciCatAuth.authenticate", autospec=True)
    def test_orchestrate_marks_every_group_and_continues_on_error(
        self, mock_authenticate, _, mock_submit, mock_log
    ):
        mock_submit.side_effect = [None, Exception("boom"), None]

        self.orchestrator.orchestrate()

        mock_authenticate.assert_called_once()
        assert mock_submit.call_args_list == [
            call("group1", ["pid1"], "3M"),
            call("group2", ["pid2"], "3M"),
            call("group3", ["pid3"], "3M"),
        ]
        mock_log.error.assert_called_once()

    @pytest.mark.parametrize("value", [None, "3 months"])
    def test_requires_a_valid_retention_time(self, value):
        with patch.dict(os.environ):
            if value is None:
                del os.environ["EXPIRED_RETENTION_TIME"]
            else:
                os.environ["EXPIRED_RETENTION_TIME"] = value
            with pytest.raises((KeyError, ValueError)):
                orchestrator.MarkExpiredOrchestrator()
