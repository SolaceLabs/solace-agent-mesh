"""
Pydantic models for agent tool configurations defined in YAML.
"""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import Field
from ...common.utils.pydantic_utils import SamConfigBase


class BaseToolConfig(SamConfigBase):
    """Base model for common tool configuration fields."""

    required_scopes: List[str] = Field(default_factory=list)
    tool_config: Dict[str, Any] = Field(default_factory=dict)


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
    init_function: Optional[str] = Field(
        default=None,
        description="Name of the lifecycle init function in the same component_module.",
    )
    cleanup_function: Optional[str] = Field(
        default=None,
        description="Name of the lifecycle cleanup function in the same component_module.",
    )
    raw_string_args: List[str] = Field(default_factory=list)


class McpToolConfig(BaseToolConfig):
    """Configuration for an MCP tool or toolset."""
    tool_type: Literal["mcp"]
    connection_params: Dict[str, Any]
    tool_name: Optional[str] = None # Optional filter
    environment_variables: Optional[Dict[str, Any]] = None
    auth: dict[str, Any] | None = None
    manifest: list[dict[str, Any]] | None = None


class OpenApiToolConfig(BaseToolConfig):
    """Configuration for OpenAPI-based tools."""
    tool_type: Literal["openapi"]

    # Specification input (mutually exclusive - only one should be provided)
    specification_file: Optional[str] = None  # Path to OpenAPI spec file
    specification: Optional[str] = None       # Inline OpenAPI spec (JSON/YAML)
    specification_url: Optional[str] = None   # URL to fetch OpenAPI spec from
    specification_format: Optional[Literal["json", "yaml"]] = None  # Optional format hint

    # Server URL override
    base_url: Optional[str] = None  # Base URL to override/complete the server URL in the spec

    # Tool filtering
    tool_filter: Optional[List[str]] = None  # Filter specific operations/endpoints

    # Authentication
    auth: Optional[Dict[str, Any]] = None


AnyToolConfig = Union[
    BuiltinToolConfig,
    BuiltinGroupToolConfig,
    PythonToolConfig,
    McpToolConfig,
    OpenApiToolConfig,
]
