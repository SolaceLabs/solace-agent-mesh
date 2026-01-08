"""
Unit tests for cli/commands/add_cmd/web_add_gateway_step.py

Tests the web-based gateway addition functionality including:
- Portal launching and process management
- Browser opening and server waiting
- Data handling from web portal
- Error handling and timeout scenarios
- Process cleanup and return value handling
"""

import multiprocessing
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from cli.commands.add_cmd.web_add_gateway_step import launch_add_gateway_web_portal


@pytest.fixture
def mock_manager():
    """Create a mock multiprocessing Manager"""
    manager = Mock()
    shared_dict = {}
    manager.dict.return_value = shared_dict
    return manager, shared_dict


@pytest.fixture
def mock_process():
    """Create a mock multiprocessing Process"""
    process = Mock()
    process.start = Mock()
    process.join = Mock()
    return process


class TestLaunchAddGatewayWebPortal:
    """Tests for launch_add_gateway_web_portal function"""

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_successful_gateway_creation(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test successful gateway creation through web portal"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'gateway_name_input': 'TestGateway',
            'config': {'type': 'http_sse', 'port': 8080}
        }
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Verify
        assert result == ('TestGateway', {'type': 'http_sse', 'port': 8080}, Path.cwd())
        mock_process_class.assert_called_once()
        process_mock.start.assert_called_once()
        process_mock.join.assert_called_once()
        mock_wait.assert_called_once_with("http://127.0.0.1:5002/?config_mode=addGateway")
        mock_browser.assert_called_once_with("http://127.0.0.1:5002/?config_mode=addGateway")

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_server_timeout_error(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test handling of server timeout"""
        # Setup mocks
        shared_data = {}
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = False  # Server timeout
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Verify
        assert result is None
        mock_browser.assert_not_called()

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_browser_open_exception(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test handling of browser opening exception"""
        # Setup mocks
        shared_data = {}
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        mock_browser.side_effect = Exception("Browser error")
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Verify
        assert result is None
        # Should still try to open browser despite error
        mock_browser.assert_called_once()

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_incomplete_data_from_portal(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test handling of incomplete data from web portal"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'gateway_name_input': 'TestGateway',
            # Missing 'config' key
        }
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Verify
        assert result is None

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_config_is_none(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test handling when config is explicitly None"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'gateway_name_input': 'TestGateway',
            'config': None
        }
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Verify - should return None since config is None (incomplete data)
        assert result is None

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_shutdown_aborted_status(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test handling of shutdown_aborted status"""
        # Setup mocks
        shared_data = {
            'status': 'shutdown_aborted',
            'message': 'User cancelled operation'
        }
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Verify
        assert result is None

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_no_data_from_portal(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test handling when no data is received from portal"""
        # Setup mocks
        shared_data = {}  # Empty data
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Verify
        assert result is None

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_unknown_status_from_portal(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test handling of unknown status from portal"""
        # Setup mocks
        shared_data = {
            'status': 'unknown_status',
            'message': 'Something went wrong'
        }
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Verify
        assert result is None

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_process_management(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test proper process management"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'gateway_name_input': 'TestGateway',
            'config': {'type': 'http_sse'}
        }
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Verify process lifecycle
        process_mock.start.assert_called_once()
        process_mock.join.assert_called_once()
        
        # Verify process was created with correct arguments
        mock_process_class.assert_called_once()
        call_args = mock_process_class.call_args
        assert call_args[1]['target'].__name__ == 'run_flask'
        assert call_args[1]['args'] == ("127.0.0.1", 5002, shared_data)

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_click_echo_messages(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test that appropriate messages are displayed to user"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'gateway_name_input': 'TestGateway',
            'config': {'type': 'http_sse'}
        }
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        
        cli_options = {}
        
        # Execute
        launch_add_gateway_web_portal(cli_options)
        
        # Verify messages
        echo_calls = [call[0][0] for call in mock_echo.call_args_list]
        
        # Check for key messages
        assert any("Attempting to start web-based 'Add Gateway' portal" in msg for msg in echo_calls)
        assert any("Add Gateway portal is attempting to start" in msg for msg in echo_calls)
        assert any("Opening your browser" in msg for msg in echo_calls)
        assert any("Complete the gateway configuration" in msg for msg in echo_calls)
        assert any("Configuration received from web portal" in msg for msg in echo_calls)

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_error_messages_to_stderr(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test that error messages are sent to stderr"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'gateway_name_input': None,  # Missing name
            'config': {'type': 'http_sse'}
        }
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Verify
        assert result is None
        
        # Check that error messages use err=True
        error_calls = [call for call in mock_echo.call_args_list if call[1].get('err') is True]
        assert len(error_calls) > 0

    def test_cli_options_parameter(self):
        """Test that cli_options parameter is properly handled"""
        # This test verifies the function signature accepts cli_options
        # The actual implementation doesn't use cli_options currently
        # but the parameter should be accepted for future extensibility
        
        with patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager') as mock_manager_class:
            with patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process'):
                with patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server', return_value=False):
                    
                    shared_data = {}
                    manager_mock = Mock()
                    manager_mock.dict.return_value = shared_data
                    manager_mock.__enter__ = Mock(return_value=manager_mock)
                    manager_mock.__exit__ = Mock(return_value=None)
                    mock_manager_class.return_value = manager_mock
                    
                    # Should accept various cli_options formats
                    test_options = [
                        {},
                        {'name': 'test'},
                        {'type': 'http_sse', 'port': 8080}
                    ]
                    
                    for options in test_options:
                        result = launch_add_gateway_web_portal(options)
                        assert result is None  # Expected due to server timeout

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_detailed_error_message_for_incomplete_data(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test detailed error message when data is incomplete"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'gateway_name_input': 'TestGateway',
            'config': None  # This should be fine, but missing name would be an issue
        }
        
        manager_mock = Mock()
        manager_mock.dict.return_value = shared_data
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        mock_wait.return_value = True
        
        cli_options = {}
        
        # Execute
        result = launch_add_gateway_web_portal(cli_options)
        
        # Should return None since config is None (incomplete data)
        assert result is None

    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_gateway_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_gateway_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_gateway_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_gateway_step.click.echo')
    def test_return_none_on_all_failure_paths(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test that function returns None on all failure paths"""
        # Setup mocks
        manager_mock = Mock()
        manager_mock.__enter__ = Mock(return_value=manager_mock)
        manager_mock.__exit__ = Mock(return_value=None)
        mock_manager_class.return_value = manager_mock
        
        process_mock = Mock()
        mock_process_class.return_value = process_mock
        
        cli_options = {}
        
        # Test various failure scenarios
        failure_scenarios = [
            # Server timeout
            {'shared_data': {}, 'server_wait': False},
            # No data from portal
            {'shared_data': {}, 'server_wait': True},
            # Shutdown aborted
            {'shared_data': {'status': 'shutdown_aborted'}, 'server_wait': True},
            # Unknown status
            {'shared_data': {'status': 'unknown'}, 'server_wait': True},
            # Missing gateway name
            {'shared_data': {'status': 'success_from_gui_save', 'config': {}}, 'server_wait': True},
        ]
        
        for scenario in failure_scenarios:
            manager_mock.dict.return_value = scenario['shared_data']
            mock_wait.return_value = scenario['server_wait']
            
            result = launch_add_gateway_web_portal(cli_options)
            assert result is None, f"Expected None for scenario: {scenario}"