"""
Unit tests for cli/main.py

Tests the main CLI entry point including:
- CLI group creation and configuration
- Version option functionality
- Command registration
- Help text display
- Main function entry point
"""
from click.testing import CliRunner

from cli.main import cli, main
from cli import __version__


class TestCLIGroup:
    """Tests for the CLI group configuration"""

    def test_cli_group_exists(self):
        """Test that the CLI group is created correctly"""
        assert cli is not None
        assert hasattr(cli, 'name')
        assert cli.name == 'cli'

    def test_cli_group_is_group(self):
        """Test that cli is a Click group"""
        assert hasattr(cli, 'commands')
        assert callable(cli)

    def test_cli_help_option_names(self):
        """Test that custom help option names are configured"""
        runner = CliRunner()
        
        # Test -h flag
        result = runner.invoke(cli, ['-h'])
        assert result.exit_code == 0
        assert 'Solace CLI Application' in result.output
        
        # Test --help flag
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Solace CLI Application' in result.output

    def test_cli_docstring(self):
        """Test that the CLI has the correct docstring"""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Solace CLI Application' in result.output


class TestVersionOption:
    """Tests for the version option"""

    def test_version_flag_short(self):
        """Test that -v flag displays the version"""
        runner = CliRunner()
        result = runner.invoke(cli, ['-v'])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_flag_long(self):
        """Test that --version flag displays the version"""
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_output_format(self):
        """Test that version output contains expected format"""
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        # Click formats version as "cli, version X.Y.Z"
        assert 'version' in result.output.lower()
        assert __version__ in result.output


class TestCommandRegistration:
    """Tests for command registration"""

    def test_init_command_registered(self):
        """Test that init command is registered"""
        assert 'init' in cli.commands
        assert cli.commands['init'] is not None

    def test_run_command_registered(self):
        """Test that run command is registered"""
        assert 'run' in cli.commands
        assert cli.commands['run'] is not None

    def test_add_command_registered(self):
        """Test that add command is registered"""
        assert 'add' in cli.commands
        assert cli.commands['add'] is not None

    def test_plugin_command_registered(self):
        """Test that plugin command is registered"""
        assert 'plugin' in cli.commands
        assert cli.commands['plugin'] is not None

    def test_eval_cmd_command_registered(self):
        """Test that eval_cmd command is registered"""
        assert 'eval' in cli.commands
        assert cli.commands['eval'] is not None

    def test_docs_command_registered(self):
        """Test that docs command is registered"""
        assert 'docs' in cli.commands
        assert cli.commands['docs'] is not None

    def test_all_expected_commands_registered(self):
        """Test that all expected commands are registered"""
        expected_commands = ['init', 'run', 'add', 'plugin', 'eval', 'docs']
        for cmd in expected_commands:
            assert cmd in cli.commands, f"Command '{cmd}' not registered"

    def test_command_count(self):
        """Test that the expected number of commands are registered"""
        # Should have exactly 6 commands
        assert len(cli.commands) == 6


class TestHelpText:
    """Tests for help text display"""

    def test_help_shows_all_commands(self):
        """Test that help text shows all registered commands"""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        
        # Check that all commands appear in help
        expected_commands = ['init', 'run', 'add', 'plugin', 'eval', 'docs']
        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not in help output"

    def test_help_shows_version_option(self):
        """Test that help text shows version option"""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert '--version' in result.output or '-v' in result.output

    def test_help_exit_code(self):
        """Test that help command exits with code 0"""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0

    def test_short_help_exit_code(self):
        """Test that -h flag exits with code 0"""
        runner = CliRunner()
        result = runner.invoke(cli, ['-h'])
        assert result.exit_code == 0


class TestMainFunction:
    """Tests for the main() entry point"""

    def test_main_function_exists(self):
        """Test that main function exists"""
        assert main is not None
        assert callable(main)

    def test_main_calls_cli(self, mocker):
        """Test that main() calls cli()"""
        # Mock the cli function to prevent actual execution
        mock_cli = mocker.patch('cli.main.cli')
        
        # Call main
        main()
        
        # Verify cli was called
        mock_cli.assert_called_once()

    def test_main_with_help_flag(self, mocker):
        """Test main function with help flag through sys.argv"""
        # Mock sys.argv to simulate command line arguments
        mocker.patch('sys.argv', ['cli', '--help'])
        
        # Mock cli to capture the call
        mock_cli = mocker.patch('cli.main.cli')
        
        # Call main
        main()
        
        # Verify cli was called
        mock_cli.assert_called_once()


class TestCLIInvocation:
    """Tests for CLI invocation scenarios"""

    def test_cli_no_arguments(self):
        """Test CLI invocation with no arguments shows help"""
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert 'Solace CLI Application' in result.output

    def test_cli_invalid_command(self):
        """Test CLI with invalid command shows error"""
        runner = CliRunner()
        result = runner.invoke(cli, ['invalid-command'])
        assert result.exit_code != 0
        assert 'Error' in result.output or 'No such command' in result.output

    def test_cli_with_context_settings(self):
        """Test that CLI respects context settings"""
        # Verify help option names are configured
        assert cli.context_settings is not None
        assert 'help_option_names' in cli.context_settings
        assert '-h' in cli.context_settings['help_option_names']
        assert '--help' in cli.context_settings['help_option_names']


class TestCLIIntegration:
    """Integration tests for CLI functionality"""

    def test_version_and_help_mutually_exclusive(self):
        """Test that version flag takes precedence"""
        runner = CliRunner()
        result = runner.invoke(cli, ['--version', '--help'])
        assert result.exit_code == 0
        # Version should be shown (Click handles this)
        assert __version__ in result.output

    def test_cli_command_help(self):
        """Test that individual commands have help"""
        runner = CliRunner()
        
        # Test a few commands to ensure they have help
        commands_to_test = ['init', 'run', 'add']
        for cmd in commands_to_test:
            result = runner.invoke(cli, [cmd, '--help'])
            assert result.exit_code == 0
            assert 'Usage:' in result.output or 'Options:' in result.output