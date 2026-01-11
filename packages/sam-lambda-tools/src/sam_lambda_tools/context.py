"""
Lambda-side implementation of ToolContextBase.

This module provides LambdaToolContext, which implements the ToolContextBase
interface for Lambda execution. Status updates are sent via an asyncio Queue
that is consumed by the streaming response handler.

Example usage:
    from sam_lambda_tools.context import LambdaToolContext

    # Created by LambdaToolHandler, not directly by tools
    ctx = LambdaToolContext(
        session_id="sess-123",
        user_id="user-456",
        tool_config={"max_items": 100},
        stream_queue=queue,
    )

    # Tool uses it like any ToolContextBase
    ctx.send_status("Processing...")
    max_items = ctx.get_config("max_items", default=50)
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from agent_tools import ToolContextBase, StreamMessage

log = logging.getLogger(__name__)


class LambdaToolContext(ToolContextBase):
    """
    Tool context implementation for Lambda execution.

    This class implements ToolContextBase, allowing tools written for SAM
    to run in Lambda without modification. Status updates are sent via
    an asyncio Queue that is consumed by the FastAPI streaming response.

    Attributes:
        session_id: The session ID from the invocation context
        user_id: The user ID from the invocation context
        tool_config: Tool-specific configuration dictionary
        stream_queue: Queue for sending status updates to the stream

    Note:
        Unlike ToolContextFacade, this context does NOT support:
        - load_artifact() - artifacts are pre-loaded and passed as parameters
        - list_artifacts() - no artifact store access in Lambda
        - artifact_exists() - no artifact store access in Lambda
        - send_signal() - only simple status messages via streaming

        For artifact operations, tools should use Artifact parameters which
        are pre-loaded by SAM before Lambda invocation.
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        tool_config: Dict[str, Any],
        stream_queue: asyncio.Queue,
        app_name: str = "",
    ):
        """
        Initialize the Lambda tool context.

        Args:
            session_id: Session ID from the SAM invocation
            user_id: User ID from the SAM invocation
            tool_config: Tool-specific configuration
            stream_queue: Queue for sending streaming messages
            app_name: Application name (optional)
        """
        self._session_id = session_id
        self._user_id = user_id
        self._app_name = app_name
        self._tool_config = tool_config
        self._stream_queue = stream_queue
        self._state: Dict[str, Any] = {}

    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        return self._session_id

    @property
    def user_id(self) -> str:
        """Get the current user ID."""
        return self._user_id

    @property
    def app_name(self) -> str:
        """Get the application name."""
        return self._app_name

    @property
    def state(self) -> Dict[str, Any]:
        """
        Get the tool context state dictionary.

        Note: In Lambda, state is local to the invocation and not
        shared across invocations.
        """
        return self._state

    @property
    def a2a_context(self) -> Optional[Dict[str, Any]]:
        """
        Get the A2A context.

        Note: A2A context is not available in Lambda execution.
        """
        return None

    def send_status(self, message: str) -> bool:
        """
        Send a status update to the streaming response.

        This creates a StreamMessage and puts it in the queue for the
        FastAPI streaming response to consume.

        Args:
            message: Human-readable status message

        Returns:
            True if the message was queued successfully, False if queue is full
        """
        try:
            msg = StreamMessage.status(message)
            self._stream_queue.put_nowait(msg)
            log.debug("[LambdaToolContext] Status queued: %s", message)
            return True
        except asyncio.QueueFull:
            log.warning(
                "[LambdaToolContext] Queue full, status dropped: %s", message
            )
            return False

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the tool configuration.

        Args:
            key: The configuration key to look up
            default: Default value if key is not found

        Returns:
            The configuration value or the default
        """
        return self._tool_config.get(key, default)

    def __repr__(self) -> str:
        return (
            f"LambdaToolContext(session={self._session_id}, "
            f"user={self._user_id})"
        )
