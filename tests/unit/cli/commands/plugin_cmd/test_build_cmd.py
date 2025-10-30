"""
Unit tests for cli/commands/plugin_cmd/build_cmd.py

Tests the plugin build command including:
- Successful build with python -m build
- Build failures
- Missing build dependencies
- Error handling
"""

from pathlib import Path
from unittest.mock import Mock
from click.testing import CliRunner

from cli.commands.plugin_cmd.build_cmd import build_plugin_cmd


class TestBuildPluginCmd:
    """Tests for build_plugin_cmd CLI command"""
    
    def test_build_success_default_directory(self, temp_project_dir, mocker):
        """Test successful build in current directory"""
        # Create pyproject.toml in current directory
        pyproject_content = """
[project]
name = "test-plugin"
version = "0.1.0"
"""
        Path("pyproject.toml").write_text(pyproject_content)
        
        # Mock subprocess.run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Successfully built test-plugin-0.1.0.tar.gz",
            stderr=""
        )
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [])
        
        assert result.exit_code == 0
        assert "built successfully" in result.output.lower()
        mock_run.assert_called_once()
        
        # Verify correct command was used
        call_args = mock_run.call_args[0][0]
        assert "python" in call_args
        assert "build" in call_args
    
    def test_build_success_specific_directory(self, temp_project_dir, mocker):
        """Test successful build in specified directory"""
        # Create plugin directory
        plugin_dir = Path("my-plugin")
        plugin_dir.mkdir()
        
        pyproject_content = """
[project]
name = "my-plugin"
version = "1.0.0"
"""
        (plugin_dir / "pyproject.toml").write_text(pyproject_content)
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Build successful",
            stderr=""
        )
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [str(plugin_dir)])
        
        assert result.exit_code == 0
        assert "built successfully" in result.output.lower()
    
    def test_build_with_output_artifacts(self, temp_project_dir, mocker):
        """Test build with generated artifacts in dist directory"""
        Path("pyproject.toml").write_text("[project]\nname = 'test'")
        
        # Create dist directory with artifacts
        dist_dir = Path("dist")
        dist_dir.mkdir()
        (dist_dir / "test-0.1.0.tar.gz").touch()
        (dist_dir / "test-0.1.0-py3-none-any.whl").touch()
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [])
        
        assert result.exit_code == 0
        assert "test-0.1.0.tar.gz" in result.output
        assert "test-0.1.0-py3-none-any.whl" in result.output
    
    def test_build_failure(self, temp_project_dir, mocker):
        """Test build failure"""
        Path("pyproject.toml").write_text("[project]\nname = 'test'")
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: Missing dependencies"
        )
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [])
        
        assert result.exit_code == 1
        assert "failed" in result.output.lower()
    
    def test_build_missing_pyproject(self, temp_project_dir, mocker):
        """Test build when pyproject.toml is missing"""
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [])
        
        assert result.exit_code == 1
        assert "pyproject.toml not found" in result.output.lower()
    
    def test_build_python_not_found(self, temp_project_dir, mocker):
        """Test build when Python executable is not found"""
        Path("pyproject.toml").write_text("[project]\nname = 'test'")
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = FileNotFoundError()
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [])
        
        assert result.exit_code == 1
        assert "python executable not found" in result.output.lower()
    
    def test_build_with_warnings(self, temp_project_dir, mocker):
        """Test build with warnings in stderr"""
        Path("pyproject.toml").write_text("[project]\nname = 'test'")
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Build successful",
            stderr="Warning: Deprecated feature used"
        )
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [])
        
        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        assert "deprecated" in result.output.lower()
    
    def test_build_unexpected_error(self, temp_project_dir, mocker):
        """Test build with unexpected error"""
        Path("pyproject.toml").write_text("[project]\nname = 'test'")
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = Exception("Unexpected error occurred")
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [])
        
        assert result.exit_code == 1
        assert "unexpected error" in result.output.lower()
    
    def test_build_preserves_working_directory(self, temp_project_dir, mocker):
        """Test that build preserves original working directory"""
        original_cwd = Path.cwd()
        
        plugin_dir = Path("plugin")
        plugin_dir.mkdir()
        (plugin_dir / "pyproject.toml").write_text("[project]\nname = 'test'")
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [str(plugin_dir)])
        
        # Verify we're back in original directory
        assert Path.cwd() == original_cwd
    
    def test_build_with_stdout_output(self, temp_project_dir, mocker):
        """Test that build output is displayed"""
        Path("pyproject.toml").write_text("[project]\nname = 'test'")
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Building wheel...\nCreating distribution...\nDone!",
            stderr=""
        )
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [])
        
        assert result.exit_code == 0
        assert "building wheel" in result.output.lower()
        assert "done" in result.output.lower()
    
    def test_build_nonexistent_directory(self, temp_project_dir):
        """Test build with nonexistent directory"""
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, ["nonexistent"])
        
        # Click should handle this with path validation
        assert result.exit_code != 0
    
    def test_build_file_instead_of_directory(self, temp_project_dir):
        """Test build with file path instead of directory"""
        # Create a file
        test_file = Path("test.txt")
        test_file.touch()
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [str(test_file)])
        
        # Click should reject file paths
        assert result.exit_code != 0
    
    def test_build_with_complex_pyproject(self, temp_project_dir, mocker):
        """Test build with complex pyproject.toml"""
        pyproject_content = """
[build-system]
requires = ["setuptools>=45", "wheel", "setuptools_scm[toml]>=6.2"]
build-backend = "setuptools.build_meta"

[project]
name = "complex-plugin"
version = "2.0.0"
description = "A complex plugin"
dependencies = [
    "click>=8.0",
    "requests>=2.28"
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "black>=22.0"]
"""
        Path("pyproject.toml").write_text(pyproject_content)
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [])
        
        assert result.exit_code == 0
    
    def test_build_shows_note_about_build_package(self, temp_project_dir, mocker):
        """Test that build command shows note about build package requirement"""
        Path("pyproject.toml").write_text("[project]\nname = 'test'")
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [])
        
        assert "python -m build" in result.output.lower()
        assert "pip install build" in result.output.lower()
    
    def test_build_relative_path(self, temp_project_dir, mocker):
        """Test build with relative path"""
        plugin_dir = Path("./my-plugin")
        plugin_dir.mkdir()
        (plugin_dir / "pyproject.toml").write_text("[project]\nname = 'test'")
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, ["./my-plugin"])
        
        assert result.exit_code == 0
    
    def test_build_absolute_path(self, temp_project_dir, mocker):
        """Test build with absolute path"""
        plugin_dir = temp_project_dir / "my-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "pyproject.toml").write_text("[project]\nname = 'test'")
        
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        runner = CliRunner()
        result = runner.invoke(build_plugin_cmd, [str(plugin_dir)])
        
        assert result.exit_code == 0