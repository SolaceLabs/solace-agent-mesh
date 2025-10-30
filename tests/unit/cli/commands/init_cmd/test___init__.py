"""
Unit tests for init_cmd/__init__.py
Target: Increase coverage from 92% to 80%+ (already above target, adding comprehensive tests)
"""
from click.testing import CliRunner

from cli.commands.init_cmd import init, run_init_flow, DEFAULT_INIT_VALUES


class TestRunInitFlow:
    """Test run_init_flow function"""

    def test_successful_init_flow_skip_interactive(self, temp_project_dir, mocker):
        """Test successful initialization flow in skip interactive mode"""
        mock_echo = mocker.patch("click.echo")
        mock_broker = mocker.patch("cli.commands.init_cmd.broker_setup_step", return_value={})
        mock_dirs = mocker.patch("cli.commands.init_cmd.create_project_directories", return_value=True)
        mock_files = mocker.patch("cli.commands.init_cmd.create_project_files", return_value=True)
        mock_orch = mocker.patch("cli.commands.init_cmd.create_orchestrator_config", return_value=True)
        mock_webui = mocker.patch("cli.commands.init_cmd.create_webui_gateway_config", return_value=True)
        mock_env = mocker.patch("cli.commands.init_cmd.create_env_file", return_value=True)
        
        mocker.patch("pathlib.Path.cwd", return_value=temp_project_dir)
        
        run_init_flow(skip_interactive=True, use_web_based_init_flag=False)
        
        # Verify all steps were called
        mock_broker.assert_called_once()
        mock_dirs.assert_called_once()
        mock_files.assert_called_once()
        mock_orch.assert_called_once()
        mock_webui.assert_called_once()
        mock_env.assert_called_once()

    def test_init_flow_with_web_init(self, temp_project_dir, mocker):
        """Test initialization flow with web-based init"""
        mock_echo = mocker.patch("click.echo")
        mock_web_init = mocker.patch(
            "cli.commands.init_cmd.perform_web_init",
            return_value={"llm_service_endpoint": "https://api.test.com"}
        )
        mock_broker = mocker.patch("cli.commands.init_cmd.broker_setup_step", return_value={})
        mock_dirs = mocker.patch("cli.commands.init_cmd.create_project_directories", return_value=True)
        mock_files = mocker.patch("cli.commands.init_cmd.create_project_files", return_value=True)
        mock_orch = mocker.patch("cli.commands.init_cmd.create_orchestrator_config", return_value=True)
        mock_webui = mocker.patch("cli.commands.init_cmd.create_webui_gateway_config", return_value=True)
        mock_env = mocker.patch("cli.commands.init_cmd.create_env_file", return_value=True)
        
        mocker.patch("pathlib.Path.cwd", return_value=temp_project_dir)
        
        run_init_flow(skip_interactive=False, use_web_based_init_flag=True)
        
        # Verify web init was called
        mock_web_init.assert_called_once()

    def test_init_flow_interactive_web_prompt(self, temp_project_dir, mocker):
        """Test that interactive mode prompts for web init"""
        mock_echo = mocker.patch("click.echo")
        mock_ask_yes_no = mocker.patch("cli.commands.init_cmd.ask_yes_no_question", return_value=False)
        mock_broker = mocker.patch("cli.commands.init_cmd.broker_setup_step", return_value={})
        mock_dirs = mocker.patch("cli.commands.init_cmd.create_project_directories", return_value=True)
        mock_files = mocker.patch("cli.commands.init_cmd.create_project_files", return_value=True)
        mock_orch = mocker.patch("cli.commands.init_cmd.create_orchestrator_config", return_value=True)
        mock_webui = mocker.patch("cli.commands.init_cmd.create_webui_gateway_config", return_value=True)
        mock_env = mocker.patch("cli.commands.init_cmd.create_env_file", return_value=True)
        
        mocker.patch("pathlib.Path.cwd", return_value=temp_project_dir)
        
        run_init_flow(skip_interactive=False, use_web_based_init_flag=False)
        
        # Verify user was asked about web init
        mock_ask_yes_no.assert_called_once()

    def test_init_flow_web_init_with_skip_shows_warning(self, temp_project_dir, mocker):
        """Test that web init with skip interactive shows warning"""
        mock_echo = mocker.patch("click.echo")
        mock_broker = mocker.patch("cli.commands.init_cmd.broker_setup_step", return_value={})
        mock_dirs = mocker.patch("cli.commands.init_cmd.create_project_directories", return_value=True)
        mock_files = mocker.patch("cli.commands.init_cmd.create_project_files", return_value=True)
        mock_orch = mocker.patch("cli.commands.init_cmd.create_orchestrator_config", return_value=True)
        mock_webui = mocker.patch("cli.commands.init_cmd.create_webui_gateway_config", return_value=True)
        mock_env = mocker.patch("cli.commands.init_cmd.create_env_file", return_value=True)
        
        mocker.patch("pathlib.Path.cwd", return_value=temp_project_dir)
        
        run_init_flow(skip_interactive=True, use_web_based_init_flag=True)
        
        # Verify warning was shown
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("not compatible with --skip" in call for call in echo_calls)


class TestInitCommand:
    """Test init CLI command"""

    def test_init_command_basic(self, mocker):
        """Test basic init command execution"""
        mock_run_flow = mocker.patch("cli.commands.init_cmd.run_init_flow")
        
        runner = CliRunner()
        result = runner.invoke(init, ["--skip"])
        
        assert result.exit_code == 0
        mock_run_flow.assert_called_once()

    def test_init_command_with_gui_flag(self, mocker):
        """Test init command with --gui flag"""
        mock_run_flow = mocker.patch("cli.commands.init_cmd.run_init_flow")
        
        runner = CliRunner()
        result = runner.invoke(init, ["--gui"])
        
        assert result.exit_code == 0
        # Verify gui flag was passed
        call_kwargs = mock_run_flow.call_args[1]
        assert call_kwargs["use_web_based_init_flag"] is True

    def test_init_command_with_dev_mode_flag(self, mocker):
        """Test init command with --dev-mode flag"""
        mock_run_flow = mocker.patch("cli.commands.init_cmd.run_init_flow")
        
        runner = CliRunner()
        result = runner.invoke(init, ["--dev-mode", "--skip"])
        
        assert result.exit_code == 0
        # Verify broker_type was set to dev
        call_kwargs = mock_run_flow.call_args[1]
        assert call_kwargs.get("broker_type") == "dev"

    def test_init_command_dev_mode_overrides_broker_type(self, mocker):
        """Test that --dev-mode overrides conflicting --broker-type"""
        mock_run_flow = mocker.patch("cli.commands.init_cmd.run_init_flow")
        
        runner = CliRunner()
        result = runner.invoke(init, ["--dev-mode", "--broker-type", "1", "--skip"])
        
        assert result.exit_code == 0
        # Verify broker_type was overridden to dev
        call_kwargs = mock_run_flow.call_args[1]
        assert call_kwargs.get("broker_type") == "dev"

    def test_init_command_with_llm_options(self, mocker):
        """Test init command with LLM configuration options"""
        mock_run_flow = mocker.patch("cli.commands.init_cmd.run_init_flow")
        
        runner = CliRunner()
        result = runner.invoke(init, [
            "--skip",
            "--llm-service-endpoint", "https://api.test.com",
            "--llm-service-api-key", "test-key",
            "--llm-service-planning-model-name", "gpt-4",
            "--llm-service-general-model-name", "gpt-3.5",
        ])
        
        assert result.exit_code == 0
        call_kwargs = mock_run_flow.call_args[1]
        assert call_kwargs.get("llm_service_endpoint") == "https://api.test.com"

    def test_init_command_with_broker_options(self, mocker):
        """Test init command with broker configuration options"""
        mock_run_flow = mocker.patch("cli.commands.init_cmd.run_init_flow")
        
        runner = CliRunner()
        result = runner.invoke(init, [
            "--skip",
            "--broker-type", "1",
            "--broker-url", "ws://broker:8008",
            "--broker-vpn", "my_vpn",
            "--broker-username", "user",
            "--broker-password", "pass",
        ])
        
        assert result.exit_code == 0
        call_kwargs = mock_run_flow.call_args[1]
        assert call_kwargs.get("broker_url") == "ws://broker:8008"

    def test_init_command_with_agent_options(self, mocker):
        """Test init command with agent configuration options"""
        mock_run_flow = mocker.patch("cli.commands.init_cmd.run_init_flow")
        
        runner = CliRunner()
        result = runner.invoke(init, [
            "--skip",
            "--agent-name", "MyAgent",
            "--supports-streaming",
            "--agent-card-description", "My test agent",
        ])
        
        assert result.exit_code == 0
        call_kwargs = mock_run_flow.call_args[1]
        assert call_kwargs.get("agent_name") == "MyAgent"
        assert call_kwargs.get("supports_streaming") is True

    def test_init_command_with_webui_options(self, mocker):
        """Test init command with WebUI gateway options"""
        mock_run_flow = mocker.patch("cli.commands.init_cmd.run_init_flow")
        
        runner = CliRunner()
        result = runner.invoke(init, [
            "--skip",
            "--add-webui-gateway",
            "--webui-fastapi-host", "0.0.0.0",
            "--webui-fastapi-port", "9000",
        ])
        
        assert result.exit_code == 0
        call_kwargs = mock_run_flow.call_args[1]
        assert call_kwargs.get("add_webui_gateway") is True
        assert call_kwargs.get("webui_fastapi_port") == 9000

    def test_default_init_values_structure(self):
        """Test that DEFAULT_INIT_VALUES has expected structure"""
        assert "broker_type" in DEFAULT_INIT_VALUES
        assert "llm_endpoint_url" in DEFAULT_INIT_VALUES
        assert "namespace" in DEFAULT_INIT_VALUES
        assert "agent_name" in DEFAULT_INIT_VALUES
        assert "add_webui_gateway" in DEFAULT_INIT_VALUES

    def test_init_flow_step_count_display(self, temp_project_dir, mocker):
        """Test that step count is displayed correctly"""
        mock_echo = mocker.patch("click.echo")
        mock_broker = mocker.patch("cli.commands.init_cmd.broker_setup_step", return_value={})
        mock_dirs = mocker.patch("cli.commands.init_cmd.create_project_directories", return_value=True)
        mock_files = mocker.patch("cli.commands.init_cmd.create_project_files", return_value=True)
        mock_orch = mocker.patch("cli.commands.init_cmd.create_orchestrator_config", return_value=True)
        mock_webui = mocker.patch("cli.commands.init_cmd.create_webui_gateway_config", return_value=True)
        mock_env = mocker.patch("cli.commands.init_cmd.create_env_file", return_value=True)
        
        mocker.patch("pathlib.Path.cwd", return_value=temp_project_dir)
        
        run_init_flow(skip_interactive=True, use_web_based_init_flag=False)
        
        # Verify step messages were displayed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Step 1 of" in call for call in echo_calls)
        assert any("Project initialization complete" in call for call in echo_calls)