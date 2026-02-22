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
from ..tools.artifact_preloading import (
    is_tool_context_facade_param as _is_tool_context_facade_param,
    resolve_artifact_params,
)
from ..utils.tool_context_facade import ToolContextFacade

log = logging.getLogger(__name__)


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

        # Sanitize __signature__ so ADK doesn't see types it can't parse.
        # Replace Artifact annotations with str, remove ToolContextFacade params.
        self._sanitize_signature()

    def _sanitize_signature(self) -> None:
        """Replace Artifact type annotations with str and remove framework-injected
        params (ToolContextFacade) from the exposed signature so that ADK's
        automatic function declaration parser doesn't choke on unknown types."""
        if self.__signature__ is None:
            return

        new_params = []
        for param_name, param in self.__signature__.parameters.items():
            # Remove ToolContextFacade params — they are injected by the framework
            if param_name == self._ctx_facade_param_name:
                continue

            # Replace Artifact annotations with str
            if param_name in self._artifact_params:
                new_param = param.replace(annotation=str)
                new_params.append(new_param)
            else:
                new_params.append(param)

        self.__signature__ = self.__signature__.replace(parameters=new_params)

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
            error = await resolve_artifact_params(
                artifact_params=self._artifact_params,
                resolved_kwargs=resolved_kwargs,
                tool_context=context_for_embeds,
                tool_name=self._tool_name,
                log_identifier=log_identifier,
            )
            if error is not None:
                return error

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
