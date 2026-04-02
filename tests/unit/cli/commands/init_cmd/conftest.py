"""
Shared fixtures for init_cmd tests
"""

import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import shared mock_templates fixture from parent directory


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory for testing"""
    project_path = tmp_path / "test_project"
    project_path.mkdir()

    # Store the original CWD and change to the new project directory
    original_cwd = Path.cwd()
    os.chdir(project_path)

    yield project_path

    # Restore the original CWD and clean up
    os.chdir(original_cwd)
    shutil.rmtree(project_path, ignore_errors=True)


@pytest.fixture
def mock_database_operations(mocker):
    """Mock database creation and validation"""
    mock_engine = MagicMock()
    mocker.patch("cli.utils.create_engine", return_value=mock_engine)
    mocker.patch("cli.utils.event")
    return mock_engine


@pytest.fixture
def mock_multiprocessing(mocker):
    """Mock multiprocessing for web init"""
    mock_manager = MagicMock()
    mock_dict = {}
    mock_manager.dict.return_value = mock_dict
    mock_manager.__enter__ = MagicMock(return_value=mock_manager)
    mock_manager.__exit__ = MagicMock(return_value=False)

    mock_process = MagicMock()
    mock_process.start = MagicMock()
    mock_process.join = MagicMock()

    mocker.patch("multiprocessing.Manager", return_value=mock_manager)
    mocker.patch("multiprocessing.Process", return_value=mock_process)

    return {"manager": mock_manager, "process": mock_process, "dict": mock_dict}


@pytest.fixture
def mock_webbrowser(mocker):
    """Mock webbrowser.open"""
    return mocker.patch("webbrowser.open")


@pytest.fixture
def mock_wait_for_server(mocker):
    """Mock wait_for_server utility"""
    return mocker.patch(
        "cli.commands.init_cmd.web_init_step.wait_for_server", return_value=True
    )


@pytest.fixture
def mock_subprocess(mocker):
    """Mock os.system for subprocess calls"""
    return mocker.patch("os.system", return_value=0)


@pytest.fixture
def mock_shutil_which(mocker):
    """Mock shutil.which to simulate command availability"""

    def which_side_effect(cmd):
        if cmd in ["podman", "docker"]:
            return f"/usr/bin/{cmd}"
        return None

    return mocker.patch("shutil.which", side_effect=which_side_effect)


@pytest.fixture
def mock_get_formatted_names(mocker):
    """Mock get_formatted_names utility"""

    def formatted_names_side_effect(name):
        return {
            "KEBAB_CASE_NAME": name.lower().replace("_", "-"),
            "SNAKE_CASE_NAME": name.lower().replace("-", "_"),
            "PASCAL_CASE_NAME": "".join(
                word.capitalize() for word in name.replace("-", "_").split("_")
            ),
        }

    return mocker.patch(
        "cli.commands.init_cmd.orchestrator_step.get_formatted_names",
        side_effect=formatted_names_side_effect,
    )
