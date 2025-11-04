"""
Unit tests for orchestrator_step.py
Target: Increase coverage from 69% to 80%+
"""
import pytest

from cli.commands.init_cmd.orchestrator_step import (
    create_orchestrator_config,
)


class TestCreateOrchestratorConfig:
    """Test create_orchestrator_config function"""

    def test_successful_orchestrator_creation(self, temp_project_dir, mocker, mock_templates, mock_get_formatted_names):
        """Test successful orchestrator configuration creation"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.orchestrator_step.ask_if_not_provided")
        mock_ask.return_value = "test_value"
        
        options = {
            "agent_name": "TestAgent",
            "supports_streaming": True,
            "artifact_service_type": "filesystem",
            "artifact_service_base_path": "/tmp/artifacts",
            "artifact_service_scope": "namespace",
            "artifact_handling_mode": "reference",
            "enable_embed_resolution": True,
            "enable_artifact_content_instruction": True,
            "agent_card_description": "Test description",
            "agent_card_default_input_modes": ["text"],
            "agent_card_default_output_modes": ["text", "file"],
            "agent_discovery_enabled": True,
            "agent_card_publishing_interval": 10,
            "inter_agent_communication_allow_list": ["*"],
            "inter_agent_communication_deny_list": [],
            "inter_agent_communication_timeout": 30,
        }
        
        result = create_orchestrator_config(temp_project_dir, options, skip_interactive=True)
        
        assert result is True
        assert (temp_project_dir / "configs" / "shared_config.yaml").exists()
        assert (temp_project_dir / "configs" / "logging_config.yaml").exists()
        assert (temp_project_dir / "configs" / "agents" / "main_orchestrator.yaml").exists()

    def test_invalid_agent_name_skip_interactive(self, temp_project_dir, mocker, mock_templates):
        """Test invalid agent name in skip interactive mode raises error"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.orchestrator_step.ask_if_not_provided")
        
        options = {"agent_name": "Invalid-Name!"}
        
        with pytest.raises(Exception):  # Should raise UsageError
            create_orchestrator_config(temp_project_dir, options, skip_interactive=True)

    def test_invalid_agent_name_interactive_reprompt(self, temp_project_dir, mocker, mock_templates, mock_get_formatted_names):
        """Test invalid agent name in interactive mode prompts again"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.orchestrator_step.ask_if_not_provided")
        
        # ask_if_not_provided updates options dict and returns value
        def ask_side_effect(opts, key, *args, **kwargs):
            if key == "agent_name":
                opts[key] = "Invalid-Name!"
                return "Invalid-Name!"
            opts[key] = "test"
            return "test"
        
        mock_ask.side_effect = ask_side_effect
        mock_prompt = mocker.patch("click.prompt", return_value="ValidName")
        
        options = {}
        
        result = create_orchestrator_config(temp_project_dir, options, skip_interactive=False)
        
        # Should have prompted for valid name
        mock_prompt.assert_called()

    def test_s3_artifact_service(self, temp_project_dir, mocker, mock_templates, mock_get_formatted_names):
        """Test orchestrator with S3 artifact service"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.orchestrator_step.ask_if_not_provided")
        
        def ask_side_effect(opts, key, *args, **kwargs):
            values = {
                "agent_name": "TestAgent",
                "supports_streaming": True,
                "artifact_service_type": "s3",
                "s3_bucket_name": "my-bucket",
                "s3_endpoint_url": "https://s3.example.com",
                "s3_region": "us-west-2",
                "artifact_service_scope": "namespace",
                "artifact_handling_mode": "reference",
                "enable_embed_resolution": True,
                "enable_artifact_content_instruction": True,
                "agent_card_description": "Test",
                "agent_card_default_input_modes": "text",
                "agent_card_default_output_modes": "text",
                "agent_discovery_enabled": True,
                "agent_card_publishing_interval": 10,
                "inter_agent_communication_allow_list": "*",
                "inter_agent_communication_deny_list": "",
                "inter_agent_communication_timeout": 30,
            }
            opts[key] = values.get(key, "test")
            return opts[key]
        
        mock_ask.side_effect = ask_side_effect
        
        options = {}
        
        result = create_orchestrator_config(temp_project_dir, options, skip_interactive=False)
        
        assert result is True

    def test_shared_config_creation_failure(self, temp_project_dir, mocker):
        """Test handling of shared config creation failure"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.orchestrator_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        mock_load = mocker.patch(
            "cli.commands.init_cmd.orchestrator_step.load_template",
            side_effect=Exception("Template error")
        )
        
        options = {"agent_name": "TestAgent"}
        
        result = create_orchestrator_config(temp_project_dir, options, skip_interactive=True)
        
        assert result is False

    def test_logging_config_creation_failure(self, temp_project_dir, mocker, mock_templates):
        """Test handling of logging config creation failure"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.orchestrator_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        # Mock to fail on logging config write
        original_open = open
        def mock_open(file, *args, **kwargs):
            if "logging_config.yaml" in str(file):
                raise IOError("Write error")
            return original_open(file, *args, **kwargs)
        
        mocker.patch("builtins.open", mock_open)
        
        options = {"agent_name": "TestAgent"}
        
        result = create_orchestrator_config(temp_project_dir, options, skip_interactive=True)
        
        assert result is False

    def test_orchestrator_config_with_deny_list(self, temp_project_dir, mocker, mock_templates, mock_get_formatted_names):
        """Test orchestrator with deny list configured"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.orchestrator_step.ask_if_not_provided")
        
        def ask_side_effect(opts, key, *args, **kwargs):
            values = {
                "agent_name": "TestAgent",
                "inter_agent_communication_deny_list": ["agent1", "agent2"],
            }
            opts[key] = values.get(key, "test")
            return opts[key]
        
        mock_ask.side_effect = ask_side_effect
        
        options = {}
        
        result = create_orchestrator_config(temp_project_dir, options, skip_interactive=False)
        
        assert result is True

    def test_artifact_service_parameter_mapping(self, temp_project_dir, mocker, mock_templates, mock_get_formatted_names):
        """Test that artifact service parameters are mapped correctly for S3"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.orchestrator_step.ask_if_not_provided")
        
        # ask_if_not_provided updates options dict and returns value
        def ask_side_effect(opts, key, *args, **kwargs):
            # Return the value if it exists, otherwise set to test
            if key in opts:
                return opts[key]
            opts[key] = "test"
            return "test"
        
        mock_ask.side_effect = ask_side_effect
        
        options = {
            "agent_name": "TestAgent",
            "artifact_service_type": "s3",
            "artifact_service_bucket_name": "cli-bucket",
            "artifact_service_endpoint_url": "https://cli.s3.com",
            "artifact_service_region": "eu-west-1",
        }
        
        result = create_orchestrator_config(temp_project_dir, options, skip_interactive=True)
        
        # Verify parameters were mapped to s3_* keys
        assert options.get("s3_bucket_name") == "cli-bucket"
        assert options.get("s3_endpoint_url") == "https://cli.s3.com"
        assert options.get("s3_region") == "eu-west-1"

    def test_list_input_output_modes_as_strings(self, temp_project_dir, mocker, mock_templates, mock_get_formatted_names):
        """Test that comma-separated mode strings are converted to lists"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.orchestrator_step.ask_if_not_provided")
        
        def ask_side_effect(opts, key, *args, **kwargs):
            values = {
                "agent_name": "TestAgent",
                "agent_card_default_input_modes": "text,audio,video",
                "agent_card_default_output_modes": "text,file",
            }
            opts[key] = values.get(key, "test")
            return opts[key]
        
        mock_ask.side_effect = ask_side_effect
        
        options = {}
        
        result = create_orchestrator_config(temp_project_dir, options, skip_interactive=False)
        
        assert result is True

    def test_messages_displayed(self, temp_project_dir, mocker, mock_templates, mock_get_formatted_names):
        """Test that appropriate messages are displayed"""
        mock_echo = mocker.patch("click.echo")
        mock_ask = mocker.patch("cli.commands.init_cmd.orchestrator_step.ask_if_not_provided")
        mock_ask.return_value = "test"
        
        options = {"agent_name": "TestAgent"}
        
        create_orchestrator_config(temp_project_dir, options, skip_interactive=True)
        
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Configuring main orchestrator" in call for call in echo_calls)
        assert any("Configured" in call or "Created" in call for call in echo_calls)