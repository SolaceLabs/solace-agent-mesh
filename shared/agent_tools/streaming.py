"""
NDJSON streaming protocol message types for Lambda tool execution.

This module defines the message format used for streaming communication between
Lambda functions (running tools) and SAM (the executor). The protocol uses
Newline-Delimited JSON (NDJSON) where each line is a complete JSON message.

Protocol Overview:
    - Lambda sends status updates as the tool executes
    - SAM consumes the stream and forwards status to the frontend
    - Final message is either 'result' (success) or 'error'

Message Format:
    {"type":"status","payload":{"message":"Processing..."},"timestamp":1704067200.1}
    {"type":"status","payload":{"message":"Almost done..."},"timestamp":1704067201.2}
    {"type":"result","payload":{"tool_result":{...}},"timestamp":1704067202.3}

Example Lambda Stream:
    {"type":"status","payload":{"message":"Starting analysis..."},"timestamp":1704067200.0}
    {"type":"status","payload":{"message":"Loading data..."},"timestamp":1704067200.5}
    {"type":"status","payload":{"message":"Processing 1000 items..."},"timestamp":1704067201.0}
    {"type":"heartbeat","payload":{},"timestamp":1704067211.0}
    {"type":"status","payload":{"message":"Generating results..."},"timestamp":1704067215.0}
    {"type":"result","payload":{"tool_result":{"_schema":"ToolResult",...}},"timestamp":1704067220.0}
"""

import time
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class StreamMessageType(str, Enum):
    """
    Types of messages in the streaming protocol.

    STATUS: Progress update from the tool
    RESULT: Final successful result (contains serialized ToolResult)
    ERROR: Error occurred during execution
    HEARTBEAT: Keep-alive message (sent every 10s if no other activity)
    """
    STATUS = "status"
    RESULT = "result"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class StatusPayload(BaseModel):
    """Payload for status messages."""
    message: str = Field(..., description="Human-readable status message")


class ResultPayload(BaseModel):
    """Payload for result messages."""
    tool_result: Dict[str, Any] = Field(
        ...,
        description="Serialized ToolResult (from ToolResult.to_serializable())"
    )


class ErrorPayload(BaseModel):
    """Payload for error messages."""
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(
        None,
        description="Machine-readable error code"
    )


class HeartbeatPayload(BaseModel):
    """Payload for heartbeat messages (empty)."""
    pass


class StreamMessage(BaseModel):
    """
    A single message in the NDJSON stream.

    Each line in the stream is a JSON-serialized StreamMessage.
    Messages are ordered by timestamp and must end with either
    a 'result' or 'error' message.

    Attributes:
        type: The message type (status, result, error, heartbeat)
        payload: Type-specific payload data
        timestamp: Unix timestamp for ordering

    Usage (Lambda side - sending):
        import json
        from agent_tools.streaming import StreamMessage, StreamMessageType, StatusPayload

        # Send status update
        msg = StreamMessage.status("Processing item 5 of 10...")
        yield json.dumps(msg.model_dump()) + "\\n"

        # Send final result
        msg = StreamMessage.result(tool_result.to_serializable())
        yield json.dumps(msg.model_dump()) + "\\n"

    Usage (SAM side - receiving):
        import json
        from agent_tools.streaming import StreamMessage, StreamMessageType

        async for line in response.aiter_lines():
            msg = StreamMessage.model_validate_json(line)
            if msg.type == StreamMessageType.STATUS:
                facade.send_status(msg.payload["message"])
            elif msg.type == StreamMessageType.RESULT:
                return ToolResult.from_serialized(msg.payload["tool_result"])
    """
    type: StreamMessageType = Field(..., description="Message type")
    payload: Dict[str, Any] = Field(..., description="Type-specific payload")
    timestamp: float = Field(
        default_factory=time.time,
        description="Unix timestamp for ordering"
    )

    @classmethod
    def status(cls, message: str) -> "StreamMessage":
        """
        Create a status message.

        Args:
            message: Human-readable progress message

        Returns:
            StreamMessage with type=STATUS
        """
        return cls(
            type=StreamMessageType.STATUS,
            payload=StatusPayload(message=message).model_dump(),
        )

    @classmethod
    def result(cls, tool_result: Dict[str, Any]) -> "StreamMessage":
        """
        Create a result message with the final ToolResult.

        Args:
            tool_result: Serialized ToolResult (from to_serializable())

        Returns:
            StreamMessage with type=RESULT
        """
        return cls(
            type=StreamMessageType.RESULT,
            payload=ResultPayload(tool_result=tool_result).model_dump(),
        )

    @classmethod
    def error(
        cls,
        error: str,
        error_code: Optional[str] = None,
    ) -> "StreamMessage":
        """
        Create an error message.

        Args:
            error: Human-readable error message
            error_code: Optional machine-readable error code

        Returns:
            StreamMessage with type=ERROR
        """
        return cls(
            type=StreamMessageType.ERROR,
            payload=ErrorPayload(error=error, error_code=error_code).model_dump(),
        )

    @classmethod
    def heartbeat(cls) -> "StreamMessage":
        """
        Create a heartbeat message.

        Heartbeats should be sent every 10 seconds if no other
        messages are being sent, to keep the connection alive.

        Returns:
            StreamMessage with type=HEARTBEAT
        """
        return cls(
            type=StreamMessageType.HEARTBEAT,
            payload={},
        )

    def to_ndjson_line(self) -> str:
        """
        Convert to NDJSON line (JSON + newline).

        Returns:
            JSON string with trailing newline
        """
        import json
        return json.dumps(self.model_dump()) + "\n"
