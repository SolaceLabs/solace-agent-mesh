"""
Helper functions for extracting context from tool_context in Claude Code tools.

Supports "app mode" where workspace_id is automatically determined from a2a_context
instead of being provided by the LLM.
"""

import logging
from typing import Optional
from google.adk.tools import ToolContext

log = logging.getLogger(__name__)


def extract_app_id_from_context(
    tool_context: Optional[ToolContext],
    tool_config: Optional[dict] = None,
) -> Optional[str]:
    """
    Extract app_id from a2a_context if app mode is enabled in tool_config.

    This allows tools to automatically use the app workspace associated with
    the current conversation, preventing the LLM from selecting a different workspace.

    Args:
        tool_context: ADK tool context containing a2a_context in state
        tool_config: Tool configuration dict with optional app_mode settings

    Returns:
        app_id if found and app mode enabled, None otherwise
    """
    log.debug("[App Mode Debug] extract_app_id_from_context called")

    # Check if app mode is enabled
    if not tool_config:
        log.debug("[App Mode Debug] tool_config is None")
        return None

    log.debug(f"[App Mode Debug] tool_config keys: {list(tool_config.keys())}")
    app_mode_config = tool_config.get("app_mode", {})
    log.debug(f"[App Mode Debug] app_mode_config: {app_mode_config}")

    if not app_mode_config.get("enabled"):
        log.debug("[App Mode Debug] app_mode not enabled")
        return None

    if not app_mode_config.get("extract_app_id_from_context"):
        log.debug("[App Mode Debug] extract_app_id_from_context not enabled")
        return None

    # Check tool_context
    log.debug(f"[App Mode Debug] tool_context type: {type(tool_context)}")
    log.debug(f"[App Mode Debug] tool_context has 'state' attr: {hasattr(tool_context, 'state') if tool_context else False}")

    # Extract app_id from a2a_context
    if tool_context and hasattr(tool_context, 'state'):
        # Log entire state to see what's available
        # State object has to_dict() method for inspection
        state_dict = tool_context.state.to_dict() if hasattr(tool_context.state, 'to_dict') else {}
        log.debug(f"[App Mode Debug] tool_context.state keys: {list(state_dict.keys())}")
        log.debug(f"[App Mode Debug] tool_context.state contents: {state_dict}")

        a2a_context = tool_context.state.get("a2a_context", {})
        log.debug(f"[App Mode Debug] a2a_context type: {type(a2a_context)}")
        log.info(f"[App Mode] Retrieved a2a_context from tool_context.state: {a2a_context}")

        app_id = a2a_context.get("app_id") if isinstance(a2a_context, dict) else None
        log.info(f"[App Mode] Extracted app_id value: {app_id}")

        if app_id:
            log.info(f"[App Mode] Extracted app_id from a2a_context: {app_id}")
            return app_id
        else:
            log.warning("[App Mode] No app_id found in a2a_context - workspace_id will be required from LLM")
    else:
        log.warning(f"[App Mode Debug] Cannot access state - tool_context is None: {tool_context is None}, has state: {hasattr(tool_context, 'state') if tool_context else 'N/A'}")

    return None


def should_hide_workspace_params(tool_config: Optional[dict] = None) -> bool:
    """
    Check if workspace parameters should be hidden from the tool schema.

    When enabled, workspace_id and workspace_type parameters won't be included
    in the tool's parameter schema, preventing the LLM from providing them.

    Args:
        tool_config: Tool configuration dict with optional app_mode settings

    Returns:
        True if workspace params should be hidden, False otherwise
    """
    if not tool_config:
        return False

    app_mode_config = tool_config.get("app_mode", {})
    return app_mode_config.get("hide_workspace_params", False)


def get_fixed_workspace_type(tool_config: Optional[dict] = None) -> Optional[str]:
    """
    Get fixed workspace type from config if set.

    When configured, this workspace type will be used regardless of what
    the LLM provides or what's in the arguments.

    Args:
        tool_config: Tool configuration dict with optional app_mode settings

    Returns:
        Fixed workspace type ("session" or "app") if configured, None otherwise
    """
    if not tool_config:
        return None

    app_mode_config = tool_config.get("app_mode", {})
    return app_mode_config.get("fixed_workspace_type")


def resolve_workspace_params(
    args: dict,
    tool_context: Optional[ToolContext],
    tool_config: Optional[dict],
    default_workspace_type: str = "session",
) -> tuple[str, str]:
    """
    Resolve workspace_id and workspace_type, applying app_mode overrides if configured.

    Resolution order:
    1. If app_id is in a2a_context and app_mode enabled: use app_id as workspace_id
    2. Otherwise: use workspace_id from args (LLM-provided)
    3. workspace_type: use fixed_workspace_type if configured, else from args, else default

    Args:
        args: Tool invocation arguments from LLM
        tool_context: ADK tool context
        tool_config: Tool configuration dict
        default_workspace_type: Default workspace type if not specified

    Returns:
        Tuple of (workspace_id, workspace_type)

    Raises:
        ValueError: If workspace_id cannot be determined
    """
    # Try to extract app_id from context
    app_id = extract_app_id_from_context(tool_context, tool_config)

    # Determine workspace_id
    if app_id:
        # App mode: use app_id from context
        workspace_id = app_id
        log.info(f"[App Mode] Using workspace_id from context: {workspace_id}")
    else:
        # Normal mode: use workspace_id from args
        workspace_id = args.get("workspace_id")
        if not workspace_id:
            raise ValueError("workspace_id is required when not in app mode")

    # Determine workspace_type
    fixed_type = get_fixed_workspace_type(tool_config)
    if fixed_type:
        # Use fixed workspace type from config
        workspace_type = fixed_type
        log.debug(f"[App Mode] Using fixed workspace_type: {workspace_type}")
    else:
        # Use workspace_type from args or default
        workspace_type = args.get("workspace_type", default_workspace_type)

    return workspace_id, workspace_type
