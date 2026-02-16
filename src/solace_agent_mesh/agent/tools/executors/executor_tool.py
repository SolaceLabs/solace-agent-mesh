"""
ExecutorBasedTool - A DynamicTool that delegates execution to a ToolExecutor.

This allows tools to be defined via configuration and run on different backends
without changing the tool definition.
"""

import logging
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from ..dynamic_tool import DynamicTool
from ..tool_result import ToolResult, DataObject
from ..artifact_types import ArtifactTypeInfo
from .base import ToolExecutor, ToolExecutionResult

if TYPE_CHECKING:
    from ...sac.component import SamAgentComponent

log = logging.getLogger(__name__)


class ExecutorBasedTool(DynamicTool):
    """
    A DynamicTool that delegates execution to a ToolExecutor.

    This class provides the bridge between the ADK tool interface and
    the executor abstraction, allowing tools to run on different backends
    through configuration.

    Example:
        executor = LocalPythonExecutor(
            module="my_tools",
            function="process_data"
        )
        tool = ExecutorBasedTool(
            name="process_data",
            description="Process data using custom logic",
            parameters_schema=schema,
            executor=executor,
        )
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters_schema: adk_types.Schema,
        executor: ToolExecutor,
        tool_config: Optional[Dict[str, Any]] = None,
        artifact_params: Optional[Dict[str, ArtifactTypeInfo]] = None,
        # Deprecated - use artifact_params or type: artifact in schema
        artifact_args: Optional[List[str]] = None,
        artifact_list_args: Optional[List[str]] = None,
        # Aliases for backward compatibility with setup.py / YAML configs
        artifact_content_args: Optional[List[str]] = None,
        artifact_content_list_args: Optional[List[str]] = None,
        # Embed resolution control
        raw_string_args: Optional[List[str]] = None,
        resolution_type: Literal["early", "all"] = "early",
        # ToolContextFacade injection
        ctx_facade_param_name: Optional[str] = None,
    ):
        """
        Initialize an executor-based tool.

        Args:
            name: The tool name (what the LLM calls)
            description: Tool description for the LLM
            parameters_schema: ADK Schema defining parameters
            executor: The executor to delegate to
            tool_config: Optional tool configuration
            artifact_params: Dict mapping param names to ArtifactTypeInfo
            artifact_args: (Deprecated) Parameter names (single) to pre-load
            artifact_list_args: (Deprecated) Parameter names (lists) to pre-load
            artifact_content_args: (Deprecated) Alias for artifact_args
            artifact_content_list_args: (Deprecated) Alias for artifact_list_args
            raw_string_args: Parameters that should not have embeds resolved
            resolution_type: "early" or "all" for embed resolution
            ctx_facade_param_name: Parameter name for ToolContextFacade injection
        """
        super().__init__(tool_config=tool_config)
        self._name = name
        self._description = description
        self._schema = parameters_schema
        self._executor = executor
        self._raw_string_args = raw_string_args or []
        self._resolution_type = resolution_type
        self._ctx_facade_param_name = ctx_facade_param_name

        # Merge artifact_content_args into artifact_args for backward compatibility
        effective_artifact_args = list(artifact_args or [])
        effective_artifact_args.extend(artifact_content_args or [])

        effective_list_args = list(artifact_list_args or [])
        effective_list_args.extend(artifact_content_list_args or [])

        # Use artifact_params if provided, otherwise build from deprecated args
        if artifact_params is not None:
            self._artifact_params = artifact_params
        else:
            # Build from deprecated args for backward compatibility
            self._artifact_params = {}
            for param_name in effective_artifact_args:
                self._artifact_params[param_name] = ArtifactTypeInfo(
                    is_artifact=True, is_list=False
                )
            for param_name in effective_list_args:
                self._artifact_params[param_name] = ArtifactTypeInfo(
                    is_artifact=True, is_list=True
                )

    def update_from_init(
        self,
        description: Optional[str] = None,
        parameters_schema: Optional[adk_types.Schema] = None,
        ctx_facade_param_name: Optional[str] = None,
    ) -> None:
        """
        Update tool metadata from init protocol response.

        Called after the remote worker runs the tool's init() inside bwrap
        and returns enriched description/schema. Only non-None values are
        applied.

        Args:
            description: Enriched tool description from init()
            parameters_schema: Enriched ADK Schema from init()
            ctx_facade_param_name: Parameter name for ToolContextFacade injection
        """
        if description is not None:
            self._description = description
        if parameters_schema is not None:
            self._schema = parameters_schema
        if ctx_facade_param_name is not None:
            self._ctx_facade_param_name = ctx_facade_param_name

    @property
    def tool_name(self) -> str:
        return self._name

    @property
    def tool_description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return self._schema

    @property
    def artifact_args(self) -> List[str]:
        """Return list of all artifact parameter names."""
        return list(self._artifact_params.keys())

    @property
    def artifact_params(self) -> Dict[str, ArtifactTypeInfo]:
        """Return detailed info about artifact parameters."""
        return self._artifact_params

    @property
    def raw_string_args(self) -> List[str]:
        """Return list of arguments that should not have embeds resolved."""
        return self._raw_string_args

    @property
    def resolution_type(self) -> Literal["early", "all"]:
        """Return the embed resolution type."""
        return self._resolution_type

    @property
    def ctx_facade_param_name(self) -> Optional[str]:
        """Return the parameter name for ToolContextFacade injection."""
        return self._ctx_facade_param_name

    async def init(
        self,
        component: "SamAgentComponent",
        tool_config: Any,
    ) -> None:
        """Initialize the underlying executor."""
        log_id = f"[ExecutorBasedTool:{self._name}]"
        log.debug("%s Initializing executor", log_id)

        executor_config = {}
        if hasattr(tool_config, "model_dump"):
            executor_config = tool_config.model_dump()
        elif isinstance(tool_config, dict):
            executor_config = tool_config

        await self._executor.initialize(component, executor_config)
        log.info(
            "%s Initialized with %s executor",
            log_id,
            self._executor.executor_type,
        )

    async def cleanup(
        self,
        component: "SamAgentComponent",
        tool_config: Any,
    ) -> None:
        """Clean up the underlying executor."""
        log_id = f"[ExecutorBasedTool:{self._name}]"

        executor_config = {}
        if hasattr(tool_config, "model_dump"):
            executor_config = tool_config.model_dump()
        elif isinstance(tool_config, dict):
            executor_config = tool_config

        await self._executor.cleanup(component, executor_config)
        log.debug("%s Cleaned up", log_id)

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: ToolContext,
        credential: Optional[str] = None,
    ):
        """Execute using the configured executor."""
        log_id = f"[ExecutorBasedTool:{self._name}]"

        # Get tool config as dict
        tool_config_dict = {}
        if isinstance(self.tool_config, dict):
            tool_config_dict = self.tool_config
        elif hasattr(self.tool_config, "model_dump"):
            tool_config_dict = self.tool_config.model_dump()

        log.debug("%s Executing via %s executor", log_id, self._executor.executor_type)

        # Execute via the executor
        result = await self._executor.execute(
            args=args,
            tool_context=tool_context,
            tool_config=tool_config_dict,
        )

        # If executor returned a ToolResult, pass it through directly
        # ToolResultProcessor will handle artifact saving
        if isinstance(result, ToolResult):
            log.debug("%s Passing through ToolResult to framework", log_id)
            return result

        # Convert ToolExecutionResult to dict for the framework
        return self._convert_result(result)

    def _convert_result(self, result: ToolExecutionResult) -> dict:
        """Convert ToolExecutionResult to dict response."""
        if result.success:
            response = {
                "status": "success",
            }

            # Always nest data to avoid key collisions with status/metadata
            if result.data is not None:
                response["data"] = result.data

            if result.metadata:
                response["metadata"] = result.metadata

            return response
        else:
            return {
                "status": "error",
                "message": result.error or "Execution failed",
                "error_code": result.error_code,
                "metadata": result.metadata,
            }


def create_executor_tool_from_config(
    config: Dict[str, Any],
) -> ExecutorBasedTool:
    """
    Create an ExecutorBasedTool from a configuration dictionary.

    This is a convenience function for creating tools from YAML config.

    Args:
        config: Tool configuration dictionary with keys:
            - name: Tool name
            - description: Tool description
            - executor: Executor type ("python")
            - parameters: Parameter schema definition
            - artifact_content_args: List of single-value params to pre-load artifacts
            - artifact_content_list_args: List of list-value params to pre-load artifacts
            - ... executor-specific config

    Returns:
        Configured ExecutorBasedTool instance

    Raises:
        ValueError: If configuration is invalid
    """
    from .base import create_executor

    # Validate required fields
    required = ["name", "description", "executor"]
    for field in required:
        if field not in config:
            raise ValueError(f"Missing required field: {field}")

    executor_type = config["executor"]

    # Define required fields for each executor type
    executor_required_fields = {
        "python": ["module", "function"],
    }

    # Validate executor type
    if executor_type not in executor_required_fields:
        raise ValueError(f"Unknown executor type: {executor_type}")

    # Validate required fields for this executor type
    missing_fields = [
        field for field in executor_required_fields[executor_type]
        if not config.get(field)
    ]
    if missing_fields:
        raise ValueError(
            f"Missing required fields for '{executor_type}' executor: {missing_fields}"
        )

    # Build executor kwargs based on type
    executor_kwargs = {}

    if executor_type == "python":
        executor_kwargs = {
            "module": config["module"],
            "function": config["function"],
            "pass_tool_context": config.get("pass_tool_context", True),
            "pass_tool_config": config.get("pass_tool_config", True),
        }

    # Create executor
    executor = create_executor(executor_type, **executor_kwargs)

    # Build parameter schema and detect artifact types
    schema_result = _build_schema_from_config(config.get("parameters", {}))

    # Merge schema-detected artifacts with explicit config (for backward compatibility)
    # Schema-detected artifacts take precedence
    artifact_params = dict(schema_result.artifact_params)

    # Add any explicitly configured artifact args (backward compat, deprecated)
    # Support both old names (artifact_args) and YAML config names (artifact_content_args)
    for param_name in config.get("artifact_content_args", config.get("artifact_args", [])):
        if param_name not in artifact_params:
            artifact_params[param_name] = ArtifactTypeInfo(
                is_artifact=True, is_list=False
            )
    for param_name in config.get("artifact_content_list_args", config.get("artifact_list_args", [])):
        if param_name not in artifact_params:
            artifact_params[param_name] = ArtifactTypeInfo(
                is_artifact=True, is_list=True
            )

    # Create tool
    return ExecutorBasedTool(
        name=config["name"],
        description=config["description"],
        parameters_schema=schema_result.schema,
        executor=executor,
        tool_config=config.get("tool_config", {}),
        artifact_params=artifact_params,
    )


class SchemaParseResult:
    """Result from parsing a parameters config into ADK schema."""

    def __init__(
        self,
        schema: adk_types.Schema,
        artifact_params: Dict[str, ArtifactTypeInfo],
    ):
        self.schema = schema
        self.artifact_params = artifact_params


def _build_schema_from_config(
    params_config: Dict[str, Any],
) -> SchemaParseResult:
    """
    Build an ADK Schema from a parameters configuration dict.

    Detects 'artifact' type and translates to 'string' for the LLM,
    while tracking which parameters need artifact pre-loading.

    Supported artifact type formats:
        type: artifact                    -> single artifact (string)
        type: array, items.type: artifact -> list of artifacts (array of strings)

    Args:
        params_config: Parameter configuration dict

    Returns:
        SchemaParseResult with schema and artifact parameter info
    """
    artifact_params: Dict[str, ArtifactTypeInfo] = {}

    if not params_config:
        return SchemaParseResult(
            schema=adk_types.Schema(
                type=adk_types.Type.OBJECT,
                properties={},
                required=[],
            ),
            artifact_params={},
        )

    type_map = {
        "string": adk_types.Type.STRING,
        "str": adk_types.Type.STRING,
        "integer": adk_types.Type.INTEGER,
        "int": adk_types.Type.INTEGER,
        "number": adk_types.Type.NUMBER,
        "float": adk_types.Type.NUMBER,
        "boolean": adk_types.Type.BOOLEAN,
        "bool": adk_types.Type.BOOLEAN,
        "array": adk_types.Type.ARRAY,
        "list": adk_types.Type.ARRAY,
        "object": adk_types.Type.OBJECT,
        "dict": adk_types.Type.OBJECT,
        # Artifact type - translated to string for LLM
        "artifact": adk_types.Type.STRING,
    }

    def process_property(name: str, prop_config: Any) -> adk_types.Schema:
        """Process a single property config and return its schema."""
        if isinstance(prop_config, str):
            # Simple type string: "string", "artifact", etc.
            prop_type = prop_config.lower()
            if prop_type == "artifact":
                artifact_params[name] = ArtifactTypeInfo(
                    is_artifact=True, is_list=False
                )
            adk_type = type_map.get(prop_type, adk_types.Type.STRING)
            return adk_types.Schema(type=adk_type)

        elif isinstance(prop_config, dict):
            prop_type = prop_config.get("type", "string").lower()
            description = prop_config.get("description")
            nullable = prop_config.get("nullable", False)

            # Check for artifact type
            if prop_type == "artifact":
                artifact_params[name] = ArtifactTypeInfo(
                    is_artifact=True, is_list=False
                )
                return adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description=description,
                    nullable=nullable,
                )

            # Check for array of artifacts
            if prop_type in ("array", "list"):
                items_config = prop_config.get("items", {})
                items_type = items_config.get("type", "string").lower() if isinstance(items_config, dict) else str(items_config).lower()

                if items_type == "artifact":
                    # Array of artifacts -> array of strings
                    artifact_params[name] = ArtifactTypeInfo(
                        is_artifact=True, is_list=True
                    )
                    return adk_types.Schema(
                        type=adk_types.Type.ARRAY,
                        items=adk_types.Schema(type=adk_types.Type.STRING),
                        description=description,
                        nullable=nullable,
                    )
                else:
                    # Regular array
                    items_adk_type = type_map.get(items_type, adk_types.Type.STRING)
                    return adk_types.Schema(
                        type=adk_types.Type.ARRAY,
                        items=adk_types.Schema(type=items_adk_type),
                        description=description,
                        nullable=nullable,
                    )

            # Regular type
            adk_type = type_map.get(prop_type, adk_types.Type.STRING)
            return adk_types.Schema(
                type=adk_type,
                description=description,
                nullable=nullable,
            )

        else:
            # Unknown format, default to string
            return adk_types.Schema(type=adk_types.Type.STRING)

    # Handle both direct schema format and nested format
    if "properties" in params_config:
        # Standard JSON Schema format
        properties = {}
        for name, prop_config in params_config.get("properties", {}).items():
            properties[name] = process_property(name, prop_config)

        return SchemaParseResult(
            schema=adk_types.Schema(
                type=adk_types.Type.OBJECT,
                properties=properties,
                required=params_config.get("required", []),
            ),
            artifact_params=artifact_params,
        )
    else:
        # Simple format: {param_name: param_type_or_config}
        properties = {}
        for name, type_spec in params_config.items():
            properties[name] = process_property(name, type_spec)

        return SchemaParseResult(
            schema=adk_types.Schema(
                type=adk_types.Type.OBJECT,
                properties=properties,
                required=[],
            ),
            artifact_params=artifact_params,
        )
