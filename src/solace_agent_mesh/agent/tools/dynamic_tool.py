"""
Defines the base classes and helpers for "dynamic" tools.
Dynamic tools allow for programmatic definition of tool names, descriptions,
and parameter schemas, offering more flexibility than standard Python tools.
"""

import logging
from abc import ABC, abstractmethod
from typing import (
    Optional,
    List,
    Callable,
    Dict,
    Any,
    Set,
    get_origin,
    get_args,
    Union,
    Literal,
    TYPE_CHECKING,
    Type,
)
import inspect

from pydantic import BaseModel
from google.adk.tools import BaseTool, ToolContext
from google.genai import types as adk_types

from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id
from solace_agent_mesh.agent.utils.artifact_helpers import load_artifact_content_or_metadata
from solace_agent_mesh.agent.utils.tool_context_facade import ToolContextFacade
from .artifact_types import Artifact, is_artifact_type, get_artifact_info, ArtifactTypeInfo

from ...common.utils.embeds import (
    resolve_embeds_in_string,
    evaluate_embed,
    EARLY_EMBED_TYPES,
    LATE_EMBED_TYPES,
    EMBED_DELIMITER_OPEN,
)
from ...common.utils.embeds.types import ResolutionMode

log = logging.getLogger(__name__)


def _is_tool_context_facade_param(annotation) -> bool:
    """Check if an annotation represents a ToolContextFacade parameter."""
    if annotation is None:
        return False
    if annotation is ToolContextFacade:
        return True
    if isinstance(annotation, str) and "ToolContextFacade" in annotation:
        return True
    return False


if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent
    from .tool_config_types import AnyToolConfig


# --- Base Class for Programmatic Tools ---


class DynamicTool(BaseTool, ABC):
    """
    Base class for dynamic tools that can define their own function names,
    descriptions, and parameter schemas programmatically.
    """

    config_model: Optional[Type[BaseModel]] = None

    def __init__(self, tool_config: Optional[Union[dict, BaseModel]] = None):
        # Initialize with placeholder values, will be overridden by properties
        super().__init__(
            name="dynamic_tool_placeholder", description="dynamic_tool_placeholder"
        )
        self.tool_config = tool_config or {}

    async def init(
        self, component: "SamAgentComponent", tool_config: "AnyToolConfig"
    ) -> None:
        """
        (Optional) Asynchronously initializes resources for the tool.
        This method is called once when the agent starts up.
        The `component` provides access to agent-wide state, and `tool_config`
        is the validated Pydantic model instance if `config_model` is defined.
        """
        pass

    async def cleanup(
        self, component: "SamAgentComponent", tool_config: "AnyToolConfig"
    ) -> None:
        """
        (Optional) Asynchronously cleans up resources used by the tool.
        This method is called once when the agent is shutting down.
        """
        pass

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Return the function name that the LLM will call."""
        pass

    @property
    @abstractmethod
    def tool_description(self) -> str:
        """Return the description of what this tool does."""
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> adk_types.Schema:
        """Return the ADK Schema defining the tool's parameters."""
        pass

    @property
    def raw_string_args(self) -> List[str]:
        """
        Return a list of argument names that should not have embeds resolved.
        Subclasses can override this property.
        """
        return []

    @property
    def resolution_type(self) -> Literal["early", "all"]:
        """
        Determines which embeds to resolve. 'early' resolves simple embeds like
        math and uuid. 'all' also resolves 'artifact_content'.
        Defaults to 'early'.
        """
        return "early"

    @property
    def artifact_args(self) -> List[str]:
        """
        Return a list of argument names that should have artifacts pre-loaded.
        The framework will load the artifact before invoking the tool,
        replacing the filename with an Artifact object containing content and metadata.

        Subclasses can override this property to specify which parameters
        should have artifacts pre-loaded.

        Returns:
            List of parameter names to pre-load artifacts for.
        """
        return []

    @property
    def artifact_params(self) -> Dict[str, ArtifactTypeInfo]:
        """
        Return detailed information about artifact parameters.

        This maps parameter names to ArtifactTypeInfo objects that indicate:
        - is_list: Whether the parameter expects a list of artifacts
        - is_optional: Whether the parameter is optional

        Subclasses can override this for fine-grained control over artifact loading.
        Default implementation creates basic info from artifact_args.

        Returns:
            Dict mapping parameter names to ArtifactTypeInfo.
        """
        # Default: create basic info from artifact_args
        return {name: ArtifactTypeInfo(is_artifact=True) for name in self.artifact_args}

    @property
    def ctx_facade_param_name(self) -> Optional[str]:
        """
        Return the parameter name that should receive a ToolContextFacade.

        If not None, the framework will create and inject a ToolContextFacade
        instance for this parameter before invoking the tool.

        Subclasses can override this property to specify the parameter name.
        Default is None (no facade injection).

        Returns:
            Parameter name for ToolContextFacade injection, or None.
        """
        return None

    def _get_declaration(self) -> Optional[Any]:
        """
        Generate the FunctionDeclaration for this dynamic tool.
        This follows the same pattern as PeerAgentTool and MCP tools.
        """
        # Update the tool name to match what the module defines
        self.name = self.tool_name

        return adk_types.FunctionDeclaration(
            name=self.tool_name,
            description=self.tool_description,
            parameters=self.parameters_schema,
        )

    async def _load_artifact_for_param(
        self,
        param_name: str,
        filename: str,
        tool_context: ToolContext,
        log_identifier: str,
    ) -> Artifact:
        """
        Load artifact for a parameter.

        Args:
            param_name: Name of the parameter
            filename: Artifact filename to load (supports filename:version format)
            tool_context: The ADK ToolContext for accessing services
            log_identifier: Prefix for log messages

        Returns:
            An Artifact object containing the content and all metadata

        Raises:
            ValueError: If artifact loading fails
        """
        if not filename:
            log.debug(
                "%s Skipping artifact load for '%s': empty filename",
                log_identifier,
                param_name,
            )
            raise ValueError(f"Empty filename for parameter '{param_name}'")

        try:
            inv_context = tool_context._invocation_context
            artifact_service = inv_context.artifact_service
            app_name = inv_context.app_name
            user_id = inv_context.user_id
            session_id = get_original_session_id(inv_context)

            # Parse filename:version format (rsplit to handle colons in filenames)
            parts = filename.rsplit(":", 1)
            if len(parts) == 2 and parts[1].isdigit():
                filename_base = parts[0]
                version = int(parts[1])
            else:
                filename_base = filename
                version = "latest"

            log.debug(
                "%s Loading artifact '%s' (version=%s) for param '%s'",
                log_identifier,
                filename_base,
                version,
                param_name,
            )

            result = await load_artifact_content_or_metadata(
                artifact_service=artifact_service,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base,
                version=version,
                return_raw_bytes=True,
            )

            if result.get("status") == "success":
                content = result.get("raw_bytes") or result.get("content")
                # Get metadata from result
                loaded_version = result.get("version", 0 if version == "latest" else version)
                mime_type = result.get("mime_type", "application/octet-stream")
                metadata = result.get("metadata", {})

                log.info(
                    "%s Loaded artifact '%s' v%s for param '%s' (%d bytes, %s)",
                    log_identifier,
                    filename_base,
                    loaded_version,
                    param_name,
                    len(content) if content else 0,
                    mime_type,
                )

                return Artifact(
                    content=content,
                    filename=filename_base,
                    version=loaded_version,
                    mime_type=mime_type,
                    metadata=metadata,
                )
            else:
                error_msg = result.get("message", "Unknown error loading artifact")
                raise ValueError(f"Failed to load artifact '{filename}': {error_msg}")

        except ValueError:
            raise
        except Exception as e:
            log.error(
                "%s Failed to load artifact '%s' for param '%s': %s",
                log_identifier,
                filename,
                param_name,
                e,
            )
            raise ValueError(
                f"Artifact pre-load failed for parameter '{param_name}': {e}"
            ) from e

    async def run_async(
        self, *, args: Dict[str, Any], tool_context: ToolContext
    ) -> Dict[str, Any]:
        """
        Asynchronously runs the tool with the given arguments.
        This method resolves embeds in arguments and then delegates the call
        to the abstract _run_async_impl.
        """
        log_identifier = f"[DynamicTool:{self.tool_name}]"
        resolved_kwargs = args.copy()

        types_to_resolve = EARLY_EMBED_TYPES
        if self.resolution_type == "all":
            types_to_resolve = EARLY_EMBED_TYPES.union(LATE_EMBED_TYPES)

        # Unlike ADKToolWrapper, DynamicTools receive all args in a single dict.
        # We iterate through this dict to resolve embeds.
        for key, value in args.items():
            if key in self.raw_string_args and isinstance(value, str):
                log.debug(
                    "%s Skipping embed resolution for raw string kwarg '%s'",
                    log_identifier,
                    key,
                )
            elif isinstance(value, str) and EMBED_DELIMITER_OPEN in value:
                log.debug("%s Resolving embeds for kwarg '%s'", log_identifier, key)
                # Create the resolution context
                if hasattr(tool_context, "_invocation_context"):
                    # Use the invocation context if available
                    invocation_context = tool_context._invocation_context
                else:
                    # Error if no invocation context is found
                    raise RuntimeError(
                        f"{log_identifier} No invocation context found in ToolContext. Cannot resolve embeds."
                    )
                session_context = invocation_context.session
                if not session_context:
                    raise RuntimeError(
                        f"{log_identifier} No session context found in invocation context. Cannot resolve embeds."
                    )
                resolution_context = {
                    "artifact_service": invocation_context.artifact_service,
                    "session_context": {
                        "session_id": get_original_session_id(invocation_context),
                        "user_id": session_context.user_id,
                        "app_name": session_context.app_name,
                    },
                }
                resolved_value, _, _ = await resolve_embeds_in_string(
                    text=value,
                    context=resolution_context,
                    resolver_func=evaluate_embed,
                    types_to_resolve=types_to_resolve,
                    resolution_mode=ResolutionMode.TOOL_PARAMETER,
                    log_identifier=log_identifier,
                    config=self.tool_config,
                )
                resolved_kwargs[key] = resolved_value

        # Pre-load artifacts for Artifact parameters
        artifact_param_info = self.artifact_params
        if artifact_param_info:
            for param_name, param_info in artifact_param_info.items():
                if param_name not in resolved_kwargs:
                    continue

                value = resolved_kwargs[param_name]

                # Handle List[Artifact] - load each filename in the list
                if param_info.is_list:
                    if not value:
                        # Empty list or None - keep as-is
                        continue
                    if not isinstance(value, list):
                        log.warning(
                            "%s Expected list for param '%s' but got %s",
                            log_identifier,
                            param_name,
                            type(value).__name__,
                        )
                        continue

                    loaded_artifacts = []
                    for idx, filename in enumerate(value):
                        if filename and isinstance(filename, str):
                            try:
                                artifact = await self._load_artifact_for_param(
                                    param_name=f"{param_name}[{idx}]",
                                    filename=filename,
                                    tool_context=tool_context,
                                    log_identifier=log_identifier,
                                )
                                loaded_artifacts.append(artifact)
                            except ValueError as e:
                                log.error(
                                    "%s Artifact pre-load failed for %s[%d], returning error: %s",
                                    log_identifier,
                                    param_name,
                                    idx,
                                    e,
                                )
                                return {
                                    "status": "error",
                                    "message": str(e),
                                    "tool_name": self.tool_name,
                                }
                        else:
                            # Non-string entry - skip (shouldn't happen normally)
                            log.warning(
                                "%s Skipping non-string entry at %s[%d]: %s",
                                log_identifier,
                                param_name,
                                idx,
                                type(filename).__name__,
                            )

                    resolved_kwargs[param_name] = loaded_artifacts
                    log.debug(
                        "%s Pre-loaded %d artifacts for list param '%s'",
                        log_identifier,
                        len(loaded_artifacts),
                        param_name,
                    )

                # Handle single Artifact
                elif value and isinstance(value, str):
                    try:
                        artifact = await self._load_artifact_for_param(
                            param_name=param_name,
                            filename=value,
                            tool_context=tool_context,
                            log_identifier=log_identifier,
                        )
                        resolved_kwargs[param_name] = artifact
                    except ValueError as e:
                        # Return error immediately if artifact loading fails
                        log.error(
                            "%s Artifact pre-load failed, returning error: %s",
                            log_identifier,
                            e,
                        )
                        return {
                            "status": "error",
                            "message": str(e),
                            "tool_name": self.tool_name,
                        }

        # Inject ToolContextFacade if the tool expects it
        ctx_param = self.ctx_facade_param_name
        if ctx_param:
            facade = ToolContextFacade(
                tool_context=tool_context,
                tool_config=self.tool_config if isinstance(self.tool_config, dict) else {},
            )
            resolved_kwargs[ctx_param] = facade
            log.debug(
                "%s Injected ToolContextFacade as '%s'",
                log_identifier,
                ctx_param,
            )

        return await self._run_async_impl(
            args=resolved_kwargs, tool_context=tool_context, credential=None
        )

    @abstractmethod
    async def _run_async_impl(
        self, args: dict, tool_context: ToolContext, credential: Optional[str] = None
    ) -> dict:
        """
        Implement the actual tool logic.
        Must return a dictionary response.
        """
        pass


# --- Internal Adapter for Function-Based Tools ---


class _SchemaDetectionResult:
    """Result from schema generation with detected special params."""

    def __init__(self):
        self.schema: Optional[adk_types.Schema] = None
        # Maps param name to ArtifactTypeInfo (includes is_list, is_optional)
        self.artifact_params: Dict[str, ArtifactTypeInfo] = {}
        self.ctx_facade_param_name: Optional[str] = None

    @property
    def artifact_args(self) -> Set[str]:
        """Property returning set of artifact param names."""
        return set(self.artifact_params.keys())


def _get_schema_from_signature(
    func: Callable,
    artifact_args: Optional[Set[str]] = None,
    detection_result: Optional[_SchemaDetectionResult] = None,
) -> adk_types.Schema:
    """
    Introspects a function's signature and generates an ADK Schema for its parameters.

    Args:
        func: The function to introspect
        artifact_args: Optional set to populate with param names that have
                       Artifact type annotation (will be pre-loaded)
        detection_result: Optional result object to populate with all detected params
    """
    sig = inspect.signature(func)
    properties = {}
    required = []

    type_map = {
        str: adk_types.Type.STRING,
        int: adk_types.Type.INTEGER,
        float: adk_types.Type.NUMBER,
        bool: adk_types.Type.BOOLEAN,
        list: adk_types.Type.ARRAY,
        dict: adk_types.Type.OBJECT,
    }

    for param in sig.parameters.values():
        if param.name in ("tool_context", "tool_config", "kwargs", "self", "cls"):
            continue

        param_type = param.annotation
        is_optional = False

        # Handle Optional[T] which is Union[T, None]
        origin = get_origin(param_type)
        args = get_args(param_type)
        if origin is Union and type(None) in args:
            is_optional = True
            # Get the actual type from Union[T, None]
            param_type = next((t for t in args if t is not type(None)), Any)

        # Check for ToolContextFacade - exclude from schema (injected by framework)
        if _is_tool_context_facade_param(param_type):
            if detection_result is not None:
                detection_result.ctx_facade_param_name = param.name
            log.debug(
                "Detected ToolContextFacade param '%s' in %s, excluding from schema",
                param.name,
                func.__name__,
            )
            continue  # Don't add to schema - framework injects this

        # Check for Artifact type - translate to appropriate schema for LLM
        # Also check the original annotation for List/Optional detection
        original_annotation = param.annotation
        artifact_type_info = get_artifact_info(original_annotation)

        if artifact_type_info.is_artifact:
            if artifact_args is not None:
                artifact_args.add(param.name)
            if detection_result is not None:
                detection_result.artifact_params[param.name] = artifact_type_info

            if artifact_type_info.is_list:
                # List[Artifact] -> array of strings (filenames)
                log.debug(
                    "Detected List[Artifact] param '%s' in %s, translating to ARRAY of STRING",
                    param.name,
                    func.__name__,
                )
                properties[param.name] = adk_types.Schema(
                    type=adk_types.Type.ARRAY,
                    items=adk_types.Schema(type=adk_types.Type.STRING),
                    nullable=is_optional or artifact_type_info.is_optional,
                )
            else:
                # Single Artifact -> string (filename)
                log.debug(
                    "Detected Artifact param '%s' in %s, translating to STRING",
                    param.name,
                    func.__name__,
                )
                properties[param.name] = adk_types.Schema(
                    type=adk_types.Type.STRING,
                    nullable=is_optional or artifact_type_info.is_optional,
                )
        else:
            adk_type = type_map.get(param_type)
            if not adk_type:
                # Default to string if type is not supported or specified (e.g., Any)
                adk_type = adk_types.Type.STRING
            properties[param.name] = adk_types.Schema(type=adk_type, nullable=is_optional)

        if param.default is inspect.Parameter.empty and not is_optional:
            required.append(param.name)

    return adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties=properties,
        required=required,
    )


class _FunctionAsDynamicTool(DynamicTool):
    """
    Internal adapter to wrap a standard Python function as a DynamicTool.
    """

    def __init__(
        self,
        func: Callable,
        tool_config: Optional[Union[dict, BaseModel]] = None,
        provider_instance: Optional[Any] = None,
    ):
        super().__init__(tool_config=tool_config)
        self._func = func
        self._provider_instance = provider_instance

        # Detect special params during schema generation
        self._detection_result = _SchemaDetectionResult()
        self._schema = _get_schema_from_signature(
            func,
            detection_result=self._detection_result,
        )

        if self._detection_result.artifact_args:
            log.info(
                "[_FunctionAsDynamicTool:%s] Will pre-load artifacts for params: %s",
                func.__name__,
                list(self._detection_result.artifact_args),
            )

        if self._detection_result.ctx_facade_param_name:
            log.info(
                "[_FunctionAsDynamicTool:%s] Will inject ToolContextFacade as '%s'",
                func.__name__,
                self._detection_result.ctx_facade_param_name,
            )

        # Check if the function is an instance method that needs `self`
        self._is_instance_method = False
        sig = inspect.signature(self._func)
        if sig.parameters:
            first_param = next(iter(sig.parameters.values()))
            if first_param.name == "self":
                self._is_instance_method = True

    @property
    def tool_name(self) -> str:
        return self._func.__name__

    @property
    def tool_description(self) -> str:
        return inspect.getdoc(self._func) or ""

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return self._schema

    @property
    def artifact_args(self) -> List[str]:
        """Return the detected Artifact parameters."""
        return list(self._detection_result.artifact_args)

    @property
    def artifact_params(self) -> Dict[str, ArtifactTypeInfo]:
        """Return detailed info about Artifact parameters (including is_list)."""
        return self._detection_result.artifact_params

    @property
    def ctx_facade_param_name(self) -> Optional[str]:
        """Return the detected ToolContextFacade parameter name."""
        return self._detection_result.ctx_facade_param_name

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: ToolContext,
        credential: Optional[str] = None,
    ) -> dict:
        # Inject tool_context and tool_config if the function expects them
        sig = inspect.signature(self._func)
        if "tool_context" in sig.parameters:
            args["tool_context"] = tool_context
        if "tool_config" in sig.parameters:
            args["tool_config"] = self.tool_config

        if self._provider_instance and self._is_instance_method:
            # It's an instance method, call it on the provider instance
            return await self._func(self._provider_instance, **args)
        else:
            # It's a static method or a standalone function
            return await self._func(**args)


# --- Base Class for Tool Providers ---


class DynamicToolProvider(ABC):
    """
    Base class for dynamic tool providers that can generate a list of tools
    programmatically from a single configuration block.
    """

    config_model: Optional[Type[BaseModel]] = None
    _decorated_tools: List[Callable] = []

    @classmethod
    def register_tool(cls, func: Callable) -> Callable:
        """
        A decorator to register a standard async function as a tool.
        The decorated function's signature and docstring will be used to
        create the tool definition.
        """
        # This check is crucial. It runs for each decorated method.
        # If the current class `cls` is using the list from the base class
        # `DynamicToolProvider`, it creates a new, empty list just for `cls`.
        # On subsequent decorator calls for the same `cls`, this condition will
        # be false, and it will append to the existing list.
        if (
            not hasattr(cls, "_decorated_tools")
            or cls._decorated_tools is DynamicToolProvider._decorated_tools
        ):
            cls._decorated_tools = []

        cls._decorated_tools.append(func)
        return func

    def _create_tools_from_decorators(
        self, tool_config: Optional[Union[dict, BaseModel]] = None
    ) -> List[DynamicTool]:
        """
        Internal helper to convert decorated functions into DynamicTool instances.
        """
        tools = []
        for func in self._decorated_tools:
            adapter = _FunctionAsDynamicTool(func, tool_config, provider_instance=self)
            tools.append(adapter)
        return tools

    def get_all_tools_for_framework(
        self, tool_config: Optional[Union[dict, BaseModel]] = None
    ) -> List[DynamicTool]:
        """
        Framework-internal method that automatically combines decorated tools with custom tools.
        This is called by the ADK setup code, not by users.

        Args:
            tool_config: The configuration dictionary from the agent's YAML file.

        Returns:
            A list of all DynamicTool objects (decorated + custom).
        """
        # Get tools from decorators automatically
        decorated_tools = self._create_tools_from_decorators(tool_config)

        # Get custom tools from the user's implementation
        custom_tools = self.create_tools(tool_config)

        return decorated_tools + custom_tools

    @abstractmethod
    def create_tools(self, tool_config: Optional[Union[dict, BaseModel]] = None) -> List[DynamicTool]:
        """
        Generate and return a list of custom DynamicTool instances.

        Note: Tools registered with the @register_tool decorator are automatically
        included by the framework - you don't need to handle them here.

        Args:
            tool_config: The configuration dictionary from the agent's YAML file.

        Returns:
            A list of custom DynamicTool objects (decorated tools are added automatically).
        """
        pass
