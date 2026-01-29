"""
Base classes for tool executors.

Tool executors provide an abstraction layer that allows tools to run on different
backends through configuration.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, TYPE_CHECKING

from pydantic import BaseModel, Field
from google.adk.tools import ToolContext

from ..tool_result import ToolResult

if TYPE_CHECKING:
    from ...sac.component import SamAgentComponent

log = logging.getLogger(__name__)


class ToolExecutionResult(BaseModel):
    """
    Result from a tool executor.

    This is the standardized result format that all executors return,
    which is then converted to a ToolResult or dict for the LLM.
    """

    success: bool = Field(
        ...,
        description="Whether the execution was successful",
    )
    data: Any = Field(
        default=None,
        description="Result data from the execution",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed",
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the execution",
    )

    @classmethod
    def ok(cls, data: Any = None, metadata: Optional[Dict[str, Any]] = None) -> "ToolExecutionResult":
        """Create a successful result."""
        return cls(success=True, data=data, metadata=metadata or {})

    @classmethod
    def fail(
        cls,
        error: str,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ToolExecutionResult":
        """Create a failed result."""
        return cls(
            success=False,
            error=error,
            error_code=error_code,
            metadata=metadata or {},
        )


class ToolExecutor(ABC):
    """
    Abstract base class for tool executors.

    Executors handle the actual execution of tool logic on various backends:
    - LocalPythonExecutor: Runs Python functions locally

    Subclasses must implement:
    - executor_type: Property returning the executor type name
    - execute: The main execution method
    - initialize: Called once at agent startup
    - cleanup: Called once at agent shutdown
    """

    @property
    @abstractmethod
    def executor_type(self) -> str:
        """
        Return the executor type identifier.

        Example: "python"
        """
        pass

    @abstractmethod
    async def execute(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> Union[ToolExecutionResult, ToolResult]:
        """
        Execute the tool with the given arguments.

        Args:
            args: The arguments passed to the tool (already resolved)
            tool_context: The ADK ToolContext for accessing services
            tool_config: Tool-specific configuration

        Returns:
            ToolExecutionResult for simple results, or ToolResult for results
            with DataObjects that need artifact handling.
        """
        pass

    async def initialize(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """
        Initialize the executor.

        Called once when the agent starts up. Use this to set up
        connections, validate configuration, etc.

        Args:
            component: The host SamAgentComponent
            executor_config: Executor-specific configuration
        """
        pass

    async def cleanup(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """
        Clean up executor resources.

        Called once when the agent is shutting down.

        Args:
            component: The host SamAgentComponent
            executor_config: Executor-specific configuration
        """
        pass


# Registry for executor types
_EXECUTOR_REGISTRY: Dict[str, type] = {}


def register_executor(executor_type: str):
    """
    Decorator to register an executor class.

    Usage:
        @register_executor("python")
        class LocalPythonExecutor(ToolExecutor):
            ...
    """
    def decorator(cls: type) -> type:
        if not issubclass(cls, ToolExecutor):
            raise TypeError(f"{cls.__name__} must be a subclass of ToolExecutor")
        _EXECUTOR_REGISTRY[executor_type] = cls
        log.debug("Registered executor type '%s': %s", executor_type, cls.__name__)
        return cls
    return decorator


def get_executor_class(executor_type: str) -> Optional[type]:
    """
    Get the executor class for a given type.

    Args:
        executor_type: The executor type identifier (e.g., "python")

    Returns:
        The executor class, or None if not found
    """
    return _EXECUTOR_REGISTRY.get(executor_type)


def create_executor(executor_type: str, **kwargs) -> ToolExecutor:
    """
    Create an executor instance by type.

    Args:
        executor_type: The executor type identifier
        **kwargs: Arguments to pass to the executor constructor

    Returns:
        A ToolExecutor instance

    Raises:
        ValueError: If the executor type is not registered
    """
    executor_class = get_executor_class(executor_type)
    if executor_class is None:
        available = list(_EXECUTOR_REGISTRY.keys())
        raise ValueError(
            f"Unknown executor type '{executor_type}'. Available types: {available}"
        )
    return executor_class(**kwargs)


def list_executor_types() -> list:
    """Return a list of registered executor types."""
    return list(_EXECUTOR_REGISTRY.keys())
