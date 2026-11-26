from unittest.mock import patch

import pytest

import main


@pytest.mark.parametrize(
    "argv, orchestrator",
    [
        [[], "RetentionOrchestrator"],
        [["retention"], "RetentionOrchestrator"],
        [["mark-expired"], "MarkExpiredOrchestrator"],
    ],
)
def test_main_runs_the_command_orchestrator(argv, orchestrator):
    with patch(f"main.{orchestrator}", autospec=True) as mock_orchestrator:
        main.main(argv)
    mock_orchestrator.assert_called_once()
    mock_orchestrator.return_value.orchestrate.assert_called_once()


def test_main_rejects_unknown_command():
    with pytest.raises(SystemExit):
        main.main(["unknown"])
