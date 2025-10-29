"""
Shared fixtures for plugin_cmd tests
"""
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory for testing"""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    
    # Create necessary directory structure
    (project_path / "configs" / "agents").mkdir(parents=True)
    (project_path / "configs" / "gateways").mkdir(parents=True)
    (project_path / "configs" / "plugins").mkdir(parents=True)
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
def mock_templates(mocker):
    """Mock template loading to avoid file system dependencies"""
    mock_config_template = """
namespace: __COMPONENT_KEBAB_CASE_NAME__
component_id: __COMPONENT_SNAKE_CASE_NAME__
type: __PLUGIN_META_DATA_TYPE__
"""
    
    mock_pyproject_template = """
[project]
name = "__PLUGIN_KEBAB_CASE_NAME__"
version = "__PLUGIN_VERSION__"
description = "__PLUGIN_DESCRIPTION__"

[tool.__PLUGIN_SNAKE_CASE_NAME__.metadata]
type = "__PLUGIN_META_DATA_TYPE__"
"""
    
    mock_readme_template = """
# __PLUGIN_SPACED_NAME__

__PLUGIN_DESCRIPTION__
"""
    
    mock_tools_template = """
# Tools for __PLUGIN_PASCAL_CASE_NAME__
"""
    
    mock_gateway_app_template = """
# __GATEWAY_NAME_PASCAL_CASE__ Gateway App
"""
    
    mock_gateway_component_template = """
# __GATEWAY_NAME_PASCAL_CASE__ Component
"""
    
    mock_custom_template = """
# __COMPONENT_PASCAL_CASE_NAME__ Custom Component
"""
    
    def load_template_side_effect(name, parser=None, *args):
        templates = {
            "plugin_agent_config_template.yaml": mock_config_template,
            "plugin_gateway_config_template.yaml": mock_config_template,
            "plugin_custom_config_template.yaml": mock_config_template,
            "plugin_pyproject_template.toml": mock_pyproject_template,
            "plugin_readme_template.md": mock_readme_template,
            "plugin_tools_template.py": mock_tools_template,
            "gateway_app_template.py": mock_gateway_app_template,
            "gateway_component_template.py": mock_gateway_component_template,
            "plugin_custom_template.py": mock_custom_template,
        }
        content = templates.get(name, "")
        if parser and args:
            return parser(content, *args)
        return content
    
    return mocker.patch(
        "cli.commands.plugin_cmd.create_cmd.load_template",
        side_effect=load_template_side_effect
    )


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