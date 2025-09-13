"""
Pydantic models for agent tool configurations defined in YAML.
"""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import Field
from ...agent.utils.pydantic_compat import BackwardCompatibleModel


class ToolLifecycleHookConfig(BackwardCompatibleModel):
    """Configuration for a tool's lifecycle hook function."""

    module: str = Field(
        ...,
        description="Python module path for the function (e.g., 'my_plugin.initializers').",
    )
    name: str = Field(..., description="Name of the function within the module.")
    base_path: Optional[str] = Field(
        default=None,
        description="Optional base path for module resolution if not in PYTHONPATH.",
    )
    config: Dict[str, Any] = Field(
        default_factory=dict, description="Configuration dictionary for the function."
    )


class BaseToolConfig(BackwardCompatibleModel):
    """Base model for common tool configuration fields."""

    required_scopes: List[str] = Field(default_factory=list)
    tool_config: Dict[str, Any] = Field(default_factory=dict)
    init_function: Optional[ToolLifecycleHookConfig] = None
    cleanup_function: Optional[ToolLifecycleHookConfig] = None

class BuiltinToolConfig(BaseToolConfig):
    """Configuration for a single built-in tool."""
    tool_type: Literal["builtin"]
    tool_name: str

class BuiltinGroupToolConfig(BaseToolConfig):
    """Configuration for a group of built-in tools by category."""
    tool_type: Literal["builtin-group"]
    group_name: str

class PythonToolConfig(BaseToolConfig):
    """Configuration for a custom Python tool (function or DynamicTool)."""
    tool_type: Literal["python"]
    component_module: str
    component_base_path: Optional[str] = None
    function_name: Optional[str] = None
    tool_name: Optional[str] = None
    tool_description: Optional[str] = None
    class_name: Optional[str] = None
    raw_string_args: List[str] = Field(default_factory=list)

class McpToolConfig(BaseToolConfig):
    """Configuration for an MCP tool or toolset."""
    tool_type: Literal["mcp"]
    connection_params: Dict[str, Any]
    tool_name: Optional[str] = None # Optional filter
    environment_variables: Optional[Dict[str, Any]] = None

AnyToolConfig = Union[
    BuiltinToolConfig,
    BuiltinGroupToolConfig,
    PythonToolConfig,
    McpToolConfig,
]
