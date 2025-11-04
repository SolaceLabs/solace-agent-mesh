"""
Shared fixtures for init_cmd tests
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
    
    # Store the original CWD and change to the new project directory
    original_cwd = Path.cwd()
    os.chdir(project_path)
    
    yield project_path
    
    # Restore the original CWD and clean up
    os.chdir(original_cwd)
    shutil.rmtree(project_path, ignore_errors=True)


@pytest.fixture
def mock_templates(mocker):
    """Mock template loading to avoid file system dependencies"""
    mock_shared_config = """
artifact_service:
  type: __DEFAULT_ARTIFACT_SERVICE_TYPE__
  artifact_scope: __DEFAULT_ARTIFACT_SERVICE_SCOPE__
  # __DEFAULT_ARTIFACT_SERVICE_BASE_PATH_LINE__
"""
    
    mock_logging_config = """
version: 1
disable_existing_loggers: false

formatters:
  simpleFormatter:
    format: "%(asctime)s | %(levelname)-5s | %(threadName)s | %(name)s | %(message)s"

handlers:
  consoleHandler:
    class: logging.StreamHandler
    formatter: simpleFormatter
    stream: ext://sys.stdout

root:
  level: WARNING
  handlers:
    - consoleHandler
"""
    
    mock_orchestrator_config = """
namespace: __NAMESPACE__
app_name: __APP_NAME__
supports_streaming: __SUPPORTS_STREAMING__
agent_name: __AGENT_NAME__
log_file_name: __LOG_FILE_NAME__
instruction: |
  __INSTRUCTION__
session_service:__SESSION_SERVICE__
artifact_service: __ARTIFACT_SERVICE__
artifact_handling_mode: __ARTIFACT_HANDLING_MODE__
enable_embed_resolution: __ENABLE_EMBED_RESOLUTION__
enable_artifact_content_instruction: __ENABLE_ARTIFACT_CONTENT_INSTRUCTION__
agent_card:
  description: __AGENT_CARD_DESCRIPTION__
  defaultInputModes: __DEFAULT_INPUT_MODES__
  defaultOutputModes: __DEFAULT_OUTPUT_MODES__
agent_card_publishing:
  interval_seconds: __AGENT_CARD_PUBLISHING_INTERVAL__
agent_discovery:
  enabled: __AGENT_DISCOVERY_ENABLED__
inter_agent_communication:
  allow_list: __INTER_AGENT_COMMUNICATION_ALLOW_LIST__
  __INTER_AGENT_COMMUNICATION_DENY_LIST_LINE__
  request_timeout_seconds: __INTER_AGENT_COMMUNICATION_TIMEOUT__
"""
    
    mock_webui_config = """
frontend_welcome_message: __FRONTEND_WELCOME_MESSAGE__
frontend_bot_name: __FRONTEND_BOT_NAME__
frontend_collect_feedback: __FRONTEND_COLLECT_FEEDBACK__
session_service:__SESSION_SERVICE__
"""
    
    def load_template_side_effect(name, parser=None, *args):
        templates = {
            "shared_config.yaml": mock_shared_config,
            "logging_config_template.yaml": mock_logging_config,
            "main_orchestrator.yaml": mock_orchestrator_config,
            "webui.yaml": mock_webui_config,
        }
        content = templates.get(name, "")
        if parser and args:
            return parser(content, *args)
        return content
    
    return mocker.patch(
        "cli.utils.load_template",
        side_effect=load_template_side_effect
    )


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
    return mocker.patch("cli.commands.init_cmd.web_init_step.wait_for_server", return_value=True)


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
            "PASCAL_CASE_NAME": "".join(word.capitalize() for word in name.replace("-", "_").split("_")),
        }
    return mocker.patch(
        "cli.commands.init_cmd.orchestrator_step.get_formatted_names",
        side_effect=formatted_names_side_effect
    )