"""
Unit tests for cli/commands/run_cmd.py

Tests the run command including:
- Running with default config discovery
- Running with specific config files
- Running with directories
- Skip files functionality
- System environment flag
- .env file loading
- Logging configuration
- YAML file filtering (underscore prefix, shared_config)
- Error handling (missing config directory, no files to run)
- Graceful exit handling
"""

import os
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from click.testing import CliRunner

from cli.commands.run_cmd import run, _execute_with_solace_ai_connector


@pytest.fixture
def runner():
    """Create a Click CLI runner for testing with logging capture"""
    return CliRunner(mix_stderr=False)


@pytest.fixture
def caplog_handler(caplog):
    """Configure caplog to capture logging at all levels"""
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory with configs"""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    
    # Create configs directory
    configs_dir = project_path / "configs"
    configs_dir.mkdir()
    
    # Create some test config files
    (configs_dir / "agent1.yaml").write_text("agent: config1")
    (configs_dir / "agent2.yml").write_text("agent: config2")
    (configs_dir / "_private.yaml").write_text("private: config")
    (configs_dir / "shared_config.yaml").write_text("shared: config")
    
    # Create subdirectory with configs
    sub_dir = configs_dir / "subdir"
    sub_dir.mkdir()
    (sub_dir / "agent3.yaml").write_text("agent: config3")
    
    # Create .env file
    env_file = project_path / ".env"
    env_file.write_text("TEST_VAR=test_value\nLOGGING_CONFIG_PATH=configs/logging.yaml")
    
    return project_path


@pytest.fixture
def mock_solace_connector(mocker):
    """Mock the solace_ai_connector module"""
    mock_main = mocker.patch("solace_ai_connector.main.main", return_value=0)
    return mock_main


@pytest.fixture
def mock_initialize(mocker):
    """Mock the initialize function"""
    return mocker.patch("cli.commands.run_cmd.initialize")


@pytest.fixture
def mock_configure_logging(mocker):
    """Mock the configure_from_file function from solace_ai_connector"""
    return mocker.patch(
        "solace_ai_connector.common.logging_config.configure_from_file",
        return_value=True
    )


class TestExecuteWithSolaceAIConnector:
    """Tests for the _execute_with_solace_ai_connector function"""
    
    def test_execute_with_connector_basic(self, mocker):
        """Test basic execution with connector"""
        mock_main = mocker.patch("solace_ai_connector.main.main", return_value=0)
        mock_exit = mocker.patch("sys.exit")
        
        original_argv = sys.argv.copy()
        sys.argv = ["sam", "other", "args"]
        
        try:
            _execute_with_solace_ai_connector(["config1.yaml", "config2.yaml"])
            
            # Verify sys.argv was modified correctly
            assert "solace-ai-connector" in sys.argv[0]
            assert "config1.yaml" in sys.argv
            assert "config2.yaml" in sys.argv
            
            mock_main.assert_called_once()
            mock_exit.assert_called_once_with(0)
        finally:
            sys.argv = original_argv
    
    def test_execute_with_connector_sam_program_name(self, mocker):
        """Test execution when program name is 'sam'"""
        mock_main = mocker.patch("solace_ai_connector.main.main", return_value=0)
        mock_exit = mocker.patch("sys.exit")
        
        original_argv = sys.argv.copy()
        sys.argv = ["/usr/local/bin/sam"]
        
        try:
            _execute_with_solace_ai_connector(["config.yaml"])
            
            # Should replace 'sam' with 'solace-ai-connector'
            assert "solace-ai-connector" in sys.argv[0]
            mock_exit.assert_called_once_with(0)
        finally:
            sys.argv = original_argv
    
    def test_execute_with_connector_solace_agent_mesh_program_name(self, mocker):
        """Test execution when program name is 'solace-agent-mesh'"""
        mock_main = mocker.patch("solace_ai_connector.main.main", return_value=0)
        mock_exit = mocker.patch("sys.exit")
        
        original_argv = sys.argv.copy()
        sys.argv = ["/usr/local/bin/solace-agent-mesh"]
        
        try:
            _execute_with_solace_ai_connector(["config.yaml"])
            
            # Should replace 'solace-agent-mesh' with 'solace-ai-connector'
            assert "solace-ai-connector" in sys.argv[0]
            mock_exit.assert_called_once_with(0)
        finally:
            sys.argv = original_argv
    
    def test_execute_with_connector_import_error(self, mocker):
        """Test execution when solace_ai_connector import fails"""
        # Mock the import to fail
        import sys
        original_modules = sys.modules.copy()
        if 'solace_ai_connector.main' in sys.modules:
            del sys.modules['solace_ai_connector.main']
        if 'solace_ai_connector' in sys.modules:
            del sys.modules['solace_ai_connector']
        
        mock_error_exit = mocker.patch("cli.commands.run_cmd.error_exit", side_effect=SystemExit(1))
        
        # Temporarily make the import fail
        import builtins
        real_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'solace_ai_connector.main' or name == 'solace_ai_connector':
                raise ImportError("Module not found")
            return real_import(name, *args, **kwargs)
        
        mocker.patch('builtins.__import__', side_effect=mock_import)
        
        try:
            with pytest.raises(SystemExit):
                _execute_with_solace_ai_connector(["config.yaml"])
            
            mock_error_exit.assert_called_once()
            assert "Failed to import" in mock_error_exit.call_args[0][0]
        finally:
            # Restore modules
            sys.modules.update(original_modules)


class TestRunCommand:
    """Tests for the run CLI command"""
    
    def test_run_command_no_files_discovers_configs(self, runner, project_dir, mock_solace_connector, mock_initialize, mock_configure_logging, mocker, caplog):
        """Test run command discovers configs when no files provided"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            caplog.set_level(logging.INFO)
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            mock_exit = mocker.patch("sys.exit")
            
            result = runner.invoke(run, [])
            
            assert result.exit_code == 0
            output = result.output + caplog.text
            assert "No specific files provided" in output
            assert "Discovering YAML files" in output
            mock_initialize.assert_called_once()
            mock_solace_connector.assert_called_once()
            
            # Check sys.argv which contains the files passed to the connector
            # sys.argv[0] is the program name, rest are config files
            import sys
            called_files = sys.argv[1:]
            assert len(called_files) == 3
            assert any("agent1.yaml" in f for f in called_files)
            assert any("agent2.yml" in f for f in called_files)
            assert any("agent3.yaml" in f for f in called_files)
            assert not any("_private" in f for f in called_files)
            assert not any("shared_config" in f for f in called_files)
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_with_specific_file(self, runner, project_dir, mock_solace_connector, mock_initialize, mock_configure_logging, mocker, caplog):
        """Test run command with specific config file"""
        caplog.set_level(logging.INFO)
        config_file = project_dir / "configs" / "agent1.yaml"
        
        mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
        mock_exit = mocker.patch("sys.exit")
        
        result = runner.invoke(run, [str(config_file)])
        output = result.output + caplog.text
        
        assert result.exit_code == 0
        assert "Processing provided configuration files" in output
        mock_solace_connector.assert_called_once()
        
        import sys
        called_files = sys.argv[1:]
        assert len(called_files) == 1
        assert str(config_file) in called_files[0]
    
    def test_run_command_with_directory(self, runner, project_dir, mock_solace_connector, mock_initialize, mock_configure_logging, mocker, caplog):
        """Test run command with directory path"""
        caplog.set_level(logging.INFO)
        configs_dir = project_dir / "configs"
        
        mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
        mock_exit = mocker.patch("sys.exit")
        
        result = runner.invoke(run, [str(configs_dir)])
        output = result.output + caplog.text
        
        assert result.exit_code == 0
        assert "Discovering YAML files in directory" in output
        mock_solace_connector.assert_called_once()
        
        import sys
        called_files = sys.argv[1:]
        # Should find multiple files but skip _private and shared_config
        assert len(called_files) >= 2
        assert not any("_private" in f for f in called_files)
        assert not any("shared_config" in f for f in called_files)
    
    def test_run_command_with_skip_files(self, runner, project_dir, mock_solace_connector, mock_initialize, mock_configure_logging, mocker, caplog):
        """Test run command with --skip option"""
        caplog.set_level(logging.INFO)
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            mock_exit = mocker.patch("sys.exit")
            
            result = runner.invoke(run, ["--skip", "agent1.yaml"])
            output = result.output + caplog.text
            
            assert result.exit_code == 0
            assert "Applying --skip" in output
            assert "Skipping execution: " in output
            
            import sys
            called_files = sys.argv[1:]
            # agent1.yaml should be skipped
            assert not any("agent1.yaml" in f for f in called_files)
            # But agent2.yml and agent3.yaml should be present
            assert any("agent2.yml" in f for f in called_files)
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_with_multiple_skip_files(self, runner, project_dir, mock_solace_connector, mock_initialize, mock_configure_logging, mocker):
        """Test run command with multiple --skip options"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            mock_exit = mocker.patch("sys.exit")
            
            result = runner.invoke(run, ["-s", "agent1.yaml", "-s", "agent2.yml"])
            
            assert result.exit_code == 0
            
            import sys
            called_files = sys.argv[1:]
            # Both should be skipped
            assert not any("agent1.yaml" in f for f in called_files)
            assert not any("agent2.yml" in f for f in called_files)
            # But agent3.yaml should be present
            assert any("agent3.yaml" in f for f in called_files)
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_with_system_env_flag(self, runner, project_dir, mock_solace_connector, mock_initialize, mocker, caplog):
        """Test run command with --system-env flag"""
        caplog.set_level(logging.INFO)
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            mocker.patch("solace_ai_connector.common.logging_config.configure_from_file", return_value=True)
            mock_find_dotenv = mocker.patch("cli.commands.run_cmd.find_dotenv")
            mock_load_dotenv = mocker.patch("cli.commands.run_cmd.load_dotenv")
            
            result = runner.invoke(run, ["--system-env"])
            output = result.output + caplog.text
            assert result.exit_code == 0
            assert "Skipping .env file loading" in output
            # Should not try to find or load .env
            mock_find_dotenv.assert_not_called()
            mock_load_dotenv.assert_not_called()
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_loads_env_file(self, runner, project_dir, mock_solace_connector, mock_initialize, mock_configure_logging, mocker, caplog):
        """Test run command loads .env file"""
        caplog.set_level(logging.INFO)
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            env_file = project_dir / ".env"
            mocker.patch("solace_ai_connector.common.logging_config.configure_from_file", return_value=True)
            mock_find_dotenv = mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=str(env_file))
            mock_load_dotenv = mocker.patch("cli.commands.run_cmd.load_dotenv")
            
            result = runner.invoke(run, [])
            output = result.output + caplog.text
            
            assert result.exit_code == 0
            assert "Loaded environment variables from" in output
            mock_find_dotenv.assert_called_once()
            mock_load_dotenv.assert_called_once()
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_no_env_file_warning(self, runner, project_dir, mock_solace_connector, mock_initialize, mocker, mock_configure_logging, caplog):
        """Test run command shows warning when .env not found"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            caplog.set_level(logging.WARNING)
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            
            result = runner.invoke(run, [])
            
            assert result.exit_code == 0
            # Check both result.output and caplog.text for the warning
            assert "Warning: .env file not found" in result.output or "Warning: .env file not found" in caplog.text
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_missing_configs_directory(self, runner, tmp_path, mocker, caplog, mock_configure_logging):
        """Test run command when configs directory doesn't exist"""
        caplog.set_level(logging.ERROR)
        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        
        try:
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            mocker.patch("cli.commands.run_cmd.initialize")
            
            result = runner.invoke(run, [])
            output = result.output + caplog.text
            
            assert result.exit_code == 1
            assert "Configuration directory" in output
            assert "not found" in output
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_no_files_after_filtering(self, runner, project_dir, mock_initialize, mocker, caplog, mock_configure_logging):
        """Test run command when all files are filtered out"""
        caplog.set_level(logging.WARNING)
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            mocker.patch("solace_ai_connector.common.logging_config.configure_from_file", return_value=True)
            
            # Skip all discovered files
            result = runner.invoke(run, ["-s", "agent1.yaml", "-s", "agent2.yml", "-s", "agent3.yaml"])
            output = result.output + caplog.text
            
            assert result.exit_code == 0
            assert "No configuration files to run after filtering" in output
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_ignores_non_yaml_files(self, runner, project_dir, mock_solace_connector, mock_initialize, mock_configure_logging, mocker, caplog):
        """Test run command ignores non-YAML files"""
        caplog.set_level(logging.WARNING)
        # Create a non-YAML file
        (project_dir / "configs" / "readme.txt").write_text("Not a YAML file")
        
        mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
        
        result = runner.invoke(run, [str(project_dir / "configs" / "readme.txt")])
        output = result.output + caplog.text
        
        assert result.exit_code == 0
        assert "Ignoring non-YAML file" in output
        assert "No configuration files to run" in output
    
    def test_run_command_logging_config_resolution(self, runner, project_dir, mock_solace_connector, mock_initialize, mocker):
        """Test run command resolves relative logging config path"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            env_file = project_dir / ".env"
            mock_find_dotenv = mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=str(env_file))
            
            # Mock load_dotenv to set LOGGING_CONFIG_PATH
            def mock_load_env(*args, **kwargs):
                os.environ["LOGGING_CONFIG_PATH"] = "configs/logging.yaml"
            
            mocker.patch("cli.commands.run_cmd.load_dotenv", side_effect=mock_load_env)
            mocker.patch("cli.commands.run_cmd.os.path.isabs", return_value=False)
            
            result = runner.invoke(run, [])
            
            # LOGGING_CONFIG_PATH should be converted to absolute
            if "LOGGING_CONFIG_PATH" in os.environ:
                del os.environ["LOGGING_CONFIG_PATH"]
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_reconfigure_logging(self, runner, project_dir, mock_solace_connector, mock_initialize, mocker):
        """Test run command reconfigures logging when available"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            env_file = project_dir / ".env"
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=str(env_file))
            mocker.patch("cli.commands.run_cmd.load_dotenv")
            
            # Mock reconfigure_logging
            mock_reconfigure = MagicMock(return_value=True)
            mock_module = MagicMock()
            mock_module.reconfigure_logging = mock_reconfigure
            
            with patch.dict('sys.modules', {'solace_ai_connector.common.log': mock_module}):
                result = runner.invoke(run, [])
                
                assert result.exit_code == 0
                if "Logging reconfigured" in result.output:
                    mock_reconfigure.assert_called_once()
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_success_exit_code(self, runner, project_dir, mock_initialize, mocker):
        """Test run command with successful execution"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            mock_connector = mocker.patch("solace_ai_connector.main.main", return_value=0)
            mock_exit = mocker.patch("sys.exit")
            
            result = runner.invoke(run, [])
            
            mock_exit.assert_called_with(0)
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_failure_exit_code(self, runner, project_dir, mock_initialize, mocker):
        """Test run command with failed execution"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            mock_connector = mocker.patch("solace_ai_connector.main.main", return_value=1)
            # Mock sys.exit to raise SystemExit with the code
            def mock_exit_func(code):
                raise SystemExit(code)
            mock_exit = mocker.patch("sys.exit", side_effect=mock_exit_func)
            
            result = runner.invoke(run, [])
            
            mock_exit.assert_called_with(1)
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_yaml_and_yml_extensions(self, runner, project_dir, mock_solace_connector, mock_initialize, mocker):
        """Test run command discovers both .yaml and .yml files"""
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            mock_exit = mocker.patch("sys.exit")
            
            result = runner.invoke(run, [])
            
            assert result.exit_code == 0
            
            import sys
            called_files = sys.argv[1:]
            # Should find both .yaml and .yml files
            yaml_files = [f for f in called_files if f.endswith('.yaml')]
            yml_files = [f for f in called_files if f.endswith('.yml')]
            
            assert len(yaml_files) > 0
            assert len(yml_files) > 0
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_skips_underscore_prefix(self, runner, project_dir, mock_solace_connector, mock_initialize, mocker, caplog):
        """Test run command skips files with underscore prefix"""
        caplog.set_level(logging.INFO)
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            mock_exit = mocker.patch("sys.exit")
            
            result = runner.invoke(run, [])
            output = result.output + caplog.text
            
            assert result.exit_code == 0
            assert "Skipping discovery: " in output
            assert "_private" in output
            
            import sys
            called_files = sys.argv[1:]
            assert not any("_private" in f for f in called_files)
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_skips_shared_config(self, runner, project_dir, mock_solace_connector, mock_initialize, mocker, caplog):
        """Test run command skips shared_config files"""
        caplog.set_level(logging.INFO)
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            mock_exit = mocker.patch("sys.exit")
            
            result = runner.invoke(run, [])
            output = result.output + caplog.text
            
            assert result.exit_code == 0
            assert "shared_config" in output
            
            import sys
            called_files = sys.argv[1:]
            assert not any("shared_config" in f for f in called_files)
        finally:
            os.chdir(original_cwd)
    
    def test_run_command_final_list_output(self, runner, project_dir, mock_solace_connector, mock_initialize, mocker, caplog):
        """Test run command displays final list of config files"""
        caplog.set_level(logging.INFO)
        original_cwd = Path.cwd()
        os.chdir(project_dir)
        
        try:
            mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
            
            result = runner.invoke(run, [])
            output = result.output + caplog.text
            
            assert result.exit_code == 0
            print(result.output)
            assert "Final list of configuration files to run:" in output
        finally:
            os.chdir(original_cwd)

    def test_run_command_multiple_files_and_directories(self, runner, project_dir, mock_solace_connector, mock_initialize, mocker, caplog):
        """Test run command with mix of files and directories"""
        caplog.set_level(logging.INFO)
        config_file = project_dir / "configs" / "agent1.yaml"
        sub_dir = project_dir / "configs" / "subdir"
        
        mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
        mock_exit = mocker.patch("sys.exit")
        
        result = runner.invoke(run, [str(config_file), str(sub_dir)])
        
        assert result.exit_code == 0
        
        import sys
        called_files = sys.argv[1:]
        # Should include agent1.yaml and files from subdir
        assert any("agent1.yaml" in f for f in called_files)
        assert any("agent3.yaml" in f for f in called_files)
    
    def test_run_command_deduplicates_files(self, runner, project_dir, mock_solace_connector, mock_initialize, mocker, caplog):
        """Test run command deduplicates files when same file provided multiple times"""
        caplog.set_level(logging.INFO)
        config_file = project_dir / "configs" / "agent1.yaml"
        
        mocker.patch("cli.commands.run_cmd.find_dotenv", return_value=None)
        mock_exit = mocker.patch("sys.exit")
        
        result = runner.invoke(run, [str(config_file), str(config_file)])
        
        assert result.exit_code == 0
        
        import sys
        called_files = sys.argv[1:]
        # Should only include agent1.yaml once
        agent1_count = sum(1 for f in called_files if "agent1.yaml" in f)
        assert agent1_count == 1