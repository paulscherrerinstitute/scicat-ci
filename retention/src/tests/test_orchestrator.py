import os
from unittest.mock import ANY, Mock, patch

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
                "NOTIFICATION_CONTACT_EMAILS": " a@psi.ch, b@psi.ch ,",
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
        job1.advance.assert_called_once_with(ANY, ["a@psi.ch", "b@psi.ch"])
        job2.advance.assert_called_once_with(ANY, ["a@psi.ch", "b@psi.ch"])

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

        revert1.notify.assert_called_once_with(ANY, ["a@psi.ch", "b@psi.ch"])
        revert2.notify.assert_called_once_with(ANY, ["a@psi.ch", "b@psi.ch"])

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

        other_job.advance.assert_called_once_with(ANY, ["a@psi.ch", "b@psi.ch"])
        other_revert.notify.assert_called_once_with(ANY, ["a@psi.ch", "b@psi.ch"])
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

        revert.notify.assert_called_once_with(ANY, ["a@psi.ch", "b@psi.ch"])
        mock_log.error.assert_called_once()


class TestContactEmailsFromEnv:

    @patch.dict(os.environ, {"NOTIFICATION_CONTACT_EMAILS": " , "})
    def test_rejects_empty_list(self):
        with pytest.raises(ValueError):
            orchestrator.RetentionOrchestrator._contact_emails_from_env()

    @patch.dict(os.environ, clear=True)
    def test_requires_the_variable(self):
        with pytest.raises(KeyError):
            orchestrator.RetentionOrchestrator._contact_emails_from_env()
