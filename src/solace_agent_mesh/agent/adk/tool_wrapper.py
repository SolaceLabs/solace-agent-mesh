"""
Defines the ADKToolWrapper, a consolidated wrapper for ADK tools.
"""

import logging
import asyncio
import functools
import inspect
from typing import Any, Callable, Dict, List, Optional, Literal, Set

from ...common.utils.embeds import (
    resolve_embeds_in_string,
    evaluate_embed,
    EARLY_EMBED_TYPES,
    LATE_EMBED_TYPES,
    EMBED_DELIMITER_OPEN,
)
from ...common.utils.embeds.types import ResolutionMode
from ..tools.artifact_types import Artifact, is_artifact_type, get_artifact_info, ArtifactTypeInfo
from ..utils.artifact_helpers import load_artifact_content_or_metadata
from ..utils.context_helpers import get_original_session_id
from ..utils.tool_context_facade import ToolContextFacade

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

class ADKToolWrapper:
    """
    A consolidated wrapper for ADK tools that handles:
    1. Preserving original function metadata (__doc__, __signature__) for ADK.
    2. Resolving early-stage embeds in string arguments before execution.
    3. Injecting tool-specific configuration.
    4. Providing a resilient try/except block to catch all execution errors.
    """

    def __init__(
        self,
        original_func: Callable,
        tool_config: Optional[Dict],
        tool_name: str,
        origin: str,
        raw_string_args: Optional[List[str]] = None,
        resolution_type: Literal["early", "all"] = "all",
        artifact_args: Optional[List[str]] = None,
    ):
        self._original_func = original_func
        self._tool_config = tool_config or {}
        self._tool_name = tool_name
        self._resolution_type = resolution_type
        self.origin = origin
        self._raw_string_args = set(raw_string_args) if raw_string_args else set()
        self._is_async = inspect.iscoroutinefunction(original_func)

        self._types_to_resolve = EARLY_EMBED_TYPES

        if self._resolution_type == "all":
            self._types_to_resolve = EARLY_EMBED_TYPES.union(LATE_EMBED_TYPES)

        # Ensure __name__ attribute is always set before functools.update_wrapper
        self.__name__ = tool_name

        try:
            functools.update_wrapper(self, original_func)
        except AttributeError as e:
            log.debug(
                "Could not fully update wrapper for tool '%s': %s. Using fallback attributes.",
                self._tool_name,
                e,
            )
            # Ensure essential attributes are set even if update_wrapper fails
            self.__name__ = tool_name
            self.__doc__ = getattr(original_func, "__doc__", None)

        try:
            self.__code__ = original_func.__code__
            self.__globals__ = original_func.__globals__
            self.__defaults__ = getattr(original_func, "__defaults__", None)
            self.__kwdefaults__ = getattr(original_func, "__kwdefaults__", None)
            self.__closure__ = getattr(original_func, "__closure__", None)
        except AttributeError:
            log.debug(
                "Could not delegate all dunder attributes for tool '%s'. This is normal for some built-in or C-based functions.",
                self._tool_name,
            )

        try:
            self.__signature__ = inspect.signature(original_func)
            self._accepts_tool_config = "tool_config" in self.__signature__.parameters
        except (ValueError, TypeError):
            self.__signature__ = None
            self._accepts_tool_config = False
            log.warning("Could not determine signature for tool '%s'.", self._tool_name)

        # Initialize artifact params from explicit config
        # Maps param name to ArtifactTypeInfo
        self._artifact_params: Dict[str, ArtifactTypeInfo] = {}
        if artifact_args:
            for name in artifact_args:
                self._artifact_params[name] = ArtifactTypeInfo(is_artifact=True)

        # Track if the function expects a ToolContextFacade
        self._ctx_facade_param_name: Optional[str] = None

        # Auto-detect Artifact and ToolContextFacade type annotations
        self._detect_special_params()

    @property
    def _artifact_args(self) -> Set[str]:
        """Property returning set of artifact param names."""
        return set(self._artifact_params.keys())

    def _detect_special_params(self) -> None:
        """
        Detect special parameter types:
        - Artifact / List[Artifact]: Will have artifact pre-loaded
        - ToolContextFacade: Will have facade injected automatically
        """
        if self.__signature__ is None:
            return

        for param_name, param in self.__signature__.parameters.items():
            if param_name in ("tool_context", "tool_config", "kwargs", "self", "cls"):
                continue

            # Check for Artifact (including List[Artifact])
            artifact_type_info = get_artifact_info(param.annotation)
            if artifact_type_info.is_artifact:
                self._artifact_params[param_name] = artifact_type_info
                if artifact_type_info.is_list:
                    log.debug(
                        "[ADKToolWrapper:%s] Detected List[Artifact] param: %s",
                        self._tool_name,
                        param_name,
                    )
                else:
                    log.debug(
                        "[ADKToolWrapper:%s] Detected Artifact param: %s",
                        self._tool_name,
                        param_name,
                    )

            # Check for ToolContextFacade
            if _is_tool_context_facade_param(param.annotation):
                self._ctx_facade_param_name = param_name
                log.debug(
                    "[ADKToolWrapper:%s] Detected ToolContextFacade param: %s",
                    self._tool_name,
                    param_name,
                )

        if self._artifact_params:
            log.info(
                "[ADKToolWrapper:%s] Will pre-load artifacts for params: %s",
                self._tool_name,
                list(self._artifact_params.keys()),
            )

        if self._ctx_facade_param_name:
            log.info(
                "[ADKToolWrapper:%s] Will inject ToolContextFacade as '%s'",
                self._tool_name,
                self._ctx_facade_param_name,
            )

    async def _load_artifact_for_param(
        self,
        param_name: str,
        filename: str,
        tool_context: Any,
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

    async def __call__(self, *args, **kwargs):
        # Allow overriding the context for embed resolution, e.g., when called from a callback
        _override_embed_context = kwargs.pop("_override_embed_context", None)
        log_identifier = f"[ADKToolWrapper:{self._tool_name}]"

        context_for_embeds = _override_embed_context or kwargs.get("tool_context")
        resolved_args = []
        resolved_kwargs = kwargs.copy()

        if context_for_embeds:
            # Resolve positional args
            for arg in args:
                if isinstance(arg, str) and EMBED_DELIMITER_OPEN in arg:
                    resolved_arg, _, _ = await resolve_embeds_in_string(
                        text=arg,
                        context=context_for_embeds,
                        resolver_func=evaluate_embed,
                        types_to_resolve=self._types_to_resolve,
                        resolution_mode=ResolutionMode.TOOL_PARAMETER,
                        log_identifier=log_identifier,
                        config=self._tool_config,
                    )
                    resolved_args.append(resolved_arg)
                else:
                    resolved_args.append(arg)

            for key, value in kwargs.items():
                if key in self._raw_string_args and isinstance(value, str):
                    log.debug(
                        "%s Skipping embed resolution for raw string kwarg '%s'",
                        log_identifier,
                        key,
                    )
                elif isinstance(value, str) and EMBED_DELIMITER_OPEN in value:
                    log.debug("%s Resolving embeds for kwarg '%s'", log_identifier, key)
                    resolved_value, _, _ = await resolve_embeds_in_string(
                        text=value,
                        context=context_for_embeds,
                        resolver_func=evaluate_embed,
                        types_to_resolve=self._types_to_resolve,
                        resolution_mode=ResolutionMode.TOOL_PARAMETER,
                        log_identifier=log_identifier,
                        config=self._tool_config,
                    )
                    resolved_kwargs[key] = resolved_value
        else:
            log.warning(
                "%s ToolContext not found. Skipping embed resolution for all args.",
                log_identifier,
            )
            resolved_args = list(args)

        if self._accepts_tool_config:
            resolved_kwargs["tool_config"] = self._tool_config
        elif self._tool_config:
            log.warning(
                "%s Tool was provided a 'tool_config' but its function signature does not accept it. The config will be ignored.",
                log_identifier,
            )

        # Inject ToolContextFacade if the function expects it
        if self._ctx_facade_param_name and context_for_embeds:
            facade = ToolContextFacade(
                tool_context=context_for_embeds,
                tool_config=self._tool_config,
            )
            resolved_kwargs[self._ctx_facade_param_name] = facade
            log.debug(
                "%s Injected ToolContextFacade as '%s'",
                log_identifier,
                self._ctx_facade_param_name,
            )

        # Pre-load artifacts for Artifact parameters
        if self._artifact_params and context_for_embeds:
            for param_name, param_info in self._artifact_params.items():
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
                                    tool_context=context_for_embeds,
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
                                    "tool_name": self._tool_name,
                                }
                        else:
                            # Non-string entry - skip
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
                            tool_context=context_for_embeds,
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
                            "tool_name": self._tool_name,
                        }

        try:
            if self._is_async:
                return await self._original_func(*resolved_args, **resolved_kwargs)
            else:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None,
                    functools.partial(
                        self._original_func, *resolved_args, **resolved_kwargs
                    ),
                )
        except Exception as e:
            log.exception("%s Tool execution failed: %s", log_identifier, e)
            return {
                "status": "error",
                "message": f"Tool '{self._tool_name}' failed with an unexpected error: {str(e)}",
                "tool_name": self._tool_name,
            }
