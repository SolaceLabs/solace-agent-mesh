"""
Assembles response messages from SSE status updates, similar to frontend logic.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class AssembledMessage:
    """Represents the accumulated response message."""

    text_parts: List[str] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    is_complete: bool = False
    is_error: bool = False
    error_message: Optional[str] = None
    task_id: Optional[str] = None
    context_id: Optional[str] = None
    status_text: Optional[str] = None

    @property
    def text(self) -> str:
        """Get the full accumulated text."""
        return "".join(self.text_parts)


class MessageAssembler:
    """
    Accumulates text parts from status updates to build the complete response.
    Mirrors the frontend's ChatProvider logic for message assembly.
    """

    def __init__(self):
        self._text_parts: List[str] = []
        self._last_text_length: int = 0
        self._artifacts: List[Dict[str, Any]] = []
        self._is_complete = False
        self._is_error = False
        self._error_message: Optional[str] = None
        self._task_id: Optional[str] = None
        self._context_id: Optional[str] = None
        self._status_text: Optional[str] = None

    def process_event(self, event_type: str, data: Dict[str, Any]) -> tuple[AssembledMessage, Optional[str]]:
        """
        Process an SSE event and update the assembled message.

        Args:
            event_type: The SSE event type (status_update, artifact_update, final_response, error)
            data: The JSON-RPC response data

        Returns:
            Tuple of (current state of assembled message, new text to print if any)
        """
        new_text = None

        # Handle RPC errors
        if "error" in data and data["error"]:
            self._is_error = True
            self._error_message = data["error"].get("message", "Unknown error")
            self._is_complete = True
            return self.get_message(), f"\nError: {self._error_message}"

        result = data.get("result", {})
        kind = result.get("kind")

        if kind == "status-update":
            new_text = self._process_status_update(result)
        elif kind == "artifact-update":
            self._process_artifact_update(result)
        elif kind == "task":
            new_text = self._process_final_task(result)

        return self.get_message(), new_text

    def _process_status_update(self, result: Dict[str, Any]) -> Optional[str]:
        """Process a status-update event. Returns new text to print if any."""
        self._task_id = result.get("taskId")
        self._context_id = result.get("contextId")

        status = result.get("status", {})
        message = status.get("message", {})
        parts = message.get("parts", [])

        new_text_parts = []

        for part in parts:
            kind = part.get("kind")

            if kind == "text":
                text = part.get("text", "")
                if text:
                    self._text_parts.append(text)
                    new_text_parts.append(text)

            elif kind == "data":
                # Handle various data part types
                data = part.get("data", {})
                data_type = data.get("type") if isinstance(data, dict) else None

                if data_type == "agent_progress_update":
                    self._status_text = data.get("status_text", "Processing...")

                elif data_type == "artifact_creation_progress":
                    # Track artifact progress
                    filename = data.get("filename")
                    artifact_status = data.get("status")
                    if filename:
                        self._update_artifact_progress(filename, artifact_status, data)

        # Check if this is the final status update
        if result.get("final"):
            self._is_complete = True

        if new_text_parts:
            return "".join(new_text_parts)
        return None

    def _update_artifact_progress(self, filename: str, status: str, data: Dict[str, Any]):
        """Update artifact tracking."""
        existing = next((a for a in self._artifacts if a.get("filename") == filename), None)

        if existing:
            existing["status"] = status
            if data.get("bytes_transferred"):
                existing["bytes_transferred"] = data["bytes_transferred"]
            if data.get("mime_type"):
                existing["mime_type"] = data["mime_type"]
            if data.get("description"):
                existing["description"] = data["description"]
        else:
            self._artifacts.append({
                "filename": filename,
                "status": status,
                "bytes_transferred": data.get("bytes_transferred", 0),
                "mime_type": data.get("mime_type"),
                "description": data.get("description"),
            })

    def _process_artifact_update(self, result: Dict[str, Any]):
        """Process an artifact-update event."""
        artifact = result.get("artifact", {})
        if artifact:
            filename = artifact.get("name")
            if filename:
                existing = next((a for a in self._artifacts if a.get("filename") == filename), None)
                if existing:
                    existing.update(artifact)
                else:
                    self._artifacts.append({
                        "filename": filename,
                        **artifact,
                    })

    def _process_final_task(self, result: Dict[str, Any]) -> Optional[str]:
        """Process the final task response. Returns new text to print if any."""
        self._task_id = result.get("id")
        self._context_id = result.get("contextId")
        self._is_complete = True

        # Check for error state
        status = result.get("status", {})
        state = status.get("state")

        if state == "failed":
            self._is_error = True
            message = status.get("message", {})
            parts = message.get("parts", [])

            for part in parts:
                if part.get("kind") == "text":
                    self._error_message = part.get("text")
                    return f"\nTask failed: {self._error_message}"

            self._error_message = "Unknown error"
            return f"\nTask failed: {self._error_message}"

        return None

    def get_message(self) -> AssembledMessage:
        """Get the current assembled message state."""
        return AssembledMessage(
            text_parts=list(self._text_parts),
            artifacts=list(self._artifacts),
            is_complete=self._is_complete,
            is_error=self._is_error,
            error_message=self._error_message,
            task_id=self._task_id,
            context_id=self._context_id,
            status_text=self._status_text,
        )

    def reset(self):
        """Reset the assembler for a new message."""
        self._text_parts = []
        self._last_text_length = 0
        self._artifacts = []
        self._is_complete = False
        self._is_error = False
        self._error_message = None
        self._task_id = None
        self._context_id = None
        self._status_text = None
