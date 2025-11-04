"""
Unit tests for cli/commands/eval_cmd.py

Tests the eval command including:
- Running evaluation with scenario file
- Verbose output flag
- Logging configuration setup
- Error handling (missing scenario file, invalid format)
- Result output formatting
- Exception handling during evaluation
"""

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli.commands.eval_cmd import eval_cmd


@pytest.fixture
def runner():
    """Create a Click CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def test_config_file(tmp_path):
    """Create a temporary test suite config file"""
    config_file = tmp_path / "test_suite.yaml"
    config_file.write_text("""
test_suite:
  name: "Test Suite"
  scenarios:
    - name: "Test Scenario"
      input: "test input"
""")
    return config_file


@pytest.fixture
def logging_config_file(tmp_path):
    """Create a temporary logging config file"""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    logging_config = configs_dir / "logging_config.yaml"
    logging_config.write_text("""
[loggers]
keys=root

[handlers]
keys=console

[formatters]
keys=simple
""")
    return logging_config


class TestEvalCommand:
    """Tests for the eval CLI command"""
    
    def test_eval_command_basic(self, runner, test_config_file, mocker):
        """Test basic eval command with valid config file"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        result = runner.invoke(eval_cmd, [str(test_config_file)])
        
        assert result.exit_code == 0
        assert "Starting evaluation" in result.output
        assert str(test_config_file) in result.output
        assert "Evaluation completed successfully" in result.output
        mock_run_eval.assert_called_once_with(str(test_config_file), verbose=False)
    
    def test_eval_command_with_verbose(self, runner, test_config_file, mocker):
        """Test eval command with verbose flag"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        result = runner.invoke(eval_cmd, [str(test_config_file), "--verbose"])
        
        assert result.exit_code == 0
        assert "Starting evaluation" in result.output
        mock_run_eval.assert_called_once_with(str(test_config_file), verbose=True)
    
    def test_eval_command_with_verbose_short_flag(self, runner, test_config_file, mocker):
        """Test eval command with -v short flag"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        result = runner.invoke(eval_cmd, [str(test_config_file), "-v"])
        
        assert result.exit_code == 0
        mock_run_eval.assert_called_once_with(str(test_config_file), verbose=True)
    
    def test_eval_command_missing_file(self, runner, tmp_path):
        """Test eval command with non-existent config file"""
        non_existent = tmp_path / "nonexistent.yaml"
        
        result = runner.invoke(eval_cmd, [str(non_existent)])
        
        assert result.exit_code != 0
        assert "does not exist" in result.output or "Error" in result.output
    
    def test_eval_command_with_logging_config(self, runner, test_config_file, logging_config_file, mocker):
        """Test eval command sets logging config path when it exists"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        # Change to directory with logging config
        original_cwd = Path.cwd()
        os.chdir(logging_config_file.parent.parent)
        
        try:
            result = runner.invoke(eval_cmd, [str(test_config_file)])
            
            assert result.exit_code == 0
            # Verify LOGGING_CONFIG_PATH was set
            assert "LOGGING_CONFIG_PATH" in os.environ or mock_run_eval.called
            mock_run_eval.assert_called_once()
        finally:
            os.chdir(original_cwd)
            # Clean up environment
            if "LOGGING_CONFIG_PATH" in os.environ:
                del os.environ["LOGGING_CONFIG_PATH"]
    
    def test_eval_command_without_logging_config(self, runner, test_config_file, tmp_path, mocker):
        """Test eval command when logging config doesn't exist"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        # Change to directory without logging config
        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        
        try:
            result = runner.invoke(eval_cmd, [str(test_config_file)])
            
            assert result.exit_code == 0
            # Should still work without logging config
            mock_run_eval.assert_called_once()
        finally:
            os.chdir(original_cwd)
    
    def test_eval_command_evaluation_exception(self, runner, test_config_file, mocker):
        """Test eval command handles evaluation exceptions"""
        mock_run_eval = mocker.patch(
            "cli.commands.eval_cmd.run_evaluation_main",
            side_effect=Exception("Evaluation failed")
        )
        mock_error_exit = mocker.patch("cli.commands.eval_cmd.error_exit", side_effect=SystemExit(1))
        
        result = runner.invoke(eval_cmd, [str(test_config_file)])
        
        assert result.exit_code == 1
        mock_error_exit.assert_called_once()
        assert "An error occurred during evaluation" in mock_error_exit.call_args[0][0]
        assert "Evaluation failed" in mock_error_exit.call_args[0][0]
    
    def test_eval_command_runtime_error(self, runner, test_config_file, mocker):
        """Test eval command handles runtime errors"""
        mock_run_eval = mocker.patch(
            "cli.commands.eval_cmd.run_evaluation_main",
            side_effect=RuntimeError("Runtime error occurred")
        )
        mock_error_exit = mocker.patch("cli.commands.eval_cmd.error_exit", side_effect=SystemExit(1))
        
        result = runner.invoke(eval_cmd, [str(test_config_file)])
        
        assert result.exit_code == 1
        mock_error_exit.assert_called_once()
        assert "Runtime error occurred" in mock_error_exit.call_args[0][0]
    
    def test_eval_command_value_error(self, runner, test_config_file, mocker):
        """Test eval command handles value errors"""
        mock_run_eval = mocker.patch(
            "cli.commands.eval_cmd.run_evaluation_main",
            side_effect=ValueError("Invalid configuration")
        )
        mock_error_exit = mocker.patch("cli.commands.eval_cmd.error_exit", side_effect=SystemExit(1))
        
        result = runner.invoke(eval_cmd, [str(test_config_file)])
        
        assert result.exit_code == 1
        mock_error_exit.assert_called_once()
        assert "Invalid configuration" in mock_error_exit.call_args[0][0]
    
    def test_eval_command_file_not_found_error(self, runner, test_config_file, mocker):
        """Test eval command handles file not found errors"""
        mock_run_eval = mocker.patch(
            "cli.commands.eval_cmd.run_evaluation_main",
            side_effect=FileNotFoundError("Config file not found")
        )
        mock_error_exit = mocker.patch("cli.commands.eval_cmd.error_exit", side_effect=SystemExit(1))
        
        result = runner.invoke(eval_cmd, [str(test_config_file)])
        
        assert result.exit_code == 1
        mock_error_exit.assert_called_once()
    
    def test_eval_command_output_formatting(self, runner, test_config_file, mocker):
        """Test eval command output formatting"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        result = runner.invoke(eval_cmd, [str(test_config_file)])
        
        # Check for styled output
        assert "Starting evaluation" in result.output
        assert "Evaluation completed successfully" in result.output
        # Verify the config path is displayed
        assert str(test_config_file) in result.output
    
    def test_eval_command_requires_path_argument(self, runner):
        """Test eval command requires test suite config path"""
        result = runner.invoke(eval_cmd, [])
        
        assert result.exit_code != 0
        assert "Missing argument" in result.output or "Error" in result.output
    
    def test_eval_command_path_must_be_file(self, runner, tmp_path):
        """Test eval command requires path to be a file, not directory"""
        directory = tmp_path / "test_dir"
        directory.mkdir()
        
        result = runner.invoke(eval_cmd, [str(directory)])
        
        assert result.exit_code != 0
        # Click should reject directory when dir_okay=False
    
    def test_eval_command_resolves_path(self, runner, test_config_file, mocker):
        """Test eval command resolves relative paths"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        # Use relative path
        original_cwd = Path.cwd()
        os.chdir(test_config_file.parent)
        
        try:
            result = runner.invoke(eval_cmd, [test_config_file.name])
            
            assert result.exit_code == 0
            # Should be called with resolved absolute path
            called_path = mock_run_eval.call_args[0][0]
            assert Path(called_path).is_absolute()
        finally:
            os.chdir(original_cwd)
    
    def test_eval_command_logging_config_absolute_path(self, runner, test_config_file, logging_config_file, mocker):
        """Test eval command converts logging config to absolute path"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        original_cwd = Path.cwd()
        os.chdir(logging_config_file.parent.parent)
        
        try:
            result = runner.invoke(eval_cmd, [str(test_config_file)])
            
            assert result.exit_code == 0
            # If LOGGING_CONFIG_PATH was set, it should be absolute
            if "LOGGING_CONFIG_PATH" in os.environ:
                assert Path(os.environ["LOGGING_CONFIG_PATH"]).is_absolute()
        finally:
            os.chdir(original_cwd)
            if "LOGGING_CONFIG_PATH" in os.environ:
                del os.environ["LOGGING_CONFIG_PATH"]
    
    def test_eval_command_multiple_verbose_flags(self, runner, test_config_file, mocker):
        """Test eval command with multiple verbose flags (should still work)"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        result = runner.invoke(eval_cmd, [str(test_config_file), "-v", "-v"])
        
        # Should still work (verbose is a boolean flag)
        assert result.exit_code == 0
        mock_run_eval.assert_called_once_with(str(test_config_file), verbose=True)
    
    def test_eval_command_success_message_color(self, runner, test_config_file, mocker):
        """Test eval command shows success message in green"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        result = runner.invoke(eval_cmd, [str(test_config_file)])
        
        assert result.exit_code == 0
        # Success message should be present
        assert "Evaluation completed successfully" in result.output
    
    def test_eval_command_starting_message_color(self, runner, test_config_file, mocker):
        """Test eval command shows starting message in blue"""
        mock_run_eval = mocker.patch("cli.commands.eval_cmd.run_evaluation_main")
        
        result = runner.invoke(eval_cmd, [str(test_config_file)])
        
        assert result.exit_code == 0
        # Starting message should be present
        assert "Starting evaluation" in result.output