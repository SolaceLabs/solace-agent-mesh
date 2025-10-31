"""
Unit tests for cli/commands/plugin_cmd/create_cmd.py

Tests the plugin creation command including:
- Plugin creation for different types (agent, gateway, custom)
- Interactive vs non-interactive modes
- Template file generation
- Name formatting and placeholder replacement
- Error handling (missing templates, invalid plugin types)
"""

from pathlib import Path
from click.testing import CliRunner

from cli.commands.plugin_cmd.create_cmd import (
    ensure_directory_exists,
    replace_placeholders,
    load_plugin_type_config_template,
    setup_plugin_type_src,
    create_plugin_cmd,
    PLUGIN_TYPES,
    DEFAULT_PLUGIN_VERSION,
)


class TestEnsureDirectoryExists:
    """Tests for ensure_directory_exists function"""
    
    def test_create_new_directory(self, tmp_path):
        """Test creating a new directory"""
        new_dir = tmp_path / "new_directory"
        ensure_directory_exists(new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()
    
    def test_existing_directory(self, tmp_path):
        """Test with existing directory (should not raise error)"""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()
        ensure_directory_exists(existing_dir)
        assert existing_dir.exists()
    
    def test_nested_directory_creation(self, tmp_path):
        """Test creating nested directories"""
        nested_dir = tmp_path / "level1" / "level2" / "level3"
        ensure_directory_exists(nested_dir)
        assert nested_dir.exists()


class TestReplacePlaceholders:
    """Tests for replace_placeholders function"""
    
    def test_single_placeholder(self):
        """Test replacing a single placeholder"""
        content = "Hello __NAME__!"
        replacements = {"__NAME__": "World"}
        result = replace_placeholders(content, replacements)
        assert result == "Hello World!"
    
    def test_multiple_placeholders(self):
        """Test replacing multiple placeholders"""
        content = "__GREETING__ __NAME__, you are __AGE__ years old"
        replacements = {
            "__GREETING__": "Hello",
            "__NAME__": "Alice",
            "__AGE__": "25"
        }
        result = replace_placeholders(content, replacements)
        assert result == "Hello Alice, you are 25 years old"
    
    def test_no_placeholders(self):
        """Test content with no placeholders"""
        content = "No placeholders here"
        replacements = {"__NAME__": "World"}
        result = replace_placeholders(content, replacements)
        assert result == "No placeholders here"
    
    def test_repeated_placeholder(self):
        """Test replacing repeated placeholders"""
        content = "__NAME__ and __NAME__ are friends"
        replacements = {"__NAME__": "Bob"}
        result = replace_placeholders(content, replacements)
        assert result == "Bob and Bob are friends"


class TestLoadPluginTypeConfigTemplate:
    """Tests for load_plugin_type_config_template function"""
    
    def test_load_agent_template(self, mock_templates):
        """Test loading agent plugin template"""
        replacements = {"__PLUGIN_META_DATA_TYPE__": "agent"}
        result = load_plugin_type_config_template("agent", replacements)
        assert "agent" in result
    
    def test_load_gateway_template(self, mock_templates):
        """Test loading gateway plugin template"""
        replacements = {"__PLUGIN_META_DATA_TYPE__": "gateway"}
        result = load_plugin_type_config_template("gateway", replacements)
        assert result is not None
    
    def test_load_custom_template(self, mock_templates):
        """Test loading custom plugin template"""
        replacements = {"__PLUGIN_META_DATA_TYPE__": "custom"}
        result = load_plugin_type_config_template("custom", replacements)
        assert result is not None


class TestSetupPluginTypeSrc:
    """Tests for setup_plugin_type_src function"""
    
    def test_setup_agent_src(self, tmp_path, mock_templates):
        """Test setting up agent plugin source directory"""
        src_path = tmp_path / "src"
        src_path.mkdir()
        
        replacements = {
            "__PLUGIN_SNAKE_CASE_NAME__": "test_plugin",
            "__PLUGIN_PASCAL_CASE_NAME__": "TestPlugin",
        }
        
        setup_plugin_type_src("agent", src_path, replacements)
        
        assert (src_path / "__init__.py").exists()
        assert (src_path / "tools.py").exists()
    
    def test_setup_gateway_src(self, tmp_path, mock_templates):
        """Test setting up gateway plugin source directory"""
        src_path = tmp_path / "src"
        src_path.mkdir()
        
        replacements = {
            "__PLUGIN_SNAKE_CASE_NAME__": "test_gateway",
            "__PLUGIN_PASCAL_CASE_NAME__": "TestGateway",
            "__PLUGIN_UPPER_SNAKE_CASE_NAME__": "TEST_GATEWAY",
            "__PLUGIN_KEBAB_CASE_NAME__": "test-gateway",
        }
        
        setup_plugin_type_src("gateway", src_path, replacements)
        
        assert (src_path / "__init__.py").exists()
        assert (src_path / "app.py").exists()
        assert (src_path / "component.py").exists()
    
    def test_setup_custom_src(self, tmp_path, mock_templates):
        """Test setting up custom plugin source directory"""
        src_path = tmp_path / "src"
        src_path.mkdir()
        
        replacements = {
            "__PLUGIN_PASCAL_CASE_NAME__": "TestCustom",
        }
        
        setup_plugin_type_src("custom", src_path, replacements)
        
        assert (src_path / "__init__.py").exists()
        assert (src_path / "app.py").exists()


class TestCreatePluginCmd:
    """Tests for create_plugin_cmd CLI command"""
    
    def test_create_agent_plugin_skip_mode(self, temp_project_dir, mock_templates, mock_official_registry):
        """Test creating agent plugin in skip mode"""
        runner = CliRunner()
        result = runner.invoke(
            create_plugin_cmd,
            [
                "test-agent",
                "--type", "agent",
                "--author-name", "Test Author",
                "--author-email", "test@example.com",
                "--description", "Test agent plugin",
                "--version", "1.0.0",
                "--skip"
            ]
        )
        
        assert result.exit_code == 0
        assert "created successfully" in result.output.lower()
        
        # Verify directory structure
        plugin_dir = Path("test-agent")
        assert plugin_dir.exists()
        assert (plugin_dir / "config.yaml").exists()
        assert (plugin_dir / "pyproject.toml").exists()
        assert (plugin_dir / "README.md").exists()
        assert (plugin_dir / "src" / "test_agent" / "__init__.py").exists()
        assert (plugin_dir / "src" / "test_agent" / "tools.py").exists()
    
    def test_create_gateway_plugin_skip_mode(self, temp_project_dir, mock_templates, mock_official_registry):
        """Test creating gateway plugin in skip mode"""
        runner = CliRunner()
        result = runner.invoke(
            create_plugin_cmd,
            [
                "test-gateway",
                "--type", "gateway",
                "--skip"
            ]
        )
        
        assert result.exit_code == 0
        
        plugin_dir = Path("test-gateway")
        assert plugin_dir.exists()
        assert (plugin_dir / "src" / "test_gateway" / "app.py").exists()
        assert (plugin_dir / "src" / "test_gateway" / "component.py").exists()
    
    def test_create_custom_plugin_skip_mode(self, temp_project_dir, mock_templates, mock_official_registry):
        """Test creating custom plugin in skip mode"""
        runner = CliRunner()
        result = runner.invoke(
            create_plugin_cmd,
            [
                "test-custom",
                "--type", "custom",
                "--skip"
            ]
        )
        
        assert result.exit_code == 0
        
        plugin_dir = Path("test-custom")
        assert plugin_dir.exists()
        assert (plugin_dir / "src" / "test_custom" / "app.py").exists()
    
    def test_create_plugin_interactive_mode(self, temp_project_dir, mock_templates, mock_official_registry):
        """Test creating plugin in interactive mode"""
        runner = CliRunner()
        result = runner.invoke(
            create_plugin_cmd,
            ["test-interactive"],
            input="agent\nJohn Doe\njohn@example.com\nTest description\n0.1.0\n"
        )
        
        assert result.exit_code == 0
        assert Path("test-interactive").exists()
    
    def test_create_plugin_with_defaults(self, temp_project_dir, mock_templates, mock_official_registry):
        """Test creating plugin with default values"""
        runner = CliRunner()
        result = runner.invoke(
            create_plugin_cmd,
            ["my-plugin", "--skip"]
        )
        
        assert result.exit_code == 0
        
        # Verify default values were used
        plugin_dir = Path("my-plugin")
        pyproject = (plugin_dir / "pyproject.toml").read_text()
        assert DEFAULT_PLUGIN_VERSION in pyproject
    
    def test_create_plugin_invalid_type(self, temp_project_dir, mock_templates, mock_official_registry):
        """Test creating plugin with invalid type"""
        runner = CliRunner()
        result = runner.invoke(
            create_plugin_cmd,
            [
                "test-plugin",
                "--type", "invalid_type",
                "--skip"
            ]
        )
        
        assert result.exit_code == 1
        assert "invalid plugin type" in result.output.lower()
    
    def test_create_plugin_name_formatting(self, temp_project_dir, mock_templates, mock_official_registry):
        """Test plugin name formatting (kebab-case, snake_case, etc.)"""
        runner = CliRunner()
        result = runner.invoke(
            create_plugin_cmd,
            ["My Test Plugin", "--skip"]
        )
        
        assert result.exit_code == 0
        
        # Should create directory with kebab-case name
        assert Path("my-test-plugin").exists()
        
        # Source directory should use snake_case
        assert Path("my-test-plugin/src/my_test_plugin").exists()
    
    def test_create_plugin_official_name_conflict(self, temp_project_dir, mock_templates, mocker):
        """Test creating plugin with name that conflicts with official plugin"""
        mocker.patch(
            "cli.commands.plugin_cmd.create_cmd.is_official_plugin",
            return_value=True
        )
        
        runner = CliRunner()
        result = runner.invoke(
            create_plugin_cmd,
            ["official-plugin", "--skip"]
        )
        
        assert result.exit_code == 1
        assert "conflicts with an official plugin" in result.output.lower()
    
    def test_create_plugin_placeholder_replacement(self, temp_project_dir, mock_templates, mock_official_registry):
        """Test that placeholders are correctly replaced in generated files"""
        runner = CliRunner()
        result = runner.invoke(
            create_plugin_cmd,
            [
                "my-awesome-plugin",
                "--type", "agent",
                "--author-name", "Jane Doe",
                "--author-email", "jane@example.com",
                "--description", "An awesome plugin",
                "--version", "2.0.0",
                "--skip"
            ]
        )
        
        assert result.exit_code == 0
        
        plugin_dir = Path("my-awesome-plugin")
        
        # Check pyproject.toml
        pyproject_content = (plugin_dir / "pyproject.toml").read_text()
        assert "my-awesome-plugin" in pyproject_content
        assert "2.0.0" in pyproject_content
        assert "An awesome plugin" in pyproject_content
        
        # Check config.yaml
        config_content = (plugin_dir / "config.yaml").read_text()
        assert "agent" in config_content
    
    def test_create_plugin_all_types(self, temp_project_dir, mock_templates, mock_official_registry):
        """Test creating plugins of all supported types"""
        runner = CliRunner()
        
        for plugin_type in PLUGIN_TYPES:
            result = runner.invoke(
                create_plugin_cmd,
                [
                    f"test-{plugin_type}",
                    "--type", plugin_type,
                    "--skip"
                ]
            )
            
            assert result.exit_code == 0
            assert Path(f"test-{plugin_type}").exists()
    
    def test_create_plugin_with_special_characters(self, temp_project_dir, mock_templates, mock_official_registry):
        """Test creating plugin with special characters in name"""
        runner = CliRunner()
        result = runner.invoke(
            create_plugin_cmd,
            ["test_plugin-v2", "--skip"]
        )
        
        assert result.exit_code == 0
        # Should normalize to kebab-case
        assert Path("test-plugin-v2").exists()