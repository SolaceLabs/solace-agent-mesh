"""
Unit tests for webui_gateway_step.py
Target: Increase coverage from 76% to 80%+
"""
from cli.commands.init_cmd.webui_gateway_step import (
    create_webui_gateway_config,
    WEBUI_GATEWAY_DEFAULTS,
)


class TestCreateWebuiGatewayConfig:
    """Test create_webui_gateway_config function"""

    def test_skip_gateway_creation(self, temp_project_dir, mocker):
        """Test skipping WebUI gateway creation"""
        mock_echo = mocker.patch("click.echo")
        
        options = {"add_webui_gateway": False}
        default_values = {}
        
        result = create_webui_gateway_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )
        
        assert result is True
        assert not (temp_project_dir / "configs" / "gateways" / "webui.yaml").exists()
        
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Skipping Web UI Gateway" in call for call in echo_calls)

    def test_successful_gateway_creation(self, temp_project_dir, mocker, mock_templates):
        """Test successful WebUI gateway configuration creation"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.webui_gateway_step.ask_if_not_provided")
        
        # ask_if_not_provided updates options dict and returns value
        def ask_side_effect(opts, key, *args, **kwargs):
            if key in opts:
                return opts[key]
            opts[key] = "test_value"
            return "test_value"
        
        mock_ask.side_effect = ask_side_effect
        
        options = {
            "add_webui_gateway": True,
            "webui_session_secret_key": "secret123",
            "webui_fastapi_host": "0.0.0.0",
            "webui_fastapi_port": 8000,
            "webui_fastapi_https_port": 8443,
            "webui_enable_embed_resolution": True,
            "webui_ssl_keyfile": "",
            "webui_ssl_certfile": "",
            "webui_ssl_keyfile_password": "",
            "webui_frontend_welcome_message": "Welcome!",
            "webui_frontend_bot_name": "TestBot",
            "webui_frontend_collect_feedback": True,
        }
        default_values = {}
        
        result = create_webui_gateway_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )
        
        assert result is True
        assert (temp_project_dir / "configs" / "gateways" / "webui.yaml").exists()
        
        config_content = (temp_project_dir / "configs" / "gateways" / "webui.yaml").read_text()
        # The template uses ${FRONTEND_WELCOME_MESSAGE} not the actual value
        # Check that the file was created and contains expected structure
        assert "frontend_welcome_message" in config_content
        assert "frontend_bot_name" in config_content

    def test_gateway_with_defaults(self, temp_project_dir, mocker, mock_templates):
        """Test gateway creation with default values"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.webui_gateway_step.ask_if_not_provided")
        
        def ask_side_effect(opts, key, prompt, default=None, **kwargs):
            opts[key] = default
            return default
        
        mock_ask.side_effect = ask_side_effect
        
        options = {"add_webui_gateway": True}
        default_values = WEBUI_GATEWAY_DEFAULTS.copy()
        
        result = create_webui_gateway_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )
        
        assert result is True

    def test_gateway_template_not_found(self, temp_project_dir, mocker):
        """Test handling of missing template file"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.webui_gateway_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        mock_load = mocker.patch(
            "cli.commands.init_cmd.webui_gateway_step.load_template",
            side_effect=FileNotFoundError("Template not found")
        )
        
        options = {"add_webui_gateway": True}
        default_values = {}
        
        result = create_webui_gateway_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )
        
        assert result is False
        
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Template file not found" in call for call in echo_calls)

    def test_gateway_file_write_error(self, temp_project_dir, mocker, mock_templates):
        """Test handling of file write error"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.webui_gateway_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        # Mock open to fail
        original_open = open
        def mock_open(file, *args, **kwargs):
            if "webui.yaml" in str(file):
                raise IOError("Write error")
            return original_open(file, *args, **kwargs)
        
        mocker.patch("builtins.open", mock_open)
        
        options = {"add_webui_gateway": True}
        default_values = {}
        
        result = create_webui_gateway_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )
        
        assert result is False

    def test_gateway_unexpected_exception(self, temp_project_dir, mocker):
        """Test handling of unexpected exception"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.webui_gateway_step.ask_if_not_provided")
        
        # Mock load_template to raise exception
        mock_load = mocker.patch(
            "cli.commands.init_cmd.webui_gateway_step.load_template",
            side_effect=Exception("Unexpected error")
        )
        
        # ask_if_not_provided should work normally
        def ask_side_effect(opts, key, *args, **kwargs):
            opts[key] = "test"
            return "test"
        
        mock_ask.side_effect = ask_side_effect
        
        options = {"add_webui_gateway": True}
        default_values = {}
        
        result = create_webui_gateway_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )
        
        assert result is False
        
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("unexpected error" in call.lower() for call in echo_calls)

    def test_gateway_interactive_mode(self, temp_project_dir, mocker, mock_templates):
        """Test gateway creation in interactive mode"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.webui_gateway_step.ask_if_not_provided")
        mock_ask.return_value = "interactive_value"
        
        options = {"add_webui_gateway": True}
        default_values = {}
        
        result = create_webui_gateway_config(
            temp_project_dir, options, skip_interactive=False, default_values=default_values
        )
        
        assert result is True
        # Verify ask_if_not_provided was called for various parameters
        assert mock_ask.call_count > 0

    def test_gateway_none_add_webui_gateway_uses_default(self, temp_project_dir, mocker, mock_templates):
        """Test that None add_webui_gateway uses default value"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.webui_gateway_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        options = {"add_webui_gateway": None}
        default_values = {"add_webui_gateway": True}
        
        result = create_webui_gateway_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )
        
        assert result is True
        assert options["add_webui_gateway"] is True

    def test_gateway_directory_creation(self, temp_project_dir, mocker, mock_templates):
        """Test that gateway directory is created if it doesn't exist"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.webui_gateway_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        options = {"add_webui_gateway": True}
        default_values = {}
        
        # Ensure directory doesn't exist
        gateway_dir = temp_project_dir / "configs" / "gateways"
        assert not gateway_dir.exists()
        
        result = create_webui_gateway_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )
        
        assert result is True
        assert gateway_dir.exists()

    def test_gateway_messages_displayed(self, temp_project_dir, mocker, mock_templates):
        """Test that appropriate messages are displayed"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.webui_gateway_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        options = {"add_webui_gateway": True}
        default_values = {}
        
        create_webui_gateway_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )
        
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Configuring Web UI Gateway" in call for call in echo_calls)
        assert any("Creating Web UI Gateway configuration" in call for call in echo_calls)
        assert any("Created" in call for call in echo_calls)