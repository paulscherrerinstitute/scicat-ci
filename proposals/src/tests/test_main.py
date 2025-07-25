from unittest.mock import patch

import main


@patch("main.DuoSciCatOrchestrator")
def test_main(mock_orchestrator):
    mock_instance = mock_orchestrator.return_value
    main.main()
    mock_orchestrator.assert_called_once()
    mock_instance.orchestrate.assert_called_once()
