import os
from unittest.mock import ANY, Mock, patch

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

    @patch("orchestrator.MarkedForDeletionJobsRepository.due_jobs", autospec=True)
    @patch("orchestrator.SciCatAuth.authenticate", autospec=True)
    def test_orchestrate_advances_every_due_job(self, mock_authenticate, mock_due_jobs):
        job1, job2 = Mock(), Mock()
        mock_due_jobs.return_value = [job1, job2]

        self.orchestrator.orchestrate()

        mock_authenticate.assert_called_once()
        mock_due_jobs.assert_called_once_with(self.orchestrator.jobs, ANY)
        job1.advance.assert_called_once_with(ANY)
        job2.advance.assert_called_once_with(ANY)

    @patch("orchestrator.log")
    @patch("orchestrator.MarkedForDeletionJobsRepository.due_jobs", autospec=True)
    @patch("orchestrator.SciCatAuth.authenticate", autospec=True)
    def test_orchestrate_logs_and_continues_on_error(self, _, mock_due_jobs, mock_log):
        failing_job = Mock(id="job1")
        failing_job.advance.side_effect = Exception("boom")
        other_job = Mock(id="job2")
        mock_due_jobs.return_value = [failing_job, other_job]

        self.orchestrator.orchestrate()

        other_job.advance.assert_called_once_with(ANY)
        mock_log.error.assert_called_once()
