"""
Shared fixtures for plugin_cmd tests
"""
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import shared mock_templates fixture from parent directory
from tests.unit.cli.commands.shared_fixtures import mock_templates


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory for testing"""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    
    # Create necessary directory structure
    (project_path / "configs" / "agents").mkdir(parents=True)
    (project_path / "configs" / "gateways").mkdir(parents=True)
    (project_path / "configs" / "plugins").mkdir(parents=True)
    (project_path / "configs" / "workflows").mkdir(parents=True)
    (project_path / "src").mkdir(parents=True)
    
    # Store the original CWD and change to the new project directory
    original_cwd = Path.cwd()
    os.chdir(project_path)
    
    yield project_path
    
    # Restore the original CWD and clean up
    os.chdir(original_cwd)
    shutil.rmtree(project_path, ignore_errors=True)


@pytest.fixture
def mock_plugin_path(tmp_path):
    """Create a mock plugin directory with pyproject.toml and config.yaml"""
    plugin_path = tmp_path / "mock_plugin"
    plugin_path.mkdir()
    
    # Create pyproject.toml
    pyproject_content = """
[project]
name = "mock-plugin"
version = "0.1.0"

[tool.mock_plugin.metadata]
type = "agent"
"""
    (plugin_path / "pyproject.toml").write_text(pyproject_content)
    
    # Create config.yaml
    config_content = """
namespace: __COMPONENT_KEBAB_CASE_NAME__
component_id: __COMPONENT_SNAKE_CASE_NAME__
"""
    (plugin_path / "config.yaml").write_text(config_content)
    
    return plugin_path


@pytest.fixture
def mock_subprocess_run(mocker):
    """Mock subprocess.run for command execution"""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Installation successful"
    mock_result.stderr = ""
    return mocker.patch("subprocess.run", return_value=mock_result)


@pytest.fixture
def mock_shutil_which(mocker):
    """Mock shutil.which to simulate command availability"""
    return mocker.patch("shutil.which", return_value="/usr/bin/git")


@pytest.fixture
def mock_get_module_path(mocker):
    """Mock get_module_path to return a valid path"""
    def _get_module_path(module_name):
        return f"/fake/path/to/{module_name}"
    return mocker.patch("cli.commands.plugin_cmd.install_cmd.get_module_path", side_effect=_get_module_path)


@pytest.fixture
def mock_official_registry(mocker):
    """Mock official registry functions"""
    mocker.patch(
        "cli.commands.plugin_cmd.install_cmd.get_official_plugin_url",
        return_value=None
    )
    mocker.patch(
        "cli.commands.plugin_cmd.create_cmd.is_official_plugin",
        return_value=False
    )
    return mocker



@pytest.fixture
def mock_httpx_client(mocker):
    """Mock httpx.Client for HTTP requests"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"type": "dir", "name": "plugin1"},
        {"type": "dir", "name": "plugin2"},
        {"type": "file", "name": "README.md"},
    ]
    
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    
    return mocker.patch("httpx.Client", return_value=mock_client)