"""
Pydantic models for agent tool configurations defined in YAML.
"""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import Field, model_validator
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
    tool_name: Optional[str] = None  # Single tool filter (backward compat)
    tool_name_prefix: Optional[str] = None # Optional prefix for tool names
    environment_variables: Optional[Dict[str, Any]] = None
    auth: dict[str, Any] | None = None
    manifest: list[dict[str, Any]] | None = None

    # Tool filtering options (mutually exclusive with each other AND with tool_name)
    allow_list: Optional[List[str]] = None  # Include only these tools
    deny_list: Optional[List[str]] = None   # Exclude these tools

    @model_validator(mode='after')
    def validate_tool_filtering(self):
        """Ensure tool_name, allow_list, and deny_list are mutually exclusive."""
        filters_specified = [
            self.tool_name is not None,
            self.allow_list is not None,
            self.deny_list is not None,
        ]
        if sum(filters_specified) > 1:
            raise ValueError(
                "MCP tool configuration error: 'tool_name', 'allow_list', and 'deny_list' "
                "are mutually exclusive. Please use only one."
            )
        return self


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

    # Tool filtering (mutually exclusive - only one should be provided)
    allow_list: Optional[List[str]] = None  # Include only these specific operations/endpoints
    deny_list: Optional[List[str]] = None   # Exclude these specific operations/endpoints

    # Authentication
    auth: Optional[Dict[str, Any]] = None

    @model_validator(mode='after')
    def validate_tool_filtering(self):
        """Ensure allow_list and deny_list are mutually exclusive."""
        if self.allow_list is not None and self.deny_list is not None:
            raise ValueError(
                "OpenAPI tool configuration error: Cannot specify both 'allow_list' and 'deny_list'. "
                "Please use only one."
            )
        return self


class ExecutorToolConfig(BaseToolConfig):
    """
    Configuration for executor-based tools.

    Executor tools run on different backends (Python, Lambda) through
    a unified configuration interface. The executor type determines which
    additional fields are required.
    """
    tool_type: Literal["executor"]
    name: str = Field(..., description="Tool name that the LLM will call")
    description: str = Field(..., description="Description of what this tool does")
    executor: Literal["python", "lambda"] = Field(
        ..., description="The executor type to use"
    )

    # Common options
    timeout_seconds: int = Field(default=60, description="Execution timeout")
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Tool parameters schema (JSON Schema format or simple format)",
    )
    # Deprecated: Use type: artifact in parameters schema instead
    # These fields are kept for backward compatibility only
    artifact_content_args: Optional[List[str]] = Field(
        default=None,
        description="(Deprecated) Use 'type: artifact' in parameters instead. "
                    "Parameter names (single values) that should have artifact content pre-loaded",
    )
    artifact_content_list_args: Optional[List[str]] = Field(
        default=None,
        description="(Deprecated) Use 'type: array, items.type: artifact' in parameters instead. "
                    "Parameter names (lists) that should have artifact content pre-loaded for each item",
    )

    # Python executor options
    module: Optional[str] = Field(
        default=None, description="Python module path (for python executor)"
    )
    function: Optional[str] = Field(
        default=None, description="Function name in module (for python executor)"
    )
    pass_tool_context: bool = Field(
        default=True, description="Pass tool_context to function (python executor)"
    )
    pass_tool_config: bool = Field(
        default=True, description="Pass tool_config to function (python executor)"
    )

    # Lambda executor options
    function_arn: Optional[str] = Field(
        default=None, description="Lambda function ARN (for lambda executor)"
    )
    region: Optional[str] = Field(
        default=None, description="AWS region (for lambda executor)"
    )
    invocation_type: Literal["RequestResponse", "Event"] = Field(
        default="RequestResponse", description="Lambda invocation type"
    )
    include_context: bool = Field(
        default=True, description="Include session context in request"
    )

    @model_validator(mode='after')
    def validate_executor_config(self):
        """Validate executor-specific required fields."""
        if self.executor == "python":
            if not self.module or not self.function:
                raise ValueError(
                    "Python executor requires 'module' and 'function' fields"
                )
        elif self.executor == "lambda":
            if not self.function_arn:
                raise ValueError(
                    "Lambda executor requires 'function_arn' field"
                )
        return self


AnyToolConfig = Union[
    BuiltinToolConfig,
    BuiltinGroupToolConfig,
    PythonToolConfig,
    McpToolConfig,
    OpenApiToolConfig,
    ExecutorToolConfig,
]
