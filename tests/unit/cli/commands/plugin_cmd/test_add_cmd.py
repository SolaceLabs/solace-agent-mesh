"""
Unit tests for cli/commands/plugin_cmd/add_cmd.py

Tests the plugin component addition command including:
- Component instance creation from installed plugin
- Plugin installation check and auto-install
- config.yaml template reading and processing
- Error handling (plugin not found, invalid config)
"""

from pathlib import Path
from click.testing import CliRunner

from cli.commands.plugin_cmd.add_cmd import (
    ensure_directory_exists,
    _get_plugin_type_from_pyproject,
    add_plugin_component_cmd,
)


class TestEnsureDirectoryExists:
    """Tests for ensure_directory_exists function"""
    
    def test_create_new_directory(self, tmp_path):
        """Test creating a new directory"""
        new_dir = tmp_path / "new_dir"
        ensure_directory_exists(new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()
    
    def test_existing_directory(self, tmp_path):
        """Test with existing directory"""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()
        ensure_directory_exists(existing_dir)
        assert existing_dir.exists()
    
    def test_nested_directory(self, tmp_path):
        """Test creating nested directories"""
        nested = tmp_path / "a" / "b" / "c"
        ensure_directory_exists(nested)
        assert nested.exists()


class TestGetPluginTypeFromPyproject:
    """Tests for _get_plugin_type_from_pyproject function"""
    
    def test_get_agent_type(self, tmp_path):
        """Test getting agent plugin type"""
        pyproject_content = """
[project]
name = "test-plugin"

[tool.test_plugin.metadata]
type = "agent"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        result = _get_plugin_type_from_pyproject(tmp_path)
        assert result == "agent"
    
    def test_get_gateway_type(self, tmp_path):
        """Test getting gateway plugin type"""
        pyproject_content = """
[project]
name = "test-gateway"

[tool.test_gateway.metadata]
type = "gateway"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        result = _get_plugin_type_from_pyproject(tmp_path)
        assert result == "gateway"
    
    def test_get_custom_type(self, tmp_path):
        """Test getting custom plugin type"""
        pyproject_content = """
[project]
name = "test-custom"

[tool.test_custom.metadata]
type = "custom"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        result = _get_plugin_type_from_pyproject(tmp_path)
        assert result == "custom"
    
    def test_missing_pyproject(self, tmp_path):
        """Test when pyproject.toml doesn't exist"""
        result = _get_plugin_type_from_pyproject(tmp_path)
        assert result is None
    
    def test_missing_type_field(self, tmp_path):
        """Test when type field is missing"""
        pyproject_content = """
[project]
name = "test-plugin"

[tool.test_plugin.metadata]
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        result = _get_plugin_type_from_pyproject(tmp_path)
        assert result is None
    
    def test_invalid_toml(self, tmp_path):
        """Test with invalid TOML format"""
        (tmp_path / "pyproject.toml").write_text("invalid [[[")
        result = _get_plugin_type_from_pyproject(tmp_path)
        assert result is None
    
    def test_name_with_hyphens(self, tmp_path):
        """Test plugin name normalization (hyphens to underscores)"""
        pyproject_content = """
[project]
name = "my-test-plugin"

[tool.my_test_plugin.metadata]
type = "agent"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        result = _get_plugin_type_from_pyproject(tmp_path)
        assert result == "agent"


class TestAddPluginComponentCmd:
    """Tests for add_plugin_component_cmd CLI command"""
    
    def test_add_agent_component(self, temp_project_dir, mock_plugin_path, mocker):
        """Test adding an agent component"""
        # Mock install_plugin to return the mock plugin path
        mocker.patch(
            "cli.commands.plugin_cmd.add_cmd.install_plugin",
            return_value=("mock_plugin", mock_plugin_path)
        )
        
        runner = CliRunner()
        result = runner.invoke(
            add_plugin_component_cmd,
            ["my-agent", "--plugin", "mock-plugin"]
        )
        
        assert result.exit_code == 0
        assert "created successfully" in result.output.lower()
        
        # Verify component config was created in correct directory
        config_file = Path("configs/agents/my-agent.yaml")
        assert config_file.exists()
        
        # Verify placeholder replacement
        config_content = config_file.read_text()
        assert "my-agent" in config_content or "my_agent" in config_content
    
    def test_add_gateway_component(self, temp_project_dir, mocker):
        """Test adding a gateway component"""
        # Create mock gateway plugin
        gateway_plugin_path = temp_project_dir / "gateway_plugin"
        gateway_plugin_path.mkdir()
        
        pyproject_content = """
[project]
name = "gateway-plugin"

[tool.gateway_plugin.metadata]
type = "gateway"
"""
        (gateway_plugin_path / "pyproject.toml").write_text(pyproject_content)
        
        config_content = """
namespace: __COMPONENT_KEBAB_CASE_NAME__
gateway_id: __COMPONENT_SNAKE_CASE_NAME__
"""
        (gateway_plugin_path / "config.yaml").write_text(config_content)
        
        mocker.patch(
            "cli.commands.plugin_cmd.add_cmd.install_plugin",
            return_value=("gateway_plugin", gateway_plugin_path)
        )
        
        runner = CliRunner()
        result = runner.invoke(
            add_plugin_component_cmd,
            ["my-gateway", "--plugin", "gateway-plugin"]
        )
        
        assert result.exit_code == 0
        
        # Verify component config was created in gateways directory
        config_file = Path("configs/gateways/my-gateway.yaml")
        assert config_file.exists()
    
    def test_add_custom_component(self, temp_project_dir, mocker):
        """Test adding a custom component"""
        # Create mock custom plugin
        custom_plugin_path = temp_project_dir / "custom_plugin"
        custom_plugin_path.mkdir()
        
        pyproject_content = """
[project]
name = "custom-plugin"

[tool.custom_plugin.metadata]
type = "custom"
"""
        (custom_plugin_path / "pyproject.toml").write_text(pyproject_content)
        
        config_content = """
component: __COMPONENT_PASCAL_CASE_NAME__
"""
        (custom_plugin_path / "config.yaml").write_text(config_content)
        
        mocker.patch(
            "cli.commands.plugin_cmd.add_cmd.install_plugin",
            return_value=("custom_plugin", custom_plugin_path)
        )
        
        runner = CliRunner()
        result = runner.invoke(
            add_plugin_component_cmd,
            ["my-custom", "--plugin", "custom-plugin"]
        )
        
        assert result.exit_code == 0
        
        # Custom plugins go to configs/plugins directory
        config_file = Path("configs/plugins/my-custom.yaml")
        assert config_file.exists()
    
    def test_add_component_with_custom_install_command(self, temp_project_dir, mock_plugin_path, mocker):
        """Test adding component with custom install command"""
        mock_install = mocker.patch(
            "cli.commands.plugin_cmd.add_cmd.install_plugin",
            return_value=("mock_plugin", mock_plugin_path)
        )
        
        runner = CliRunner()
        result = runner.invoke(
            add_plugin_component_cmd,
            [
                "my-component",
                "--plugin", "mock-plugin",
                "--install-command", "poetry add {package}"
            ]
        )
        
        assert result.exit_code == 0
        
        # Verify install_plugin was called with custom command
        mock_install.assert_called_once()
        assert mock_install.call_args[0][1] == "poetry add {package}"
    
    def test_add_component_missing_pyproject(self, temp_project_dir, mocker):
        """Test adding component when plugin has no pyproject.toml"""
        plugin_path = temp_project_dir / "bad_plugin"
        plugin_path.mkdir()
        (plugin_path / "config.yaml").write_text("test: value")
        
        mocker.patch(
            "cli.commands.plugin_cmd.add_cmd.install_plugin",
            return_value=("bad_plugin", plugin_path)
        )
        
        runner = CliRunner()
        result = runner.invoke(
            add_plugin_component_cmd,
            ["my-component", "--plugin", "bad-plugin"]
        )
        
        assert result.exit_code == 1
        assert "pyproject.toml not found" in result.output.lower()
    
    def test_add_component_missing_config(self, temp_project_dir, mocker):
        """Test adding component when plugin has no config.yaml"""
        plugin_path = temp_project_dir / "bad_plugin"
        plugin_path.mkdir()
        
        pyproject_content = """
[project]
name = "bad-plugin"

[tool.bad_plugin.metadata]
type = "agent"
"""
        (plugin_path / "pyproject.toml").write_text(pyproject_content)
        
        mocker.patch(
            "cli.commands.plugin_cmd.add_cmd.install_plugin",
            return_value=("bad_plugin", plugin_path)
        )
        
        runner = CliRunner()
        result = runner.invoke(
            add_plugin_component_cmd,
            ["my-component", "--plugin", "bad-plugin"]
        )
        
        assert result.exit_code == 1
        assert "config.yaml not found" in result.output.lower()
    
    def test_add_component_install_failure(self, temp_project_dir, mocker):
        """Test adding component when plugin installation fails"""
        mocker.patch(
            "cli.commands.plugin_cmd.add_cmd.install_plugin",
            return_value=(None, None)
        )
        
        runner = CliRunner()
        result = runner.invoke(
            add_plugin_component_cmd,
            ["my-component", "--plugin", "nonexistent-plugin"]
        )
        
        assert result.exit_code == 1
    
    def test_add_component_placeholder_replacement(self, temp_project_dir, mock_plugin_path, mocker):
        """Test that all placeholders are correctly replaced"""
        # Update mock plugin config with all placeholders
        config_content = """
snake_case: __COMPONENT_SNAKE_CASE_NAME__
upper_snake: __COMPONENT_UPPER_SNAKE_CASE_NAME__
kebab_case: __COMPONENT_KEBAB_CASE_NAME__
pascal_case: __COMPONENT_PASCAL_CASE_NAME__
spaced: __COMPONENT_SPACED_NAME__
spaced_cap: __COMPONENT_SPACED_CAPITALIZED_NAME__
"""
        (mock_plugin_path / "config.yaml").write_text(config_content)
        
        mocker.patch(
            "cli.commands.plugin_cmd.add_cmd.install_plugin",
            return_value=("mock_plugin", mock_plugin_path)
        )
        
        runner = CliRunner()
        result = runner.invoke(
            add_plugin_component_cmd,
            ["my-test-component", "--plugin", "mock-plugin"]
        )
        
        assert result.exit_code == 0
        
        config_file = Path("configs/agents/my-test-component.yaml")
        config_content = config_file.read_text()
        
        # Verify all placeholders were replaced
        assert "__COMPONENT_" not in config_content
        assert "my_test_component" in config_content  # snake_case
        assert "my-test-component" in config_content  # kebab-case
    
    def test_add_component_from_local_path(self, temp_project_dir, mock_plugin_path, mocker):
        """Test adding component from local plugin path"""
        mocker.patch(
            "cli.commands.plugin_cmd.add_cmd.install_plugin",
            return_value=("mock_plugin", mock_plugin_path)
        )
        
        runner = CliRunner()
        result = runner.invoke(
            add_plugin_component_cmd,
            ["my-component", "--plugin", str(mock_plugin_path)]
        )
        
        assert result.exit_code == 0
    
    def test_add_component_from_git_url(self, temp_project_dir, mock_plugin_path, mocker):
        """Test adding component from Git URL"""
        mocker.patch(
            "cli.commands.plugin_cmd.add_cmd.install_plugin",
            return_value=("mock_plugin", mock_plugin_path)
        )
        
        runner = CliRunner()
        result = runner.invoke(
            add_plugin_component_cmd,
            ["my-component", "--plugin", "https://github.com/user/plugin.git"]
        )
        
        assert result.exit_code == 0