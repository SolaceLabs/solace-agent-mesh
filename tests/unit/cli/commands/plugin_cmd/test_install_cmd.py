
"""
Unit tests for cli/commands/plugin_cmd/install_cmd.py

Tests the plugin installation command including:
- Local path installation
- Git repository installation (with/without branch)
- Official registry installation
- Pip installation fallback
- Error handling (missing dependencies, invalid paths, network errors)
- Module name extraction from various sources
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner

from cli.commands.plugin_cmd.install_cmd import (
    _check_command_exists,
    _get_plugin_name_from_source_pyproject,
    _run_install,
    install_plugin,
    install_plugin_cmd,
)


class TestCheckCommandExists:
    """Tests for _check_command_exists function"""
    
    def test_command_exists(self, mocker):
        """Test when command exists on system"""
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        assert _check_command_exists("git") is True
    
    def test_command_not_exists(self, mocker):
        """Test when command does not exist on system"""
        mocker.patch("shutil.which", return_value=None)
        assert _check_command_exists("nonexistent") is False


class TestGetPluginNameFromSourcePyproject:
    """Tests for _get_plugin_name_from_source_pyproject function"""
    
    def test_valid_pyproject_toml(self, tmp_path):
        """Test reading plugin name from valid pyproject.toml"""
        pyproject_content = """
[project]
name = "test-plugin"
version = "0.1.0"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        result = _get_plugin_name_from_source_pyproject(tmp_path)
        assert result == "test_plugin"
    
    def test_pyproject_with_underscores(self, tmp_path):
        """Test plugin name normalization from hyphens to underscores"""
        pyproject_content = """
[project]
name = "my-test-plugin"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        result = _get_plugin_name_from_source_pyproject(tmp_path)
        assert result == "my_test_plugin"
    
    def test_missing_pyproject_toml(self, tmp_path):
        """Test when pyproject.toml doesn't exist"""
        result = _get_plugin_name_from_source_pyproject(tmp_path)
        assert result is None
    
    def test_missing_project_name(self, tmp_path):
        """Test when project.name is missing from pyproject.toml"""
        pyproject_content = """
[project]
version = "0.1.0"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        result = _get_plugin_name_from_source_pyproject(tmp_path)
        assert result is None
    
    def test_invalid_toml_format(self, tmp_path):
        """Test when pyproject.toml has invalid format"""
        (tmp_path / "pyproject.toml").write_text("invalid toml content [[[")
        result = _get_plugin_name_from_source_pyproject(tmp_path)
        assert result is None


class TestRunInstall:
    """Tests for _run_install function"""
    
    def test_successful_install(self, mocker):
        """Test successful installation"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Successfully installed",
            stderr=""
        )
        
        result = _run_install("pip3 install {package}", "test-plugin", "test source")
        assert result is None
        mock_run.assert_called_once()
    
    def test_failed_install(self, mocker):
        """Test failed installation"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: Package not found"
        )
        
        result = _run_install("pip3 install {package}", "test-plugin", "test source")
        assert result is not None
        assert "failed" in result.lower()
    
    def test_command_not_found(self, mocker):
        """Test when install command is not found"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = FileNotFoundError()
        
        result = _run_install("pip3 install {package}", "test-plugin", "test source")
        assert result is not None
        assert "not found" in result.lower()
    
    def test_unexpected_error(self, mocker):
        """Test unexpected error during installation"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = Exception("Unexpected error")
        
        result = _run_install("pip3 install {package}", "test-plugin", "test source")
        assert result is not None
        assert "unexpected error" in result.lower()


class TestInstallPlugin:
    """Tests for install_plugin function"""
    
    def test_install_from_local_directory(self, tmp_path, mocker):
        """Test installing plugin from local directory"""
        # Create mock plugin directory
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        pyproject_content = """
[project]
name = "test-plugin"
"""
        (plugin_dir / "pyproject.toml").write_text(pyproject_content)
        
        # Mock subprocess and get_module_path
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        mock_get_module = mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path")
        mock_get_module.return_value = str(plugin_dir)
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        module_name, plugin_path = install_plugin(str(plugin_dir))
        
        assert module_name == "test_plugin"
        assert plugin_path == Path(str(plugin_dir))
        mock_run.assert_called_once()
    
    def test_install_from_git_url(self, tmp_path, mocker):
        """Test installing plugin from Git URL"""
        git_url = "https://github.com/user/repo.git"
        
        # Mock git clone
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        # Mock git command check
        mocker.patch("cli.commands.plugin_cmd.install_cmd._check_command_exists", return_value=True)
        
        # Mock pyproject.toml reading in temp directory
        def mock_get_plugin_name(path):
            return "test_plugin"
        mocker.patch(
            "cli.commands.plugin_cmd.install_cmd._get_plugin_name_from_source_pyproject",
            side_effect=mock_get_plugin_name
        )
        
        # Mock get_module_path and Path.exists
        mock_get_module = mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path")
        mock_get_module.return_value = "/fake/path/test_plugin"
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        mocker.patch("pathlib.Path.exists", return_value=True)
        
        module_name, plugin_path = install_plugin(git_url)
        
        assert module_name == "test_plugin"
        assert plugin_path == Path("/fake/path/test_plugin")
    
    def test_install_from_git_plus_url(self, mocker):
        """Test installing plugin from git+ URL"""
        git_url = "git+https://github.com/user/repo.git#subdirectory=plugin_name"
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        mock_get_module = mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path")
        mock_get_module.return_value = "/fake/path/plugin_name"
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        mocker.patch("pathlib.Path.exists", return_value=True)
        
        module_name, plugin_path = install_plugin(git_url)
        
        assert module_name == "plugin_name"
        assert plugin_path == Path("/fake/path/plugin_name")
    
    def test_install_from_wheel_file(self, tmp_path, mocker):
        """Test installing plugin from wheel file"""
        wheel_file = tmp_path / "test_plugin-0.1.0-py3-none-any.whl"
        wheel_file.touch()
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        mock_get_module = mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path")
        mock_get_module.return_value = "/fake/path/test_plugin"
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        mocker.patch("pathlib.Path.exists", return_value=True)
        
        module_name, plugin_path = install_plugin(str(wheel_file))
        
        assert module_name == "test_plugin"
        assert plugin_path == Path("/fake/path/test_plugin")
    
    def test_install_from_official_registry(self, mocker):
        """Test installing plugin from official registry"""
        plugin_name = "official-plugin"
        official_url = "git+https://github.com/official/plugins.git#subdirectory=official-plugin"
        
        mocker.patch(
            "cli.commands.plugin_cmd.install_cmd.get_official_plugin_url",
            return_value=official_url
        )
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        mock_get_module = mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path")
        mock_get_module.return_value = "/fake/path/official_plugin"
        mocker.patch("pathlib.Path.exists", return_value=True)
        
        module_name, plugin_path = install_plugin(plugin_name)
        
        assert module_name == "official_plugin"
    
    def test_install_invalid_installer_command(self, mocker):
        """Test with invalid installer command (missing placeholder)"""
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        with pytest.raises(click.exceptions.Abort):
            install_plugin("test-plugin", installer_command="pip3 install")
    
    def test_install_git_without_git_command(self, mocker):
        """Test Git installation when git command is not available"""
        git_url = "https://github.com/user/repo.git"
        
        mocker.patch("cli.commands.plugin_cmd.install_cmd._check_command_exists", return_value=False)
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        with pytest.raises(click.exceptions.Abort):
            install_plugin(git_url)
    
    def test_install_git_clone_failure(self, mocker):
        """Test when git clone fails"""
        git_url = "https://github.com/user/repo.git"
        
        mocker.patch("cli.commands.plugin_cmd.install_cmd._check_command_exists", return_value=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="Clone failed")
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        with pytest.raises(click.exceptions.Abort):
            install_plugin(git_url)
    
    def test_install_local_missing_pyproject(self, tmp_path, mocker):
        """Test local installation when pyproject.toml is missing"""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        with pytest.raises(click.exceptions.Abort):
            install_plugin(str(plugin_dir))
    
    def test_install_invalid_local_path(self, tmp_path, mocker):
        """Test with invalid local path (file instead of directory)"""
        invalid_file = tmp_path / "not_a_plugin.txt"
        invalid_file.touch()
        
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        with pytest.raises(click.exceptions.Abort):
            install_plugin(str(invalid_file))
    
    def test_install_module_not_found_after_install(self, mocker):
        """Test when module cannot be imported after installation"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        mock_get_module = mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path")
        mock_get_module.side_effect = ImportError("Module not found")
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        with pytest.raises(click.exceptions.Abort):
            install_plugin("test-plugin")
    
    def test_install_custom_installer_command(self, tmp_path, mocker):
        """Test with custom installer command"""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        pyproject_content = """
[project]
name = "test-plugin"
"""
        (plugin_dir / "pyproject.toml").write_text(pyproject_content)
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        mock_get_module = mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path")
        mock_get_module.return_value = str(plugin_dir)
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        module_name, plugin_path = install_plugin(
            str(plugin_dir),
            installer_command="poetry add {package}"
        )
        
        assert module_name == "test_plugin"
        # Verify custom command was used
        call_args = mock_run.call_args[0][0]
        assert "poetry" in call_args
class TestInstallPluginCmd:
    """Tests for install_plugin_cmd CLI command"""
    
    def test_cli_install_success(self, tmp_path, mocker):
        """Test successful CLI installation"""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        pyproject_content = """
[project]
name = "test-plugin"
"""
        (plugin_dir / "pyproject.toml").write_text(pyproject_content)
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        mock_get_module = mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path")
        mock_get_module.return_value = str(plugin_dir)
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        runner = CliRunner()
        result = runner.invoke(install_plugin_cmd, [str(plugin_dir)])
        
        assert result.exit_code == 0
        assert "installed and available" in result.output.lower()
    
    def test_cli_install_with_custom_command(self, tmp_path, mocker):
        """Test CLI installation with custom install command"""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        pyproject_content = """
[project]
name = "test-plugin"
"""
        (plugin_dir / "pyproject.toml").write_text(pyproject_content)
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        mock_get_module = mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path")
        mock_get_module.return_value = str(plugin_dir)
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        runner = CliRunner()
        result = runner.invoke(
            install_plugin_cmd,
            [str(plugin_dir), "--install-command", "poetry add {package}"]
        )
        
        assert result.exit_code == 0
    
    def test_cli_install_failure(self, mocker):
        """Test CLI installation failure"""
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        runner = CliRunner()
        result = runner.invoke(install_plugin_cmd, ["nonexistent-plugin"])
        
        assert result.exit_code == 1
    
    def test_cli_install_from_env_variable(self, tmp_path, mocker, monkeypatch):
        """Test CLI installation using SAM_PLUGIN_INSTALL_COMMAND env variable"""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        pyproject_content = """
[project]
name = "test-plugin"
"""
        (plugin_dir / "pyproject.toml").write_text(pyproject_content)
        
        monkeypatch.setenv("SAM_PLUGIN_INSTALL_COMMAND", "custom-install {package}")
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        mock_get_module = mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path")
        mock_get_module.return_value = str(plugin_dir)
        mocker.patch("cli.commands.plugin_cmd.install_cmd.get_official_plugin_url", return_value=None)
        
        runner = CliRunner()
        result = runner.invoke(install_plugin_cmd, [str(plugin_dir)])
        
        assert result.exit_code == 0
    
    