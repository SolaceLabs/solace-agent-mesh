"""
Unit tests for platform_service_step.py
"""
from cli.commands.init_cmd.platform_service_step import (
    create_platform_service_config,
    PLATFORM_SERVICE_DEFAULTS,
)


class TestCreatePlatformServiceConfig:
    """Test create_platform_service_config function"""

    def test_skip_platform_service_when_webui_disabled(self, temp_project_dir, mocker):
        """Test skipping Platform Service creation when WebUI Gateway is disabled"""
        mock_echo = mocker.patch("click.echo")

        options = {"add_webui_gateway": False}
        default_values = {}

        result = create_platform_service_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )

        assert result is True
        assert not (temp_project_dir / "configs" / "services" / "platform.yaml").exists()

        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Skipping Platform Service" in call for call in echo_calls)

    def test_successful_platform_service_creation(self, temp_project_dir, mocker, mock_templates):
        """Test successful Platform Service configuration creation"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.platform_service_step.ask_if_not_provided")

        # ask_if_not_provided updates options dict and returns value
        def ask_side_effect(opts, key, *args, **kwargs):
            if key in opts:
                return opts[key]
            opts[key] = "test_value"
            return "test_value"

        mock_ask.side_effect = ask_side_effect

        options = {
            "add_webui_gateway": True,
            "platform_api_host": "127.0.0.1",
            "platform_api_port": 8001,
        }
        default_values = {}

        result = create_platform_service_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )

        assert result is True
        assert (temp_project_dir / "configs" / "services" / "platform.yaml").exists()

        config_content = (temp_project_dir / "configs" / "services" / "platform.yaml").read_text()
        # The template uses environment variables
        assert "namespace" in config_content
        assert "database_url" in config_content

    def test_platform_service_with_defaults(self, temp_project_dir, mocker, mock_templates):
        """Test platform service creation with default values"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.platform_service_step.ask_if_not_provided")

        def ask_side_effect(opts, key, prompt, default=None, **kwargs):
            opts[key] = default
            return default

        mock_ask.side_effect = ask_side_effect

        options = {"add_webui_gateway": True}
        default_values = PLATFORM_SERVICE_DEFAULTS.copy()

        result = create_platform_service_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )

        assert result is True

    def test_platform_service_template_not_found(self, temp_project_dir, mocker):
        """Test handling of missing template file"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.platform_service_step.ask_if_not_provided")
        mock_ask.return_value = "test"

        mock_load = mocker.patch(
            "cli.commands.init_cmd.platform_service_step.load_template",
            side_effect=FileNotFoundError("Template not found")
        )

        options = {"add_webui_gateway": True}
        default_values = {}

        result = create_platform_service_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )

        assert result is False

        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Template file not found" in call for call in echo_calls)

    def test_platform_service_file_write_error(self, temp_project_dir, mocker, mock_templates):
        """Test handling of file write error"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.platform_service_step.ask_if_not_provided")
        mock_ask.return_value = "test"

        # Mock open to fail
        original_open = open
        def mock_open(file, *args, **kwargs):
            if "platform.yaml" in str(file):
                raise IOError("Write error")
            return original_open(file, *args, **kwargs)

        mocker.patch("builtins.open", mock_open)

        options = {"add_webui_gateway": True}
        default_values = {}

        result = create_platform_service_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )

        assert result is False

    def test_platform_service_unexpected_exception(self, temp_project_dir, mocker):
        """Test handling of unexpected exception"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.platform_service_step.ask_if_not_provided")

        # Mock load_template to raise exception
        mock_load = mocker.patch(
            "cli.commands.init_cmd.platform_service_step.load_template",
            side_effect=Exception("Unexpected error")
        )

        # ask_if_not_provided should work normally
        def ask_side_effect(opts, key, *args, **kwargs):
            opts[key] = "test"
            return "test"

        mock_ask.side_effect = ask_side_effect

        options = {"add_webui_gateway": True}
        default_values = {}

        result = create_platform_service_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )

        assert result is False

        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("unexpected error" in call.lower() for call in echo_calls)

    def test_platform_service_interactive_mode(self, temp_project_dir, mocker, mock_templates):
        """Test platform service creation in interactive mode"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.platform_service_step.ask_if_not_provided")
        mock_ask.return_value = "interactive_value"

        options = {"add_webui_gateway": True}
        default_values = {}

        result = create_platform_service_config(
            temp_project_dir, options, skip_interactive=False, default_values=default_values
        )

        assert result is True
        # Verify ask_if_not_provided was called for various parameters
        assert mock_ask.call_count > 0

    def test_platform_service_created_with_webui_enabled(self, temp_project_dir, mocker, mock_templates):
        """Test that platform service is created when WebUI Gateway is enabled"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.platform_service_step.ask_if_not_provided")
        mock_ask.return_value = "test"

        options = {"add_webui_gateway": True}
        default_values = {}

        result = create_platform_service_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )

        assert result is True
        assert (temp_project_dir / "configs" / "services" / "platform.yaml").exists()

    def test_platform_service_directory_creation(self, temp_project_dir, mocker, mock_templates):
        """Test that platform service directory is created if it doesn't exist"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.platform_service_step.ask_if_not_provided")
        mock_ask.return_value = "test"

        options = {"add_webui_gateway": True}
        default_values = {}

        # Ensure directory doesn't exist
        services_dir = temp_project_dir / "configs" / "services"
        assert not services_dir.exists()

        result = create_platform_service_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )

        assert result is True
        assert services_dir.exists()

    def test_platform_service_messages_displayed(self, temp_project_dir, mocker, mock_templates):
        """Test that appropriate messages are displayed"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.platform_service_step.ask_if_not_provided")
        mock_ask.return_value = "test"

        options = {"add_webui_gateway": True}
        default_values = {}

        create_platform_service_config(
            temp_project_dir, options, skip_interactive=True, default_values=default_values
        )

        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Configuring Platform Service" in call for call in echo_calls)
        assert any("Creating Platform Service configuration" in call for call in echo_calls)
        assert any("Created" in call for call in echo_calls)

    def test_platform_service_defaults_values(self):
        """Test that PLATFORM_SERVICE_DEFAULTS contains expected values"""
        assert "platform_api_host" in PLATFORM_SERVICE_DEFAULTS
        assert "platform_api_port" in PLATFORM_SERVICE_DEFAULTS

        # Verify default values
        assert PLATFORM_SERVICE_DEFAULTS["platform_api_host"] == "127.0.0.1"
        assert PLATFORM_SERVICE_DEFAULTS["platform_api_port"] == 8001
