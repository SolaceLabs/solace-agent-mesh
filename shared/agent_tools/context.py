"""
Abstract base class for tool contexts.

This module defines the ToolContextBase interface that both SAM's ToolContextFacade
and Lambda's LambdaToolContext implement. Tools should type-hint their context
parameter as ToolContextBase to work in both environments.

Example usage:
    from agent_tools import ToolContextBase, ToolResult, Artifact

    async def my_tool(
        input_file: Artifact,
        ctx: ToolContextBase,
    ) -> ToolResult:
        # Send status updates - works in both SAM and Lambda
        ctx.send_status("Loading data...")

        # Access context properties
        print(f"Session: {ctx.session_id}, User: {ctx.user_id}")

        # Get tool configuration
        max_items = ctx.get_config("max_items", default=100)

        # Process and return
        content = input_file.as_text()
        result = process(content, max_items)
        return ToolResult.ok("Done", data={"summary": result})
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ToolContextBase(ABC):
    """
    Abstract base class for tool contexts.

    This interface is implemented by:
    - ToolContextFacade: SAM implementation that uses host_component for status updates
    - LambdaToolContext: Lambda implementation that streams status via NDJSON

    Tools should type-hint their context parameter as ToolContextBase to
    work seamlessly in both local SAM execution and Lambda execution.

    Properties:
        session_id: The current session ID
        user_id: The current user ID

    Methods:
        send_status(message): Send a text status update to the frontend
        get_config(key, default): Get a tool configuration value
    """

    @property
    @abstractmethod
    def session_id(self) -> str:
        """
        Get the current session ID.

        Returns:
            The session identifier for this tool invocation.
        """
        ...

    @property
    @abstractmethod
    def user_id(self) -> str:
        """
        Get the current user ID.

        Returns:
            The user identifier for this tool invocation.
        """
        ...

    @abstractmethod
    def send_status(self, message: str) -> bool:
        """
        Send a simple text status update to the frontend.

        This is the primary way for tools to communicate progress during
        long-running operations. The message will appear in the UI as
        a progress indicator.

        In SAM (ToolContextFacade):
            Uses host_component.publish_data_signal_from_thread()

        In Lambda (LambdaToolContext):
            Writes to the streaming response queue (NDJSON format)

        Args:
            message: Human-readable progress message (e.g., "Analyzing data...",
                    "Processing file 3 of 10...", "Fetching results...")

        Returns:
            True if the update was successfully scheduled, False otherwise.
            Returns False if the context is not available (e.g., in unit tests).

        Example:
            async def my_tool(data: str, ctx: ToolContextBase) -> ToolResult:
                ctx.send_status("Starting analysis...")
                # ... do work ...
                ctx.send_status("Processing step 2...")
                # ... more work ...
                ctx.send_status("Almost done...")
                return ToolResult.ok("Complete")
        """
        ...

    @abstractmethod
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the tool configuration.

        Tool configuration is set in the agent YAML config and passed
        to the tool at invocation time.

        Args:
            key: The configuration key to look up
            default: Default value if key is not found

        Returns:
            The configuration value or the default

        Example:
            # In agent config YAML:
            # tools:
            #   - name: my_tool
            #     tool_config:
            #       max_retries: 3
            #       timeout_seconds: 60

            max_retries = ctx.get_config("max_retries", default=1)
            timeout = ctx.get_config("timeout_seconds", default=30)
        """
        ...

    # Optional methods that implementations may provide
    # These are not abstract because not all implementations support them

    @property
    def state(self) -> Dict[str, Any]:
        """
        Get the tool context state dictionary.

        This provides access to shared state across tool invocations.
        Note: In Lambda execution, state is local to the invocation.

        Returns:
            State dictionary (empty dict if not available)
        """
        return {}

    @property
    def a2a_context(self) -> Optional[Dict[str, Any]]:
        """
        Get the A2A context for this request.

        The A2A context contains routing information needed for advanced
        signal types. May be None in Lambda or test contexts.

        Returns:
            A2A context dictionary or None
        """
        return None
