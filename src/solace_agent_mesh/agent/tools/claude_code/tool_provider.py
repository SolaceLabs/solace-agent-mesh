"""
Claude Code Tool Provider.

Provides dynamic tools for AI-assisted coding using Claude Code CLI in Docker containers.
Manages persistent workspaces and maintains session state across invocations.
"""

import logging
from typing import Any, Dict, List, Optional

from ....common.workspace import BaseWorkspaceService, LocalFilesystemWorkspaceService
from ....services.workspace import WorkspaceManager
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
        - workspace_manager: Optional workspace manager configuration (for K8S production)
            - enabled: Enable workspace manager for tarball persistence
            - app_storage: AppStorageService configuration (same format as gateway)
    """

    def __init__(self):
        super().__init__()
        self.cc_sessions: Dict[str, str] = {}  # {user_id}/{workspace_id} -> session_id
        self.workspace_service: Optional[BaseWorkspaceService] = None
        self.workspace_manager: Optional[WorkspaceManager] = None
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

        # Initialize WorkspaceManager if configured (for K8S production)
        self.workspace_manager = self._init_workspace_manager(tool_config)

        self._initialized = True
        log.info("ClaudeCodeToolProvider initialized successfully")

    def _init_workspace_manager(self, tool_config: Dict[str, Any]) -> Optional[WorkspaceManager]:
        """
        Initialize WorkspaceManager based on tool configuration.

        Configuration example:
        ```yaml
        workspace_manager:
          enabled: true
          app_storage:
            type: s3
            bucket: sam-apps
            prefix: apps
        ```

        The artifact_service is obtained from the host component if available.

        Returns:
            WorkspaceManager instance, or None if not configured
        """
        wm_config = tool_config.get("workspace_manager", {})
        if not wm_config.get("enabled", False):
            log.debug("WorkspaceManager not enabled in tool config")
            return None

        try:
            # Get artifact service from host component (if available)
            # This is passed through from the agent component
            artifact_service = tool_config.get("_artifact_service")
            if not artifact_service:
                log.warning(
                    "WorkspaceManager enabled but no artifact_service available. "
                    "Workspace persistence will not work."
                )
                return None

            # Initialize AppStorageService (optional, for syncing dist/)
            app_storage_service = None
            app_storage_config = wm_config.get("app_storage")
            if app_storage_config:
                app_storage_service = self._init_app_storage_service(app_storage_config)

            workspace_manager = WorkspaceManager(
                artifact_service=artifact_service,
                app_storage_service=app_storage_service,
            )
            log.info("Initialized WorkspaceManager for K8S production deployment")
            return workspace_manager

        except Exception as e:
            log.error(f"Failed to initialize WorkspaceManager: {e}", exc_info=True)
            return None

    def _init_app_storage_service(self, storage_config: Dict[str, Any]):
        """
        Initialize AppStorageService based on configuration.

        Args:
            storage_config: Storage configuration dict with 'type' and type-specific options

        Returns:
            AppStorageService instance, or None on failure
        """
        storage_type = storage_config.get("type", "filesystem")

        try:
            if storage_type == "s3":
                from ....services.app_storage import S3AppStorageService

                bucket = storage_config.get("bucket")
                if not bucket:
                    raise ValueError("app_storage.bucket is required for S3 storage type")

                return S3AppStorageService(
                    bucket=bucket,
                    prefix=storage_config.get("prefix", "apps"),
                    region_name=storage_config.get("region"),
                    endpoint_url=storage_config.get("endpoint_url"),
                )

            elif storage_type == "filesystem":
                from ....services.app_storage import FilesystemAppStorageService

                base_path = storage_config.get("base_path", "~/.sam-app-storage")
                return FilesystemAppStorageService(base_path=base_path)

            else:
                log.error(f"Unknown app_storage type: {storage_type}")
                return None

        except Exception as e:
            log.error(f"Failed to initialize AppStorageService: {e}", exc_info=True)
            return None

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
                workspace_manager=self.workspace_manager,
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

