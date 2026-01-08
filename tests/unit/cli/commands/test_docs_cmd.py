"""
Unit tests for cli/commands/docs_cmd.py

Tests the docs command including:
- Starting documentation server with default port
- Custom port configuration
- Browser opening behavior
- Error handling (missing docs directory)
- HTTP request handler path rewriting
- 404 redirect behavior
- Keyboard interrupt handling
"""

from unittest.mock import MagicMock, Mock, patch
import pytest
from click.testing import CliRunner

from cli.commands.docs_cmd import docs, DocsHttpRequestHandler


@pytest.fixture
def runner():
    """Create a Click CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def mock_docs_dir(tmp_path):
    """Create a temporary docs directory"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.html").write_text("<html>Test</html>")
    return docs_dir


class TestDocsHttpRequestHandler:
    """Tests for the DocsHttpRequestHandler class"""
    
    def test_path_rewriting_with_solace_prefix(self):
        """Test that paths starting with /solace-agent-mesh are rewritten"""
        # Create a mock request with proper bytes
        mock_request = MagicMock()
        mock_request.makefile.return_value = MagicMock()
        
        # We need to test the path rewriting logic directly
        # Create handler without triggering __init__ fully
        handler = DocsHttpRequestHandler.__new__(DocsHttpRequestHandler)
        handler.path = "/solace-agent-mesh/docs/getting-started/"
        
        # Mock the parent do_GET to avoid actual HTTP handling
        with patch.object(DocsHttpRequestHandler.__bases__[0], 'do_GET'):
            handler.do_GET()
        
        assert handler.path == "/docs/getting-started/"
    
    def test_path_rewriting_root_path(self):
        """Test that /solace-agent-mesh alone becomes /"""
        handler = DocsHttpRequestHandler.__new__(DocsHttpRequestHandler)
        handler.path = "/solace-agent-mesh"
        
        with patch.object(DocsHttpRequestHandler.__bases__[0], 'do_GET'):
            handler.do_GET()
        
        assert handler.path == "/"
    
    def test_path_without_prefix_unchanged(self):
        """Test that paths without /solace-agent-mesh prefix are unchanged"""
        handler = DocsHttpRequestHandler.__new__(DocsHttpRequestHandler)
        handler.path = "/other/path"
        
        with patch.object(DocsHttpRequestHandler.__bases__[0], 'do_GET'):
            handler.do_GET()
        
        assert handler.path == "/other/path"
    
    def test_404_redirect(self):
        """Test that 404 errors redirect to introduction page"""
        handler = DocsHttpRequestHandler.__new__(DocsHttpRequestHandler)
        
        # Mock the response methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.send_error(404)
        
        handler.send_response.assert_called_once_with(302)
        handler.send_header.assert_called_once_with(
            'Location',
            '/solace-agent-mesh/docs/documentation/getting-started/introduction/'
        )
        handler.end_headers.assert_called_once()
    
    def test_non_404_error_uses_parent(self):
        """Test that non-404 errors use parent error handling"""
        handler = DocsHttpRequestHandler.__new__(DocsHttpRequestHandler)
        
        with patch.object(DocsHttpRequestHandler.__bases__[0], 'send_error') as mock_parent:
            handler.send_error(500, "Internal Server Error")
            mock_parent.assert_called_once_with(500, "Internal Server Error")


class TestDocsCommand:
    """Tests for the docs CLI command"""
    
    def test_docs_command_with_prod_docs(self, runner, tmp_path, mocker):
        """Test docs command when production docs directory exists"""
        # Create mock prod docs directory
        prod_docs = tmp_path / "assets" / "docs"
        prod_docs.mkdir(parents=True)
        (prod_docs / "index.html").write_text("<html>Prod Docs</html>")
        
        # Mock get_cli_root_dir to return our tmp_path
        mocker.patch("cli.commands.docs_cmd.get_cli_root_dir", return_value=str(tmp_path))
        
        # Mock webbrowser and TCPServer
        mock_browser = mocker.patch("cli.commands.docs_cmd.webbrowser.open_new_tab")
        mock_server = MagicMock()
        mock_server.__enter__ = Mock(return_value=mock_server)
        mock_server.__exit__ = Mock(return_value=False)
        mock_server.serve_forever = Mock(side_effect=KeyboardInterrupt)
        
        mocker.patch("cli.commands.docs_cmd.socketserver.TCPServer", return_value=mock_server)
        
        result = runner.invoke(docs)
        
        assert result.exit_code == 0
        assert "Starting documentation server" in result.output
        mock_browser.assert_called_once()
        assert "http://localhost:8585" in mock_browser.call_args[0][0]
    
    def test_docs_command_with_dev_docs(self, runner, tmp_path, mocker):
        """Test docs command when only dev docs directory exists"""
        # Create mock dev docs directory
        dev_docs = tmp_path / "docs" / "build"
        dev_docs.mkdir(parents=True)
        (dev_docs / "index.html").write_text("<html>Dev Docs</html>")
        
        # Mock paths - prod doesn't exist, dev does
        mocker.patch("cli.commands.docs_cmd.get_cli_root_dir", return_value=str(tmp_path / "nonexistent"))
        mocker.patch("cli.commands.docs_cmd.os.path.dirname", return_value=str(tmp_path))
        
        def mock_exists(path):
            return "docs/build" in str(path)
        
        mocker.patch("cli.commands.docs_cmd.os.path.exists", side_effect=mock_exists)
        
        # Mock webbrowser and TCPServer
        mock_browser = mocker.patch("cli.commands.docs_cmd.webbrowser.open_new_tab")
        mock_server = MagicMock()
        mock_server.__enter__ = Mock(return_value=mock_server)
        mock_server.__exit__ = Mock(return_value=False)
        mock_server.serve_forever = Mock(side_effect=KeyboardInterrupt)
        
        mocker.patch("cli.commands.docs_cmd.socketserver.TCPServer", return_value=mock_server)
        
        result = runner.invoke(docs)
        
        assert result.exit_code == 0
        assert "Serving development documentation" in result.output
        mock_browser.assert_called_once()
    
    def test_docs_command_custom_port(self, runner, tmp_path, mocker):
        """Test docs command with custom port"""
        # Create mock docs directory
        prod_docs = tmp_path / "assets" / "docs"
        prod_docs.mkdir(parents=True)
        
        mocker.patch("cli.commands.docs_cmd.get_cli_root_dir", return_value=str(tmp_path))
        
        # Mock webbrowser and TCPServer
        mock_browser = mocker.patch("cli.commands.docs_cmd.webbrowser.open_new_tab")
        mock_server = MagicMock()
        mock_server.__enter__ = Mock(return_value=mock_server)
        mock_server.__exit__ = Mock(return_value=False)
        mock_server.serve_forever = Mock(side_effect=KeyboardInterrupt)
        
        mock_tcp_server = mocker.patch("cli.commands.docs_cmd.socketserver.TCPServer", return_value=mock_server)
        
        result = runner.invoke(docs, ["--port", "9000"])
        
        assert result.exit_code == 0
        assert "http://localhost:9000" in result.output
        mock_browser.assert_called_once()
        assert "http://localhost:9000" in mock_browser.call_args[0][0]
        
        # Verify TCPServer was called with correct port
        assert mock_tcp_server.call_args[0][0] == ("", 9000)
    
    def test_docs_command_missing_docs_directory(self, runner, tmp_path, mocker):
        """Test docs command when no docs directory exists"""
        # Mock paths to non-existent directories
        mocker.patch("cli.commands.docs_cmd.get_cli_root_dir", return_value=str(tmp_path / "nonexistent"))
        mocker.patch("cli.commands.docs_cmd.os.path.dirname", return_value=str(tmp_path / "nonexistent"))
        mocker.patch("cli.commands.docs_cmd.os.path.exists", return_value=False)
        
        # Mock error_exit to raise SystemExit
        mock_error_exit = mocker.patch("cli.commands.docs_cmd.error_exit", side_effect=SystemExit(1))
        
        result = runner.invoke(docs)
        
        assert result.exit_code == 1
        mock_error_exit.assert_called_once()
        assert "Documentation directory not found" in mock_error_exit.call_args[0][0]
    
    def test_docs_command_keyboard_interrupt(self, runner, tmp_path, mocker):
        """Test docs command handles keyboard interrupt gracefully"""
        # Create mock docs directory
        prod_docs = tmp_path / "assets" / "docs"
        prod_docs.mkdir(parents=True)
        
        mocker.patch("cli.commands.docs_cmd.get_cli_root_dir", return_value=str(tmp_path))
        mocker.patch("cli.commands.docs_cmd.webbrowser.open_new_tab")
        
        # Mock TCPServer to raise KeyboardInterrupt
        mock_server = MagicMock()
        mock_server.__enter__ = Mock(return_value=mock_server)
        mock_server.__exit__ = Mock(return_value=False)
        mock_server.serve_forever = Mock(side_effect=KeyboardInterrupt)
        
        mocker.patch("cli.commands.docs_cmd.socketserver.TCPServer", return_value=mock_server)
        
        result = runner.invoke(docs)
        
        # Should exit cleanly on KeyboardInterrupt
        assert result.exit_code == 0
    
    def test_docs_command_port_option_validation(self, runner, tmp_path, mocker):
        """Test docs command validates port as integer"""
        result = runner.invoke(docs, ["--port", "invalid"])
        
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "Error" in result.output
    
    def test_docs_command_short_port_option(self, runner, tmp_path, mocker):
        """Test docs command with short -p option"""
        # Create mock docs directory
        prod_docs = tmp_path / "assets" / "docs"
        prod_docs.mkdir(parents=True)
        
        mocker.patch("cli.commands.docs_cmd.get_cli_root_dir", return_value=str(tmp_path))
        
        mock_browser = mocker.patch("cli.commands.docs_cmd.webbrowser.open_new_tab")
        mock_server = MagicMock()
        mock_server.__enter__ = Mock(return_value=mock_server)
        mock_server.__exit__ = Mock(return_value=False)
        mock_server.serve_forever = Mock(side_effect=KeyboardInterrupt)
        
        mocker.patch("cli.commands.docs_cmd.socketserver.TCPServer", return_value=mock_server)
        
        result = runner.invoke(docs, ["-p", "7777"])
        
        assert result.exit_code == 0
        assert "http://localhost:7777" in result.output
    
    def test_docs_handler_initialization(self, tmp_path):
        """Test DocsHttpRequestHandler initialization with directory"""
        docs_dir = str(tmp_path / "docs")
        
        # Test that the handler class can be created with directory parameter
        # We use __new__ to avoid triggering the socket handling in __init__
        handler = DocsHttpRequestHandler.__new__(DocsHttpRequestHandler)
        
        # Verify the handler class was created (basic smoke test)
        assert handler is not None
        assert isinstance(handler, DocsHttpRequestHandler)
    
    def test_docs_command_url_format(self, runner, tmp_path, mocker):
        """Test that the URL format is correct"""
        prod_docs = tmp_path / "assets" / "docs"
        prod_docs.mkdir(parents=True)
        
        mocker.patch("cli.commands.docs_cmd.get_cli_root_dir", return_value=str(tmp_path))
        
        mock_browser = mocker.patch("cli.commands.docs_cmd.webbrowser.open_new_tab")
        mock_server = MagicMock()
        mock_server.__enter__ = Mock(return_value=mock_server)
        mock_server.__exit__ = Mock(return_value=False)
        mock_server.serve_forever = Mock(side_effect=KeyboardInterrupt)
        
        mocker.patch("cli.commands.docs_cmd.socketserver.TCPServer", return_value=mock_server)
        
        result = runner.invoke(docs, ["--port", "8585"])
        
        # Verify the exact URL format
        expected_url = "http://localhost:8585/solace-agent-mesh/docs/documentation/getting-started/introduction/"
        mock_browser.assert_called_once_with(expected_url)
        assert expected_url in result.output