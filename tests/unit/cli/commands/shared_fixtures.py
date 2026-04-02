"""Shared fixtures for CLI command tests.

This module contains fixtures used across multiple CLI command test suites,
particularly for mocking template loading operations.
"""

import pytest


@pytest.fixture
def mock_templates(mocker):
    """
    Mock template loading to avoid file system dependencies.

    Supports templates for both plugin and init commands:
    - Plugin templates: agent/gateway/custom configs, pyproject, readme, tools, gateway app/component
    - Init templates: shared_config, logging_config, main_orchestrator, webui

    Args:
        mocker: pytest-mock mocker fixture

    Returns:
        Mock object for template loading
    """
    # Plugin command templates
    mock_plugin_config_template = """
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

    # Init command templates
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
            # Plugin command templates
            "plugin_agent_config_template.yaml": mock_plugin_config_template,
            "plugin_gateway_config_template.yaml": mock_plugin_config_template,
            "plugin_custom_config_template.yaml": mock_plugin_config_template,
            "plugin_tool_config_template.yaml": mock_plugin_config_template,
            "plugin_workflow_config_template.yaml": mock_plugin_config_template,
            "plugin_pyproject_template.toml": mock_pyproject_template,
            "plugin_readme_template.md": mock_readme_template,
            "plugin_tools_template.py": mock_tools_template,
            "gateway_app_template.py": mock_gateway_app_template,
            "gateway_component_template.py": mock_gateway_component_template,
            "plugin_custom_template.py": mock_custom_template,
            # Init command templates
            "shared_config.yaml": mock_shared_config,
            "logging_config_template.yaml": mock_logging_config,
            "main_orchestrator.yaml": mock_orchestrator_config,
            "webui.yaml": mock_webui_config,
        }
        content = templates.get(name, "")
        if parser and args:
            return parser(content, *args)
        return content

    # The mocker needs to patch both locations where load_template is used
    plugin_mock = mocker.patch(
        "cli.commands.plugin_cmd.create_cmd.load_template",
        side_effect=load_template_side_effect,
    )

    # Return the plugin mock as the primary (for backward compatibility)
    return plugin_mock
