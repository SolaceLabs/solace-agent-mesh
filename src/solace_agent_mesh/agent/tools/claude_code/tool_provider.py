"""
Claude Code Tool Provider.

Provides dynamic tools for AI-assisted coding using Claude Code CLI in Docker containers.
Manages persistent workspaces and maintains session state across invocations.
"""

import logging
from typing import Any, Dict, List, Optional

from ....common.workspace import BaseWorkspaceService, LocalFilesystemWorkspaceService
from ..dynamic_tool import DynamicTool, DynamicToolProvider

log = logging.getLogger(__name__)


class ClaudeCodeToolProvider(DynamicToolProvider):
    """
    Dynamic tool provider for Claude Code integration.

    Manages session state and workspace lifecycle across multiple Claude Code
    invocations. Provides tools for executing code tasks, managing workspaces,
    versioning, and importing/exporting workspaces.

    Session Management:
        - Internally tracks session IDs per workspace
        - Agent doesn't need to manage session_id parameter
        - Sessions persist via mounted ~/.claude/ volume

    Configuration:
        All configuration comes from tool_config:
        - api_key: Anthropic API key
        - model: Claude model to use
        - max_iterations: Max iterations for Claude Code
        - workspace_base: Base path for workspaces
        - settings_base: Base path for Claude Code settings
        - environment_variables: Dict of arbitrary env vars
        - settings: Overrides for settings.json
        - app_mode: Optional app mode configuration
            - enabled: Enable app mode behavior
            - extract_app_id_from_context: Extract app_id from a2a_context
            - fixed_workspace_type: Force workspace_type to this value
            - hide_workspace_params: Remove workspace params from schemas
            - hidden_tools: List of tool names to exclude
    """

    def __init__(self):
        super().__init__()
        self.cc_sessions: Dict[str, str] = {}  # {user_id}/{workspace_id} -> session_id
        self.workspace_service: Optional[BaseWorkspaceService] = None
        self.settings_base: str = "/claude-settings"
        self.tool_config: Optional[Dict[str, Any]] = None
        self._initialized: bool = False


    def _initialize_sync(self, tool_config: Dict[str, Any]) -> None:
        """
        Synchronous initialization called from create_tools().

        Args:
            tool_config: Tool configuration dict
        """
        if self._initialized:
            return

        self.tool_config = tool_config

        # Initialize workspace service
        workspace_base = tool_config.get("workspace_base", "/claude-workspaces")
        self.workspace_service = LocalFilesystemWorkspaceService(workspace_base)
        log.info(f"Initialized workspace service at {workspace_base}")

        # Store settings base path
        self.settings_base = tool_config.get("settings_base", "/claude-settings")
        log.info(f"Using settings base path: {self.settings_base}")

        self._initialized = True
        log.info("ClaudeCodeToolProvider initialized successfully")

    def create_tools(
        self,
        tool_config: Optional[Dict] = None,
    ) -> List[DynamicTool]:
        """
        Create the Claude Code tools, filtering based on app_mode config.
        Called by framework to get tool instances.

        Args:
            tool_config: Optional tool configuration

        Returns:
            List of DynamicTool instances (filtered if app_mode.hidden_tools is configured)
        """
        # Initialize the provider with the config
        if tool_config:
            self._initialize_sync(tool_config)

        from .execute_tool import ClaudeCodeExecuteTool
        from .list_workspaces_tool import ClaudeCodeListWorkspacesTool
        from .list_sessions_tool import ClaudeCodeListSessionsTool
        from .read_files_tool import ClaudeCodeReadFilesTool
        from .create_version_tool import ClaudeCodeCreateVersionTool
        from .export_workspace_tool import ClaudeCodeExportWorkspaceTool
        from .import_workspace_tool import ClaudeCodeImportWorkspaceTool

        # Create all available tools in a dictionary
        all_tools = {
            "claude_code_execute": ClaudeCodeExecuteTool(
                self.workspace_service,
                self.cc_sessions,
                self.settings_base,
                self.tool_config or tool_config,
            ),
            "claude_code_list_workspaces": ClaudeCodeListWorkspacesTool(
                self.workspace_service,
                self.tool_config or tool_config,
            ),
            "claude_code_list_sessions": ClaudeCodeListSessionsTool(
                self.cc_sessions,
                self.tool_config or tool_config,
            ),
            "claude_code_read_files": ClaudeCodeReadFilesTool(
                self.workspace_service,
                self.tool_config or tool_config,
            ),
            "claude_code_create_version": ClaudeCodeCreateVersionTool(
                self.workspace_service,
                self.tool_config or tool_config,
            ),
            "claude_code_export_workspace": ClaudeCodeExportWorkspaceTool(
                self.workspace_service,
                self.tool_config or tool_config,
            ),
            "claude_code_import_workspace": ClaudeCodeImportWorkspaceTool(
                self.workspace_service,
                self.tool_config or tool_config,
            ),
        }

        # Filter tools based on app_mode configuration
        config = self.tool_config or tool_config
        if config and config.get("app_mode", {}).get("enabled"):
            hidden_tools = set(config.get("app_mode", {}).get("hidden_tools", []))
            if hidden_tools:
                log.info(f"[App Mode] Hiding tools: {hidden_tools}")
                filtered_tools = [tool for name, tool in all_tools.items() if name not in hidden_tools]
                log.info(f"[App Mode] Providing {len(filtered_tools)} tools (hidden {len(hidden_tools)})")
                return filtered_tools

        # Return all tools if no filtering configured
        return list(all_tools.values())

