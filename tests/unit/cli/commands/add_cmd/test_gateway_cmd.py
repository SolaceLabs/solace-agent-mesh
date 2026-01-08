"""
Unit tests for cli/commands/add_cmd/gateway_cmd.py

Tests the gateway command including:
- Interactive mode with user prompts
- Non-interactive mode with --skip flag
- File generation and content verification
- Name formatting (camelCase, snake_case, etc.)
- Artifact service type configurations
- Overwrite confirmation behavior
- Error handling (missing templates, file permissions, invalid inputs)
- Template placeholder replacement

Note: GUI mode tests are excluded due to import dependencies.
"""

import os
import shutil
from pathlib import Path
from importlib import import_module
import pytest

# Import the specific function we're testing by loading the module directly
gateway_cmd_module = import_module('cli.commands.add_cmd.gateway_cmd')
create_gateway_files = gateway_cmd_module.create_gateway_files

from config_portal.backend.common import GATEWAY_DEFAULTS, USE_DEFAULT_SHARED_ARTIFACT


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory for testing"""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    
    # Create necessary directory structure
    (project_path / "configs" / "gateways").mkdir(parents=True)
    (project_path / "src").mkdir(parents=True)
    
    # Store the original CWD and change to the new project directory
    original_cwd = Path.cwd()
    os.chdir(project_path)
    
    yield project_path
    
    # Restore the original CWD and clean up
    os.chdir(original_cwd)
    shutil.rmtree(project_path, ignore_errors=True)


@pytest.fixture
def mock_templates(mocker):
    """Mock template loading to avoid file system dependencies"""
    mock_config_template = """
namespace: __APP_CONFIG_NAMESPACE__
gateway_id: __GATEWAY_ID__
artifact_service: __ARTIFACT_SERVICE__
system_purpose: |
__SYSTEM_PURPOSE__
response_format: |
__RESPONSE_FORMAT__
"""
    
    mock_app_template = """
# __GATEWAY_NAME_PASCAL_CASE__ Gateway App
# Gateway: __GATEWAY_NAME_SNAKE_CASE__
"""
    
    mock_component_template = """
# __GATEWAY_NAME_PASCAL_CASE__ Component
# Gateway: __GATEWAY_NAME_KEBAB_CASE__
"""
    
    def load_template_side_effect(name):
        if "config" in name:
            return mock_config_template
        elif "app" in name:
            return mock_app_template
        elif "component" in name:
            return mock_component_template
        return ""
    
    return mocker.patch(
        "cli.commands.add_cmd.gateway_cmd.load_template",
        side_effect=load_template_side_effect
    )


class TestCreateGatewayFiles:
    """Tests for the create_gateway_files function"""
    
    def test_create_gateway_files_skip_mode_default_artifact(self, project_dir, mock_templates):
        """Test creating gateway files in skip mode with default artifact service"""
        cli_options = {
            "namespace": "test/namespace",
            "gateway_id": "test-gateway-gw-01",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
        }
        
        success, message = create_gateway_files(
            gateway_name_input="TestGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is True
        assert "Gateway 'test_gateway' skeleton created successfully" in message
        
        # Verify files were created
        assert (project_dir / "configs" / "gateways" / "test_gateway_config.yaml").exists()
        assert (project_dir / "src" / "test_gateway" / "app.py").exists()
        assert (project_dir / "src" / "test_gateway" / "component.py").exists()
        assert (project_dir / "src" / "test_gateway" / "__init__.py").exists()
        
        # Verify config content
        config_content = (project_dir / "configs" / "gateways" / "test_gateway_config.yaml").read_text()
        assert "namespace: test/namespace" in config_content
        assert "gateway_id: test-gateway-gw-01" in config_content
        assert "artifact_service: *default_artifact_service" in config_content
    
    def test_create_gateway_files_filesystem_artifact_service(self, project_dir, mock_templates):
        """Test creating gateway with filesystem artifact service"""
        cli_options = {
            "namespace": "prod/namespace",
            "gateway_id": "my-gw-01",
            "artifact_service_type": "filesystem",
            "artifact_service_base_path": "/custom/path",
            "artifact_service_scope": "app",
        }
        
        success, message = create_gateway_files(
            gateway_name_input="MyGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is True
        
        config_content = (project_dir / "configs" / "gateways" / "my_gateway_config.yaml").read_text()
        assert 'type: "filesystem"' in config_content
        assert "base_path:" in config_content
        assert "artifact_scope: app" in config_content
    
    def test_create_gateway_files_memory_artifact_service(self, project_dir, mock_templates):
        """Test creating gateway with memory artifact service"""
        cli_options = {
            "namespace": "dev/namespace",
            "gateway_id": "mem-gw-01",
            "artifact_service_type": "memory",
            "artifact_service_scope": "namespace",
        }
        
        success, message = create_gateway_files(
            gateway_name_input="MemoryGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is True
        
        config_content = (project_dir / "configs" / "gateways" / "memory_gateway_config.yaml").read_text()
        assert 'type: "memory"' in config_content
        assert "artifact_scope: namespace" in config_content
    
    def test_create_gateway_files_gcs_artifact_service(self, project_dir, mock_templates):
        """Test creating gateway with GCS artifact service"""
        cli_options = {
            "namespace": "cloud/namespace",
            "gateway_id": "gcs-gw-01",
            "artifact_service_type": "gcs",
            "artifact_service_scope": "custom",
        }
        
        success, message = create_gateway_files(
            gateway_name_input="GcsGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is True
        
        config_content = (project_dir / "configs" / "gateways" / "gcs_gateway_config.yaml").read_text()
        assert 'type: "gcs"' in config_content
        assert "artifact_scope: custom" in config_content
    
    def test_create_gateway_files_custom_system_purpose(self, project_dir, mock_templates):
        """Test creating gateway with custom system purpose"""
        custom_purpose = "This is a custom system purpose\nwith multiple lines"
        cli_options = {
            "namespace": "test/namespace",
            "gateway_id": "custom-gw-01",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
            "system_purpose": custom_purpose,
        }
        
        success, message = create_gateway_files(
            gateway_name_input="CustomGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is True
        
        config_content = (project_dir / "configs" / "gateways" / "custom_gateway_config.yaml").read_text()
        assert "This is a custom system purpose" in config_content
    
    def test_create_gateway_files_custom_response_format(self, project_dir, mock_templates):
        """Test creating gateway with custom response format"""
        custom_format = "Custom response format\nwith formatting rules"
        cli_options = {
            "namespace": "test/namespace",
            "gateway_id": "format-gw-01",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
            "response_format": custom_format,
        }
        
        success, message = create_gateway_files(
            gateway_name_input="FormatGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is True
        
        config_content = (project_dir / "configs" / "gateways" / "format_gateway_config.yaml").read_text()
        assert "Custom response format" in config_content


class TestNameFormatting:
    """Tests for various gateway name formats"""
    
    @pytest.mark.parametrize("input_name,expected_snake,expected_pascal,expected_kebab,expected_upper", [
        ("myGateway", "my_gateway", "MyGateway", "my-gateway", "MY_GATEWAY"),
        ("my-gateway", "my_gateway", "MyGateway", "my-gateway", "MY_GATEWAY"),
        ("my_gateway", "my_gateway", "MyGateway", "my-gateway", "MY_GATEWAY"),
        ("MyGateway", "my_gateway", "MyGateway", "my-gateway", "MY_GATEWAY"),
        ("MY_GATEWAY", "my_gateway", "MyGateway", "my-gateway", "MY_GATEWAY"),
        ("my gateway", "my_gateway", "MyGateway", "my-gateway", "MY_GATEWAY"),
        ("APIGateway", "api_gateway", "ApiGateway", "api-gateway", "API_GATEWAY"),
        ("HTTPSGateway", "https_gateway", "HttpsGateway", "https-gateway", "HTTPS_GATEWAY"),
    ])
    def test_name_formatting_variations(self, project_dir, mock_templates, input_name, 
                                       expected_snake, expected_pascal, expected_kebab, expected_upper):
        """Test that various name formats are correctly converted"""
        cli_options = {
            "namespace": "test/namespace",
            "gateway_id": f"{expected_kebab}-gw-01",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
        }
        
        success, message = create_gateway_files(
            gateway_name_input=input_name,
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is True
        
        # Verify snake_case in file paths
        assert (project_dir / "configs" / "gateways" / f"{expected_snake}_config.yaml").exists()
        assert (project_dir / "src" / expected_snake / "app.py").exists()
        
        # Verify PascalCase in app.py
        app_content = (project_dir / "src" / expected_snake / "app.py").read_text()
        assert expected_pascal in app_content
        
        # Verify kebab-case in component.py
        component_content = (project_dir / "src" / expected_snake / "component.py").read_text()
        assert expected_kebab in component_content


class TestOverwriteConfirmation:
    """Tests for overwrite confirmation behavior"""
    
    def test_overwrite_existing_gateway_confirmed(self, project_dir, mock_templates, mocker):
        """Test overwriting existing gateway when user confirms"""
        # Create existing gateway
        existing_dir = project_dir / "src" / "existing_gateway"
        existing_dir.mkdir(parents=True)
        (existing_dir / "app.py").write_text("old content")
        
        # Mock click.confirm to return True and click.edit to avoid editor
        mocker.patch("cli.commands.add_cmd.gateway_cmd.click.confirm", return_value=True)
        mocker.patch("cli.commands.add_cmd.gateway_cmd.click.edit", side_effect=[
            GATEWAY_DEFAULTS["system_purpose"],
            GATEWAY_DEFAULTS["response_format"]
        ])
        
        cli_options = {
            "namespace": "test/namespace",
            "gateway_id": "existing-gw-01",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
        }
        
        success, message = create_gateway_files(
            gateway_name_input="ExistingGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=False
        )
        
        assert success is True
        assert "Gateway 'existing_gateway' skeleton created successfully" in message
    
    def test_overwrite_existing_gateway_cancelled(self, project_dir, mock_templates, mocker):
        """Test cancelling overwrite of existing gateway"""
        # Create existing gateway
        existing_dir = project_dir / "src" / "existing_gateway"
        existing_dir.mkdir(parents=True)
        (existing_dir / "app.py").write_text("old content")
        
        # Mock click.confirm to return False (cancels after prompts)
        mocker.patch("cli.commands.add_cmd.gateway_cmd.click.confirm", return_value=False)
        
        # Provide system_purpose and response_format to avoid editor prompts
        cli_options = {
            "namespace": "test/namespace",
            "gateway_id": "existing-gw-01",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
            "system_purpose": "Test purpose",
            "response_format": "Test format",
        }
        
        success, message = create_gateway_files(
            gateway_name_input="ExistingGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=False
        )
        
        assert success is False
        assert "Operation cancelled" in message
        
        # Verify old content is preserved
        assert (existing_dir / "app.py").read_text() == "old content"
    
    def test_overwrite_skip_mode_no_prompt(self, project_dir, mock_templates):
        """Test that skip mode doesn't prompt for overwrite confirmation"""
        # Create existing gateway
        existing_dir = project_dir / "src" / "skip_gateway"
        existing_dir.mkdir(parents=True)
        (existing_dir / "app.py").write_text("old content")
        
        cli_options = {
            "namespace": "test/namespace",
            "gateway_id": "skip-gw-01",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
        }
        
        success, message = create_gateway_files(
            gateway_name_input="SkipGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        # In skip mode, it should overwrite without prompting
        assert success is True


class TestErrorHandling:
    """Tests for error handling scenarios"""
    
    def test_missing_template_file(self, project_dir, mocker):
        """Test error handling when template file is missing"""
        mocker.patch(
            "cli.commands.add_cmd.gateway_cmd.load_template",
            side_effect=FileNotFoundError("Template file not found")
        )
        
        cli_options = {
            "namespace": "test/namespace",
            "gateway_id": "error-gw-01",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
        }
        
        success, message = create_gateway_files(
            gateway_name_input="ErrorGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is False
        assert "Template file not found" in message
    
    def test_unexpected_exception(self, project_dir, mock_templates, mocker):
        """Test handling of unexpected exceptions"""
        # Mock Path.mkdir to raise an unexpected exception
        mocker.patch.object(
            Path,
            "mkdir",
            side_effect=RuntimeError("Unexpected error")
        )
        
        cli_options = {
            "namespace": "test/namespace",
            "gateway_id": "unexpected-gw-01",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
        }
        
        success, message = create_gateway_files(
            gateway_name_input="UnexpectedGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is False
        assert "unexpected error" in message.lower()


class TestInteractiveMode:
    """Tests for interactive mode with user prompts"""
    
    def test_interactive_mode_with_prompts(self, project_dir, mock_templates, mocker):
        """Test interactive mode prompts for missing options"""
        # Mock user inputs
        mocker.patch("cli.utils.ask_question", side_effect=[
            "interactive/namespace",  # namespace
            "interactive-gw-01",      # gateway_id
            USE_DEFAULT_SHARED_ARTIFACT,  # artifact_service_type
        ])
        mocker.patch("click.edit", side_effect=[
            "Custom system purpose",  # system_purpose
            "Custom response format",  # response_format
        ])
        
        cli_options = {}
        
        success, message = create_gateway_files(
            gateway_name_input="InteractiveGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=False
        )
        
        assert success is True
        
        config_content = (project_dir / "configs" / "gateways" / "interactive_gateway_config.yaml").read_text()
        assert "namespace: interactive/namespace" in config_content
        assert "gateway_id: interactive-gw-01" in config_content
        assert "Custom system purpose" in config_content
        assert "Custom response format" in config_content
    
    def test_interactive_mode_editor_cancelled(self, project_dir, mock_templates, mocker):
        """Test interactive mode when editor is cancelled (returns None)"""
        mocker.patch("cli.utils.ask_question", side_effect=[
            "test/namespace",
            "test-gw-01",
            USE_DEFAULT_SHARED_ARTIFACT,
        ])
        # Editor returns None when cancelled
        mocker.patch("click.edit", return_value=None)
        
        cli_options = {}
        
        success, message = create_gateway_files(
            gateway_name_input="EditorCancelGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=False
        )
        
        assert success is True
        
        # Should use defaults when editor is cancelled
        config_content = (project_dir / "configs" / "gateways" / "editor_cancel_gateway_config.yaml").read_text()
        # Check that the key parts of the defaults are present (accounting for indentation)
        assert "AI Chatbot with agentic capabilities" in config_content
        assert "clear, concise, and professionally toned" in config_content
    
    def test_interactive_filesystem_artifact_prompts(self, project_dir, mock_templates, mocker):
        """Test interactive prompts for filesystem artifact service"""
        mocker.patch("cli.utils.ask_question", side_effect=[
            "test/namespace",
            "fs-gw-01",
            "filesystem",  # artifact_service_type
            "/custom/artifact/path",  # artifact_service_base_path
            "app",  # artifact_service_scope
        ])
        mocker.patch("click.edit", side_effect=[
            GATEWAY_DEFAULTS["system_purpose"],
            GATEWAY_DEFAULTS["response_format"],
        ])
        
        cli_options = {}
        
        success, message = create_gateway_files(
            gateway_name_input="FilesystemGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=False
        )
        
        assert success is True
        
        config_content = (project_dir / "configs" / "gateways" / "filesystem_gateway_config.yaml").read_text()
        assert 'type: "filesystem"' in config_content
        assert "artifact_scope: app" in config_content


class TestTemplatePlaceholderReplacement:
    """Tests for template placeholder replacement"""
    
    def test_all_placeholders_replaced(self, project_dir, mock_templates):
        """Test that all placeholders are correctly replaced in templates"""
        cli_options = {
            "namespace": "placeholder/test",
            "gateway_id": "placeholder-gw-01",
            "artifact_service_type": USE_DEFAULT_SHARED_ARTIFACT,
            "system_purpose": "Test system purpose",
            "response_format": "Test response format",
        }
        
        success, message = create_gateway_files(
            gateway_name_input="PlaceholderTest",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is True
        
        # Check config file
        config_content = (project_dir / "configs" / "gateways" / "placeholder_test_config.yaml").read_text()
        assert "__APP_CONFIG_NAMESPACE__" not in config_content
        assert "__GATEWAY_ID__" not in config_content
        assert "__ARTIFACT_SERVICE__" not in config_content
        assert "__SYSTEM_PURPOSE__" not in config_content
        assert "__RESPONSE_FORMAT__" not in config_content
        assert "placeholder/test" in config_content
        assert "placeholder-gw-01" in config_content
        
        # Check app.py
        app_content = (project_dir / "src" / "placeholder_test" / "app.py").read_text()
        assert "__GATEWAY_NAME_PASCAL_CASE__" not in app_content
        assert "__GATEWAY_NAME_SNAKE_CASE__" not in app_content
        assert "PlaceholderTest" in app_content
        assert "placeholder_test" in app_content
        
        # Check component.py
        component_content = (project_dir / "src" / "placeholder_test" / "component.py").read_text()
        assert "__GATEWAY_NAME_PASCAL_CASE__" not in component_content
        assert "__GATEWAY_NAME_KEBAB_CASE__" not in component_content
        assert "PlaceholderTest" in component_content
        assert "placeholder-test" in component_content
    
    def test_artifact_base_path_with_env_var(self, project_dir, mock_templates):
        """Test artifact base path with environment variable"""
        cli_options = {
            "namespace": "env/test",
            "gateway_id": "env-gw-01",
            "artifact_service_type": "filesystem",
            "artifact_service_base_path": "${ARTIFACT_BASE_PATH}/custom",
            "artifact_service_scope": "namespace",
        }
        
        success, message = create_gateway_files(
            gateway_name_input="EnvVarGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is True
        
        config_content = (project_dir / "configs" / "gateways" / "env_var_gateway_config.yaml").read_text()
        # Should preserve the env var format
        assert "${ARTIFACT_BASE_PATH}/custom" in config_content
    
    def test_artifact_base_path_without_env_var(self, project_dir, mock_templates):
        """Test artifact base path without environment variable gets wrapped"""
        cli_options = {
            "namespace": "plain/test",
            "gateway_id": "plain-gw-01",
            "artifact_service_type": "filesystem",
            "artifact_service_base_path": "/plain/path",
            "artifact_service_scope": "app",
        }
        
        success, message = create_gateway_files(
            gateway_name_input="PlainPathGateway",
            cli_options=cli_options,
            project_root=project_dir,
            skip_interactive=True
        )
        
        assert success is True
        
        config_content = (project_dir / "configs" / "gateways" / "plain_path_gateway_config.yaml").read_text()
        # Should wrap plain path with ARTIFACT_BASE_PATH env var
        assert "ARTIFACT_BASE_PATH" in config_content
        