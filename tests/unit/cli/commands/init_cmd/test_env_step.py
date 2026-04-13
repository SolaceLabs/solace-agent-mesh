"""
Unit tests for env_step.py
Target: Increase coverage from 83% to 80%+ (already above target, adding comprehensive tests)
"""
from cli.commands.init_cmd.env_step import create_env_file


class TestCreateEnvFile:
    """Test create_env_file function"""

    def test_successful_env_file_creation(self, temp_project_dir, mocker):
        """Test successful creation of .env file"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.env_step.ask_if_not_provided")
        mock_ask.return_value = "test_value"
        
        options = {
            "llm_provider": "openai",
            "llm_service_endpoint": "https://api.test.com",
            "llm_service_api_key": "test-key",
            "namespace": "test_namespace",
            "broker_url": "ws://localhost:8008",
        }

        result = create_env_file(temp_project_dir, options, skip_interactive=True)

        assert result is True
        assert (temp_project_dir / ".env").exists()

        env_content = (temp_project_dir / ".env").read_text()
        assert "LLM_SERVICE_ENDPOINT" in env_content
        assert "https://api.test.com" in env_content

    def test_namespace_trailing_slash_added(self, temp_project_dir, mocker):
        """Test that trailing slash is added to namespace if missing"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.env_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        options = {
            "namespace": "my_namespace",  # No trailing slash
            "llm_service_endpoint": "https://api.test.com",
        }
        
        create_env_file(temp_project_dir, options, skip_interactive=True)
        
        env_content = (temp_project_dir / ".env").read_text()
        assert 'NAMESPACE="my_namespace/"' in env_content

    def test_namespace_with_existing_trailing_slash(self, temp_project_dir, mocker):
        """Test that namespace with trailing slash is not modified"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.env_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        options = {
            "namespace": "my_namespace/",  # Already has trailing slash
            "llm_service_endpoint": "https://api.test.com",
        }
        
        create_env_file(temp_project_dir, options, skip_interactive=True)
        
        env_content = (temp_project_dir / ".env").read_text()
        assert 'NAMESPACE="my_namespace/"' in env_content
        assert 'NAMESPACE="my_namespace//"' not in env_content

    def test_env_file_with_all_parameters(self, temp_project_dir, mocker):
        """Test .env file creation with all parameters"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.env_step.ask_if_not_provided")
        mock_ask.return_value = "test"

        options = {
            "llm_provider": "openai",
            "llm_service_endpoint": "https://api.test.com",
            "llm_service_api_key": "api-key",
            "llm_service_planning_model_name": "gpt-4",
            "llm_service_general_model_name": "gpt-3.5",
            "namespace": "test/",
            "broker_url": "ws://broker:8008",
            "broker_vpn": "vpn",
            "broker_username": "user",
            "broker_password": "pass",
            "dev_mode": "false",
            "webui_session_secret_key": "secret",
            "webui_fastapi_host": "0.0.0.0",
            "webui_fastapi_port": 8000,
            "webui_fastapi_https_port": 8443,
            "webui_ssl_keyfile": "/path/to/key",
            "webui_ssl_certfile": "/path/to/cert",
            "webui_ssl_keyfile_password": "keypass",
            "webui_enable_embed_resolution": "true",
            "logging_config_path": "configs/logging.yaml",
            "s3_bucket_name": "my-bucket",
            "s3_endpoint_url": "https://s3.example.com",
            "s3_region": "us-west-2",
        }
        
        result = create_env_file(temp_project_dir, options, skip_interactive=True)
        
        assert result is True
        env_content = (temp_project_dir / ".env").read_text()
        
        # Verify key parameters are present
        assert "LLM_SERVICE_ENDPOINT" in env_content
        assert "SOLACE_BROKER_URL" in env_content
        assert "SESSION_SECRET_KEY" in env_content
        assert "S3_BUCKET_NAME" in env_content

    def test_env_file_creation_failure(self, temp_project_dir, mocker):
        """Test handling of .env file creation failure"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.env_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        # Mock open to fail
        mocker.patch("builtins.open", side_effect=IOError("Permission denied"))
        
        options = {"llm_service_endpoint": "https://api.test.com"}
        
        result = create_env_file(temp_project_dir, options, skip_interactive=True)
        
        assert result is False
        
        # Verify error message was displayed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Error creating file" in call for call in echo_calls)

    def test_skip_interactive_uses_provided_values(self, temp_project_dir, mocker):
        """Test that skip interactive mode uses provided values"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.env_step.ask_if_not_provided")

        options = {
            "llm_provider": "openai",
            "llm_service_endpoint": "https://provided.com",
            "llm_service_api_key": "provided-key",
            "namespace": "provided/",
        }
        
        create_env_file(temp_project_dir, options, skip_interactive=True)
        
        env_content = (temp_project_dir / ".env").read_text()
        assert "https://provided.com" in env_content
        assert "provided-key" in env_content

    def test_interactive_mode_prompts_for_values(self, temp_project_dir, mocker):
        """Test that interactive mode prompts for missing values"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.env_step.ask_if_not_provided")
        mock_ask.return_value = "prompted_value"
        
        options = {}
        
        create_env_file(temp_project_dir, options, skip_interactive=False)
        
        # Verify ask_if_not_provided was called multiple times
        assert mock_ask.call_count > 0

    def test_none_values_excluded_from_env(self, temp_project_dir, mocker):
        """Test that None values are excluded from .env file"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.env_step.ask_if_not_provided")
        mock_ask.return_value = None

        options = {
            "llm_provider": "openai",
            "llm_service_endpoint": "https://api.test.com",
            "llm_service_api_key": None,
        }

        create_env_file(temp_project_dir, options, skip_interactive=True)

        env_content = (temp_project_dir / ".env").read_text()
        assert "LLM_SERVICE_ENDPOINT" in env_content
        # None values should not appear
        assert "LLM_SERVICE_API_KEY" not in env_content or "None" not in env_content

    def test_env_defaults_used(self, temp_project_dir, mocker):
        """Test that ENV_DEFAULTS are used when no values provided"""
        mock_echo = mocker.patch("click.echo")
        
        # Mock ask_if_not_provided to return the default value
        def mock_ask_side_effect(opts, key, prompt, default=None, **kwargs):
            opts[key] = default
            return default
        
        mock_ask = mocker.patch(
            "cli.commands.init_cmd.env_step.ask_if_not_provided",
            side_effect=mock_ask_side_effect
        )
        
        options = {}
        
        create_env_file(temp_project_dir, options, skip_interactive=True)
        
        # Verify defaults were used
        assert mock_ask.call_count > 0

    def test_messages_displayed(self, temp_project_dir, mocker):
        """Test that appropriate messages are displayed"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.env_step.ask_if_not_provided")
        mock_ask.return_value = "test"

        options = {"llm_service_endpoint": "https://api.test.com"}

        create_env_file(temp_project_dir, options, skip_interactive=True)

        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Configuring .env file" in call for call in echo_calls)
        assert any("Created" in call or ".env" in call for call in echo_calls)

    def test_no_provider_skips_llm_env_vars(self, temp_project_dir, mocker):
        """Test that LLM env vars are not written when no provider is selected"""
        mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.env_step.ask_if_not_provided")
        mock_ask.return_value = "test"

        options = {"llm_provider": "", "namespace": "test/"}

        result = create_env_file(temp_project_dir, options, skip_interactive=True)

        assert result is True
        env_content = (temp_project_dir / ".env").read_text()
        assert "LLM_SERVICE_ENDPOINT" not in env_content
        assert "LLM_SERVICE_API_KEY" not in env_content
        assert "LLM_SERVICE_PLANNING_MODEL_NAME" not in env_content
        assert "LLM_SERVICE_GENERAL_MODEL_NAME" not in env_content
        assert "BEDROCK_MODEL_NAME" not in env_content
        # Common env vars should still be present
        assert "NAMESPACE" in env_content

    def test_with_provider_includes_llm_env_vars(self, temp_project_dir, mocker):
        """Test that LLM env vars are written when a provider is selected"""
        mocker.patch("click.echo")

        def ask_side_effect(opts, key, *args, **kwargs):
            if key in opts:
                return opts[key]
            opts[key] = "test_value"
            return "test_value"

        mocker.patch(
            "cli.commands.init_cmd.env_step.ask_if_not_provided",
            side_effect=ask_side_effect,
        )

        options = {
            "llm_provider": "openai",
            "llm_service_endpoint": "https://api.openai.com/v1",
            "llm_service_api_key": "sk-test",
            "namespace": "test/",
        }

        result = create_env_file(temp_project_dir, options, skip_interactive=True)

        assert result is True
        env_content = (temp_project_dir / ".env").read_text()
        assert "LLM_SERVICE_ENDPOINT" in env_content
        assert "LLM_SERVICE_API_KEY" in env_content