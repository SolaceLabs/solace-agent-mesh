"""
Unit tests for cli/commands/add_cmd/agent_cmd.py

Tests the agent command including:
- Agent creation in interactive mode
- Non-interactive mode with --skip flag
- Various agent configurations (LLM providers, tools, etc.)
- Name formatting and placeholder replacement
- Overwrite confirmation
- Error handling (missing templates, invalid inputs)
- GUI mode (basic invocation)
- Session service configurations
- Artifact service configurations
- Agent card configurations
- Tool configurations
"""

import os
from pathlib import Path
import pytest
from click.testing import CliRunner

from cli.commands.add_cmd.agent_cmd import (
    add_agent,
    create_agent_config,
    _write_agent_yaml_from_data,
    _append_to_env_file,
)
from config_portal.backend.common import USE_DEFAULT_SHARED_ARTIFACT


@pytest.fixture
def runner():
    """Create a Click CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory"""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    
    # Create necessary directories
    (project_path / "configs" / "agents").mkdir(parents=True)
    (project_path / "data").mkdir()
    (project_path / ".env").write_text("")
    
    return project_path


@pytest.fixture
def mock_template(mocker):
    """Mock template loading"""
    template_content = """
namespace: __NAMESPACE__
agent_name: __AGENT_NAME__
supports_streaming: __SUPPORTS_STREAMING__
model: __MODEL_ALIAS__
instruction: |
__INSTRUCTION__
tools: __TOOLS_CONFIG__
session_service: __SESSION_SERVICE__
artifact_service: __ARTIFACT_SERVICE__
artifact_handling_mode: __ARTIFACT_HANDLING_MODE__
enable_embed_resolution: __ENABLE_EMBED_RESOLUTION__
enable_artifact_content_instruction: __ENABLE_ARTIFACT_CONTENT_INSTRUCTION__
agent_card:
  description: |
__AGENT_CARD_DESCRIPTION__
  default_input_modes: __DEFAULT_INPUT_MODES__
  default_output_modes: __DEFAULT_OUTPUT_MODES__
  skills: __AGENT_CARD_SKILLS__
  publishing_interval: __AGENT_CARD_PUBLISHING_INTERVAL__
agent_discovery_enabled: __AGENT_DISCOVERY_ENABLED__
inter_agent_communication:
  allow_list: __INTER_AGENT_COMMUNICATION_ALLOW_LIST__
  deny_list: __INTER_AGENT_COMMUNICATION_DENY_LIST__
  timeout: __INTER_AGENT_COMMUNICATION_TIMEOUT__
"""
    return mocker.patch("cli.commands.add_cmd.agent_cmd.load_template", return_value=template_content)


class TestAppendToEnvFile:
    """Tests for _append_to_env_file function"""
    
    def test_append_to_env_file_success(self, project_dir):
        """Test successfully appending to .env file"""
        result = _append_to_env_file(project_dir, "TEST_KEY", "test_value")
        
        assert result is True
        env_content = (project_dir / ".env").read_text()
        assert 'TEST_KEY="test_value"' in env_content
    
    def test_append_to_env_file_creates_newlines(self, project_dir):
        """Test that append adds proper newlines"""
        _append_to_env_file(project_dir, "KEY1", "value1")
        _append_to_env_file(project_dir, "KEY2", "value2")
        
        env_content = (project_dir / ".env").read_text()
        assert env_content.count('\n') >= 2
    
    def test_append_to_env_file_permission_error(self, project_dir, mocker):
        """Test handling of permission errors"""
        mocker.patch("builtins.open", side_effect=OSError("Permission denied"))
        
        result = _append_to_env_file(project_dir, "TEST_KEY", "test_value")
        
        assert result is False


class TestWriteAgentYamlFromData:
    """Tests for _write_agent_yaml_from_data function"""
    
    def test_write_agent_yaml_basic(self, project_dir, mock_template):
        """Test basic agent YAML creation"""
        config_options = {
            "namespace": "test/namespace",
            "supports_streaming": True,
            "model_type": "general",
            "instruction": "Test instruction",
            "session_service_type": "sql",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
            "artifact_handling_mode": "embed",
            "enable_embed_resolution": True,
            "enable_artifact_content_instruction": True,
            "agent_card_description": "Test description",
            "agent_card_default_input_modes": ["text"],
            "agent_card_default_output_modes": ["text"],
            "agent_card_publishing_interval": 60,
            "agent_discovery_enabled": True,
            "inter_agent_communication_allow_list": ["*"],
            "inter_agent_communication_deny_list": [],
            "inter_agent_communication_timeout": 30,
            "tools": [],
        }
        
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            success, message, file_path = _write_agent_yaml_from_data(
                "TestAgent", config_options, project_dir
            )
            
            assert success is True
            assert "Agent configuration created" in message
            assert file_path
            
            # Verify file was created
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            assert agent_file.exists()
            
            # Verify content
            content = agent_file.read_text()
            assert "TestAgent" in content
            assert "test/namespace" in content
        finally:
            os.chdir(original_cwd)
    
    def test_write_agent_yaml_with_sql_session_service(self, project_dir, mock_template):
        """Test agent YAML with SQL session service"""
        config_options = {
            "namespace": "test/namespace",
            "supports_streaming": True,
            "model_type": "general",
            "instruction": "Test instruction",
            "session_service_type": "sql",
            "session_service_behavior": "PERSISTENT",
            "database_url": "default_agent_db",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
            "artifact_handling_mode": "embed",
            "enable_embed_resolution": True,
            "enable_artifact_content_instruction": True,
            "agent_card_description": "Test description",
            "agent_card_default_input_modes": ["text"],
            "agent_card_default_output_modes": ["text"],
            "agent_card_publishing_interval": 60,
            "agent_discovery_enabled": True,
            "inter_agent_communication_allow_list": ["*"],
            "inter_agent_communication_deny_list": [],
            "inter_agent_communication_timeout": 30,
            "tools": [],
        }
        
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            success, message, file_path = _write_agent_yaml_from_data(
                "TestAgent", config_options, project_dir
            )
            
            assert success is True
            
            # Verify .env was updated with database URL
            env_content = (project_dir / ".env").read_text()
            assert "TEST_AGENT_DATABASE_URL" in env_content
            assert "sqlite:///" in env_content
        finally:
            os.chdir(original_cwd)
    
    def test_write_agent_yaml_with_filesystem_artifact_service(self, project_dir, mock_template):
        """Test agent YAML with filesystem artifact service"""
        config_options = {
            "namespace": "test/namespace",
            "supports_streaming": True,
            "model_type": "general",
            "instruction": "Test instruction",
            "session_service_type": "sql",
            "artifact_service_type": "filesystem",
            "artifact_service_base_path": "/tmp/artifacts",
            "artifact_service_scope": "namespace",
            "artifact_handling_mode": "embed",
            "enable_embed_resolution": True,
            "enable_artifact_content_instruction": True,
            "agent_card_description": "Test description",
            "agent_card_default_input_modes": ["text"],
            "agent_card_default_output_modes": ["text"],
            "agent_card_publishing_interval": 60,
            "agent_discovery_enabled": True,
            "inter_agent_communication_allow_list": ["*"],
            "inter_agent_communication_deny_list": [],
            "inter_agent_communication_timeout": 30,
            "tools": [],
        }
        
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            success, message, file_path = _write_agent_yaml_from_data(
                "TestAgent", config_options, project_dir
            )
            
            assert success is True
            
            # Verify file content includes filesystem config
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "filesystem" in content
            assert "/tmp/artifacts" in content
        finally:
            os.chdir(original_cwd)
    
    def test_write_agent_yaml_with_s3_artifact_service(self, project_dir, mock_template):
        """Test agent YAML with S3 artifact service"""
        config_options = {
            "namespace": "test/namespace",
            "supports_streaming": True,
            "model_type": "general",
            "instruction": "Test instruction",
            "session_service_type": "sql",
            "artifact_service_type": "s3",
            "artifact_service_scope": "app",
            "artifact_handling_mode": "embed",
            "enable_embed_resolution": True,
            "enable_artifact_content_instruction": True,
            "agent_card_description": "Test description",
            "agent_card_default_input_modes": ["text"],
            "agent_card_default_output_modes": ["text"],
            "agent_card_publishing_interval": 60,
            "agent_discovery_enabled": True,
            "inter_agent_communication_allow_list": ["*"],
            "inter_agent_communication_deny_list": [],
            "inter_agent_communication_timeout": 30,
            "tools": [],
        }
        
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            success, message, file_path = _write_agent_yaml_from_data(
                "TestAgent", config_options, project_dir
            )
            
            assert success is True
            
            # Verify file content includes S3 config
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "s3" in content or "S3" in content
        finally:
            os.chdir(original_cwd)
    
    def test_write_agent_yaml_with_tools(self, project_dir, mock_template):
        """Test agent YAML with tools configuration"""
        tools_config = [
            {
                "tool_type": "builtin",
                "name": "web_search",
                "enabled": True
            },
            {
                "tool_type": "mcp",
                "name": "custom_tool",
                "connection_params": {
                    "command": "node",
                    "args": ["server.js"]
                }
            }
        ]
        
        config_options = {
            "namespace": "test/namespace",
            "supports_streaming": True,
            "model_type": "general",
            "instruction": "Test instruction",
            "session_service_type": "sql",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
            "artifact_handling_mode": "embed",
            "enable_embed_resolution": True,
            "enable_artifact_content_instruction": True,
            "agent_card_description": "Test description",
            "agent_card_default_input_modes": ["text"],
            "agent_card_default_output_modes": ["text"],
            "agent_card_publishing_interval": 60,
            "agent_discovery_enabled": True,
            "inter_agent_communication_allow_list": ["*"],
            "inter_agent_communication_deny_list": [],
            "inter_agent_communication_timeout": 30,
            "tools": tools_config,
        }
        
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            success, message, file_path = _write_agent_yaml_from_data(
                "TestAgent", config_options, project_dir
            )
            
            assert success is True
            
            # Verify tools are in the file
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "web_search" in content
            assert "custom_tool" in content
        finally:
            os.chdir(original_cwd)
    
    def test_write_agent_yaml_adds_mcp_timeout(self, project_dir, mock_template):
        """Test that MCP tools get default timeout added"""
        tools_config = [
            {
                "tool_type": "mcp",
                "name": "mcp_tool",
                "connection_params": {
                    "command": "node",
                    "args": ["server.js"]
                }
            }
        ]
        
        config_options = {
            "namespace": "test/namespace",
            "supports_streaming": True,
            "model_type": "general",
            "instruction": "Test instruction",
            "session_service_type": "sql",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
            "artifact_handling_mode": "embed",
            "enable_embed_resolution": True,
            "enable_artifact_content_instruction": True,
            "agent_card_description": "Test description",
            "agent_card_default_input_modes": ["text"],
            "agent_card_default_output_modes": ["text"],
            "agent_card_publishing_interval": 60,
            "agent_discovery_enabled": True,
            "inter_agent_communication_allow_list": ["*"],
            "inter_agent_communication_deny_list": [],
            "inter_agent_communication_timeout": 30,
            "tools": tools_config,
        }
        
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            success, message, file_path = _write_agent_yaml_from_data(
                "TestAgent", config_options, project_dir
            )
            
            assert success is True
            
            # Verify timeout was added
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "timeout" in content
        finally:
            os.chdir(original_cwd)
    
    def test_write_agent_yaml_with_skills(self, project_dir, mock_template):
        """Test agent YAML with agent card skills"""
        skills_config = [
            {"name": "Skill 1", "description": "Description 1"},
            {"name": "Skill 2", "description": "Description 2"}
        ]
        
        config_options = {
            "namespace": "test/namespace",
            "supports_streaming": True,
            "model_type": "general",
            "instruction": "Test instruction",
            "session_service_type": "sql",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
            "artifact_handling_mode": "embed",
            "enable_embed_resolution": True,
            "enable_artifact_content_instruction": True,
            "agent_card_description": "Test description",
            "agent_card_default_input_modes": ["text"],
            "agent_card_default_output_modes": ["text"],
            "agent_card_skills": skills_config,
            "agent_card_publishing_interval": 60,
            "agent_discovery_enabled": True,
            "inter_agent_communication_allow_list": ["*"],
            "inter_agent_communication_deny_list": [],
            "inter_agent_communication_timeout": 30,
            "tools": [],
        }
        
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            success, message, file_path = _write_agent_yaml_from_data(
                "TestAgent", config_options, project_dir
            )
            
            assert success is True
            
            # Verify skills are in the file
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "Skill 1" in content
            assert "Skill 2" in content
        finally:
            os.chdir(original_cwd)
    
    def test_write_agent_yaml_name_formatting(self, project_dir, mock_template):
        """Test agent name formatting (snake_case, PascalCase, etc.)"""
        config_options = {
            "namespace": "test/namespace",
            "supports_streaming": True,
            "model_type": "general",
            "instruction": "Test instruction",
            "session_service_type": "sql",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
            "artifact_handling_mode": "embed",
            "enable_embed_resolution": True,
            "enable_artifact_content_instruction": True,
            "agent_card_description": "Test description",
            "agent_card_default_input_modes": ["text"],
            "agent_card_default_output_modes": ["text"],
            "agent_card_publishing_interval": 60,
            "agent_discovery_enabled": True,
            "inter_agent_communication_allow_list": ["*"],
            "inter_agent_communication_deny_list": [],
            "inter_agent_communication_timeout": 30,
            "tools": [],
        }
        
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            # Test with kebab-case input
            success, message, file_path = _write_agent_yaml_from_data(
                "my-test-agent", config_options, project_dir
            )
            
            assert success is True
            
            # File should be snake_case
            agent_file = project_dir / "configs" / "agents" / "my_test_agent_agent.yaml"
            assert agent_file.exists()
        finally:
            os.chdir(original_cwd)
    
    def test_write_agent_yaml_error_handling(self, project_dir, mocker):
        """Test error handling in YAML writing"""
        mocker.patch("cli.commands.add_cmd.agent_cmd.load_template", side_effect=Exception("Template error"))
        
        config_options = {}
        
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            success, message, file_path = _write_agent_yaml_from_data(
                "TestAgent", config_options, project_dir
            )
            
            assert success is False
            assert "Error creating agent configuration" in message
        finally:
            os.chdir(original_cwd)


class TestCreateAgentConfig:
    """Tests for create_agent_config function"""
    
    def test_create_agent_config_skip_mode(self, project_dir, mock_template, mocker):
        """Test creating agent config in skip mode"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            cli_options = {
                "namespace": "test/namespace",
                "model_type": "general",
            }
            
            result = create_agent_config("TestAgent", cli_options, skip_interactive=True)
            
            assert result is True
            
            # Verify file was created
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            assert agent_file.exists()
        finally:
            os.chdir(original_cwd)
    
    def test_create_agent_config_interactive_mode(self, project_dir, mock_template, mocker):
        """Test creating agent config in interactive mode"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            # Mock ask_if_not_provided to return defaults
            mock_ask = mocker.patch("cli.commands.add_cmd.agent_cmd.ask_if_not_provided")
            mock_ask.side_effect = lambda opts, key, prompt, default, skip, **kwargs: default
            
            cli_options = {}
            
            result = create_agent_config("TestAgent", cli_options, skip_interactive=False)
            
            assert result is True
            # ask_if_not_provided should have been called multiple times
            assert mock_ask.call_count > 0
        finally:
            os.chdir(original_cwd)


class TestAddAgentCommand:
    """Tests for the add_agent CLI command"""
    
    def test_add_agent_requires_name_without_gui(self, runner):
        """Test that agent name is required when not using GUI"""
        result = runner.invoke(add_agent, [])
        
        assert result.exit_code != 0 or "must provide an agent name" in result.output
    
    def test_add_agent_with_name_and_skip(self, runner, project_dir, mock_template, mocker):
        """Test add agent with name and --skip flag"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            result = runner.invoke(add_agent, ["TestAgent", "--skip"])
            
            assert result.exit_code == 0
            
            # Verify file was created
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            assert agent_file.exists()
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_with_namespace_option(self, runner, project_dir, mock_template, mocker):
        """Test add agent with --namespace option"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            result = runner.invoke(add_agent, [
                "TestAgent",
                "--skip",
                "--namespace", "custom/namespace"
            ])
            
            assert result.exit_code == 0
            
            # Verify namespace in file
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "custom/namespace" in content
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_with_model_type_option(self, runner, project_dir, mock_template, mocker):
        """Test add agent with --model-type option"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            result = runner.invoke(add_agent, [
                "TestAgent",
                "--skip",
                "--model-type", "planning"
            ])
            
            assert result.exit_code == 0
            
            # Verify model type in file
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "planning" in content
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_with_instruction_option(self, runner, project_dir, mock_template, mocker):
        """Test add agent with --instruction option"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            result = runner.invoke(add_agent, [
                "TestAgent",
                "--skip",
                "--instruction", "Custom instruction for agent"
            ])
            
            assert result.exit_code == 0
            
            # Verify instruction in file
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "Custom instruction" in content
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_with_artifact_service_options(self, runner, project_dir, mock_template, mocker):
        """Test add agent with artifact service options"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            result = runner.invoke(add_agent, [
                "TestAgent",
                "--skip",
                "--artifact-service-type", "filesystem",
                "--artifact-service-base-path", "/custom/path",
                "--artifact-service-scope", "namespace"
            ])
            
            assert result.exit_code == 0
            
            # Verify artifact service config
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "filesystem" in content
            assert "/custom/path" in content
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_with_session_service_options(self, runner, project_dir, mock_template, mocker):
        """Test add agent with session service options"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            result = runner.invoke(add_agent, [
                "TestAgent",
                "--skip",
                "--session-service-type", "sql",
                "--session-service-behavior", "PERSISTENT",
                "--database-url", "sqlite:///custom.db"
            ])
            
            assert result.exit_code == 0
            
            # Verify session service config
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            assert agent_file.exists()
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_with_boolean_flags(self, runner, project_dir, mock_template, mocker):
        """Test add agent with boolean flags"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            result = runner.invoke(add_agent, [
                "TestAgent",
                "--skip",
                "--supports-streaming", "true",
                "--enable-embed-resolution", "true",
                "--agent-discovery-enabled", "false"
            ])
            
            assert result.exit_code == 0
            
            # Verify boolean values in file
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "true" in content.lower()
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_with_agent_card_options(self, runner, project_dir, mock_template, mocker):
        """Test add agent with agent card options"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            result = runner.invoke(add_agent, [
                "TestAgent",
                "--skip",
                "--agent-card-description", "Custom description",
                "--agent-card-default-input-modes-str", "text,audio",
                "--agent-card-default-output-modes-str", "text,image",
                "--agent-card-publishing-interval", "120"
            ])
            
            assert result.exit_code == 0
            
            # Verify agent card config
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            content = agent_file.read_text()
            assert "Custom description" in content
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_with_inter_agent_communication_options(self, runner, project_dir, mock_template, mocker):
        """Test add agent with inter-agent communication options"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            result = runner.invoke(add_agent, [
                "TestAgent",
                "--skip",
                "--inter-agent-communication-allow-list-str", "agent1,agent2",
                "--inter-agent-communication-deny-list-str", "agent3",
                "--inter-agent-communication-timeout", "60"
            ])
            
            assert result.exit_code == 0
            
            # Verify inter-agent config
            agent_file = project_dir / "configs" / "agents" / "test_agent_agent.yaml"
            assert agent_file.exists()
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_gui_mode(self, runner, project_dir, mock_template, mocker):
        """Test add agent with --gui flag"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            # Mock the GUI launch function
            mock_gui = mocker.patch("cli.commands.add_cmd.agent_cmd.launch_add_agent_web_portal")
            mock_gui.return_value = ("TestAgent", {"namespace": "test"}, project_dir)
            
            result = runner.invoke(add_agent, ["TestAgent", "--gui"])
            
            assert result.exit_code == 0
            mock_gui.assert_called_once()
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_failure_exits_with_error(self, runner, project_dir, mocker):
        """Test add agent exits with error on failure"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            # Mock create_agent_config to return False
            mocker.patch("cli.commands.add_cmd.agent_cmd.create_agent_config", return_value=False)
            
            result = runner.invoke(add_agent, ["TestAgent", "--skip"])
            
            assert result.exit_code == 1
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_with_all_model_types(self, runner, project_dir, mock_template, mocker):
        """Test add agent with all available model types"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        model_types = ["planning", "general", "image_gen", "report_gen", "multimodal", "gemini_pro"]
        
        try:
            for model_type in model_types:
                result = runner.invoke(add_agent, [
                    f"Agent{model_type.title()}",
                    "--skip",
                    "--model-type", model_type
                ])
                
                assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)
    
    def test_add_agent_creates_directory_structure(self, runner, tmp_path, mock_template, mocker):
        """Test that add agent creates necessary directory structure"""
        project_path = tmp_path / "new_project"
        project_path.mkdir()
        (project_path / ".env").write_text("")
        
        original_cwd = Path.cwd()
        os.chdir(project_path)
        
        try:
            result = runner.invoke(add_agent, ["TestAgent", "--skip"])
            
            assert result.exit_code == 0
            
            # Verify directory structure was created
            assert (project_path / "configs" / "agents").exists()
        finally:
            os.chdir(original_cwd)