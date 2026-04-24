"""
Unit tests for web_init_step.py
Target: Increase coverage from 19% to 80%+
"""
from unittest.mock import MagicMock

from cli.commands.init_cmd.web_init_step import perform_web_init


class TestPerformWebInit:
    """Test perform_web_init function"""

    def test_successful_web_init_with_config_data(
        self, mocker, mock_multiprocessing, mock_webbrowser, mock_wait_for_server
    ):
        """Test successful web initialization with configuration data"""
        mock_echo = mocker.patch("click.echo")

        # Simulate config data from web portal
        config_data = {
            "broker_url": "ws://localhost:8008",
            "namespace": "test_namespace/",
        }
        mock_multiprocessing["dict"].update(config_data)

        current_params = {"existing_param": "value"}
        result = perform_web_init(current_params)

        # Verify config was merged
        assert result["broker_url"] == "ws://localhost:8008"
        assert result["namespace"] == "test_namespace/"
        assert result["existing_param"] == "value"

        # Verify process was started and joined
        mock_multiprocessing["process"].start.assert_called_once()
        mock_multiprocessing["process"].join.assert_called_once()

        # Verify browser was opened
        mock_webbrowser.assert_called_once_with("http://127.0.0.1:5002")

    def test_web_init_no_config_data_received(
        self, mocker, mock_multiprocessing, mock_webbrowser, mock_wait_for_server
    ):
        """Test web init when no configuration data is received"""
        mock_echo = mocker.patch("click.echo")
        
        # Empty dict simulates no data from portal
        current_params = {"default_param": "default_value"}
        result = perform_web_init(current_params)
        
        # Should return original params unchanged
        assert result == current_params
        
        # Should show warning messages
        assert any(
            "No configuration data received" in str(call)
            for call in mock_echo.call_args_list
        )

    def test_web_init_server_fails_to_start(
        self, mocker, mock_multiprocessing, mock_webbrowser
    ):
        """Test web init when server fails to start"""
        mock_echo = mocker.patch("click.echo")
        mock_wait = mocker.patch(
            "cli.commands.init_cmd.web_init_step.wait_for_server",
            return_value=False
        )
        
        result = perform_web_init({})
        
        # Browser should not be opened
        mock_webbrowser.assert_not_called()
        
        # Should show error message
        assert any(
            "Server did not start in time" in str(call)
            for call in mock_echo.call_args_list
        )

    def test_web_init_browser_open_exception(
        self, mocker, mock_multiprocessing, mock_wait_for_server
    ):
        """Test web init when browser fails to open"""
        mock_echo = mocker.patch("click.echo")
        mock_browser = mocker.patch(
            "webbrowser.open",
            side_effect=Exception("Browser error")
        )
        
        result = perform_web_init({})
        
        # Should handle exception gracefully
        assert any(
            "Could not automatically open browser" in str(call)
            for call in mock_echo.call_args_list
        )

    def test_web_init_preserves_existing_params(
        self, mocker, mock_multiprocessing, mock_webbrowser, mock_wait_for_server
    ):
        """Test that existing parameters are preserved"""
        mock_echo = mocker.patch("click.echo")
        
        config_data = {"new_param": "new_value"}
        mock_multiprocessing["dict"].update(config_data)
        
        current_params = {
            "existing_param1": "value1",
            "existing_param2": "value2",
        }
        
        result = perform_web_init(current_params)
        
        assert result["existing_param1"] == "value1"
        assert result["existing_param2"] == "value2"
        assert result["new_param"] == "new_value"

    def test_web_init_multiprocessing_manager_context(
        self, mocker, mock_webbrowser, mock_wait_for_server
    ):
        """Test that multiprocessing Manager is used as context manager"""
        mock_echo = mocker.patch("click.echo")
        mock_manager = MagicMock()
        mock_dict = {}
        mock_manager.dict.return_value = mock_dict
        mock_manager.__enter__ = MagicMock(return_value=mock_manager)
        mock_manager.__exit__ = MagicMock(return_value=False)
        
        mock_process = MagicMock()
        
        mocker.patch("multiprocessing.Manager", return_value=mock_manager)
        mocker.patch("multiprocessing.Process", return_value=mock_process)
        
        perform_web_init({})
        
        # Verify context manager was used
        mock_manager.__enter__.assert_called_once()
        mock_manager.__exit__.assert_called_once()

    def test_web_init_process_arguments(self, mocker, mock_webbrowser, mock_wait_for_server):
        """Test that Process is created with correct arguments"""
        mock_echo = mocker.patch("click.echo")
        mock_manager = MagicMock()
        mock_dict = {}
        mock_manager.dict.return_value = mock_dict
        mock_manager.__enter__ = MagicMock(return_value=mock_manager)
        mock_manager.__exit__ = MagicMock(return_value=False)
        
        mock_process_class = mocker.patch("multiprocessing.Process")
        mock_process = MagicMock()
        mock_process_class.return_value = mock_process
        
        mocker.patch("multiprocessing.Manager", return_value=mock_manager)
        
        perform_web_init({})
        
        # Verify Process was created with correct args
        mock_process_class.assert_called_once()
        call_kwargs = mock_process_class.call_args[1]
        assert call_kwargs["args"] == ("127.0.0.1", 5002, mock_dict)

    def test_web_init_portal_url_construction(
        self, mocker, mock_multiprocessing, mock_webbrowser, mock_wait_for_server
    ):
        """Test that portal URL is constructed correctly"""
        mock_echo = mocker.patch("click.echo")
        
        perform_web_init({})
        
        # Verify correct URL was used
        mock_wait_for_server.assert_called_once_with("http://127.0.0.1:5002")
        mock_webbrowser.assert_called_once_with("http://127.0.0.1:5002")

    def test_web_init_messages_displayed(
        self, mocker, mock_multiprocessing, mock_webbrowser, mock_wait_for_server
    ):
        """Test that appropriate messages are displayed"""
        mock_echo = mocker.patch("click.echo")
        
        config_data = {"test": "data"}
        mock_multiprocessing["dict"].update(config_data)
        
        perform_web_init({})
        
        # Verify key messages were displayed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Attempting to start web-based configuration portal" in call for call in echo_calls)
        assert any("Web configuration portal is running" in call for call in echo_calls)
        assert any("Complete the configuration in your browser" in call for call in echo_calls)
        assert any("Configuration received from web portal" in call for call in echo_calls)