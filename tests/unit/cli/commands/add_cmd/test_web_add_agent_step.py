"""
Unit tests for cli/commands/add_cmd/web_add_agent_step.py

Tests the web-based agent addition functionality including:
- Portal launching and process management
- Browser opening and server waiting
- Data handling from web portal
- Error handling and timeout scenarios
- Process cleanup and exit handling
"""

import multiprocessing
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
from click.testing import CliRunner

from cli.commands.add_cmd.web_add_agent_step import launch_add_agent_web_portal


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


class TestLaunchAddAgentWebPortal:
    """Tests for launch_add_agent_web_portal function"""

    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_agent_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_agent_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_agent_step.click.echo')
    def test_successful_agent_creation(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test successful agent creation through web portal"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'agent_name_input': 'TestAgent',
            'config': {'model': 'gpt-4', 'instruction': 'Test instruction'}
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
        result = launch_add_agent_web_portal(cli_options)
        
        # Verify
        assert result == ('TestAgent', {'model': 'gpt-4', 'instruction': 'Test instruction'}, Path.cwd())
        mock_process_class.assert_called_once()
        process_mock.start.assert_called_once()
        process_mock.join.assert_called_once()
        mock_wait.assert_called_once_with("http://127.0.0.1:5002/?config_mode=addAgent")
        mock_browser.assert_called_once_with("http://127.0.0.1:5002/?config_mode=addAgent")

    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_agent_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_agent_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_agent_step.click.echo')
    @patch('cli.commands.add_cmd.web_add_agent_step.sys.exit')
    def test_server_timeout_error(self, mock_exit, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
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
        launch_add_agent_web_portal(cli_options)
        
        # Verify
        mock_exit.assert_called_once_with(1)
        mock_browser.assert_not_called()

    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_agent_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_agent_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_agent_step.click.echo')
    @patch('cli.commands.add_cmd.web_add_agent_step.sys.exit')
    def test_browser_open_exception(self, mock_exit, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
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
        launch_add_agent_web_portal(cli_options)
        
        # Verify
        mock_exit.assert_called_once_with(1)
        # Should still try to open browser despite error
        mock_browser.assert_called_once()

    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_agent_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_agent_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_agent_step.click.echo')
    @patch('cli.commands.add_cmd.web_add_agent_step.sys.exit')
    def test_incomplete_data_from_portal(self, mock_exit, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test handling of incomplete data from web portal"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'agent_name_input': 'TestAgent',
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
        launch_add_agent_web_portal(cli_options)
        
        # Verify
        mock_exit.assert_called_once_with(1)

    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_agent_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_agent_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_agent_step.click.echo')
    @patch('cli.commands.add_cmd.web_add_agent_step.sys.exit')
    def test_shutdown_aborted_status(self, mock_exit, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
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
        launch_add_agent_web_portal(cli_options)
        
        # Verify
        mock_exit.assert_called_once_with(1)

    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_agent_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_agent_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_agent_step.click.echo')
    @patch('cli.commands.add_cmd.web_add_agent_step.sys.exit')
    def test_no_data_from_portal(self, mock_exit, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
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
        launch_add_agent_web_portal(cli_options)
        
        # Verify
        mock_exit.assert_called_once_with(1)

    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_agent_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_agent_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_agent_step.click.echo')
    @patch('cli.commands.add_cmd.web_add_agent_step.sys.exit')
    def test_unknown_status_from_portal(self, mock_exit, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
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
        launch_add_agent_web_portal(cli_options)
        
        # Verify
        mock_exit.assert_called_once_with(1)

    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_agent_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_agent_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_agent_step.click.echo')
    def test_process_management(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test proper process management"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'agent_name_input': 'TestAgent',
            'config': {'model': 'gpt-4'}
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
        result = launch_add_agent_web_portal(cli_options)
        
        # Verify process lifecycle
        process_mock.start.assert_called_once()
        process_mock.join.assert_called_once()
        
        # Verify process was created with correct arguments
        mock_process_class.assert_called_once()
        call_args = mock_process_class.call_args
        assert call_args[1]['target'].__name__ == 'run_flask'
        assert call_args[1]['args'] == ("127.0.0.1", 5002, shared_data)

    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Manager')
    @patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Process')
    @patch('cli.commands.add_cmd.web_add_agent_step.wait_for_server')
    @patch('cli.commands.add_cmd.web_add_agent_step.webbrowser.open')
    @patch('cli.commands.add_cmd.web_add_agent_step.click.echo')
    def test_click_echo_messages(self, mock_echo, mock_browser, mock_wait, mock_process_class, mock_manager_class):
        """Test that appropriate messages are displayed to user"""
        # Setup mocks
        shared_data = {
            'status': 'success_from_gui_save',
            'agent_name_input': 'TestAgent',
            'config': {'model': 'gpt-4'}
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
        launch_add_agent_web_portal(cli_options)
        
        # Verify messages
        echo_calls = [call[0][0] for call in mock_echo.call_args_list]
        
        # Check for key messages
        assert any("Attempting to start web-based 'Add Agent' portal" in msg for msg in echo_calls)
        assert any("Add Agent portal is running" in msg for msg in echo_calls)
        assert any("Opening your browser" in msg for msg in echo_calls)
        assert any("Complete the agent configuration" in msg for msg in echo_calls)
        assert any("Configuration received from web portal" in msg for msg in echo_calls)

    def test_cli_options_parameter(self):
        """Test that cli_options parameter is properly handled"""
        # This test verifies the function signature accepts cli_options
        # The actual implementation doesn't use cli_options currently
        # but the parameter should be accepted for future extensibility
        
        with patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Manager') as mock_manager_class:
            with patch('cli.commands.add_cmd.web_add_agent_step.multiprocessing.Process'):
                with patch('cli.commands.add_cmd.web_add_agent_step.wait_for_server', return_value=False):
                    with patch('cli.commands.add_cmd.web_add_agent_step.sys.exit'):
                        
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
                            {'namespace': 'test/namespace', 'model': 'gpt-4'}
                        ]
                        
                        for options in test_options:
                            try:
                                launch_add_agent_web_portal(options)
                            except SystemExit:
                                pass  # Expected due to mocked sys.exit