"""
SandboxToolContextFacade - Tool context interface for sandboxed execution.

This module provides a context facade that tools use inside the bwrap sandbox.
It provides the same interface as ToolContextFacade but uses local filesystem
and named pipes instead of broker communication.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


class SandboxToolContextFacade:
    """
    Provides tool context interface inside the bwrap sandbox.

    This facade gives tools access to:
    - Status message sending (via named pipe)
    - Tool configuration
    - Preloaded artifacts
    - Session/user context

    Unlike the regular ToolContextFacade, this implementation:
    - Writes status messages to a named pipe (worker forwards to Solace)
    - Loads artifacts from the local sandbox filesystem
    - Has no direct broker or artifact service access
    """

    def __init__(
        self,
        status_pipe_path: str,
        tool_config: Dict[str, Any],
        artifact_paths: Dict[str, str],
        output_dir: str,
        user_id: str,
        session_id: str,
    ):
        """
        Initialize the sandbox tool context.

        Args:
            status_pipe_path: Path to the named pipe for status messages
            tool_config: Tool-specific configuration
            artifact_paths: Mapping of parameter names to local artifact file paths
            output_dir: Directory for tool to write output artifacts
            user_id: User ID from the invocation context
            session_id: Session ID from the invocation context
        """
        self._status_pipe_path = status_pipe_path
        self._tool_config = tool_config or {}
        self._artifact_paths = artifact_paths or {}
        self._output_dir = Path(output_dir)
        self._user_id = user_id
        self._session_id = session_id

        # Ensure output directory exists
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def user_id(self) -> str:
        """Get the user ID from the invocation context."""
        return self._user_id

    @property
    def session_id(self) -> str:
        """Get the session ID from the invocation context."""
        return self._session_id

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a tool configuration value.

        Args:
            key: Configuration key to retrieve
            default: Default value if key not found

        Returns:
            The configuration value or default
        """
        return self._tool_config.get(key, default)

    def send_status(self, message: str) -> bool:
        """
        Send a status message to be forwarded to the agent/user.

        Writes the status message to a named pipe. The sandbox worker
        reads from this pipe and forwards messages to Solace.

        Args:
            message: The status message text

        Returns:
            True if the message was sent successfully, False otherwise
        """
        if not self._status_pipe_path:
            log.debug("No status pipe configured, skipping status: %s", message)
            return False

        try:
            # Write to named pipe (non-blocking open, blocking write)
            with open(self._status_pipe_path, "w") as pipe:
                pipe.write(json.dumps({"status": message}) + "\n")
                pipe.flush()
            return True
        except BrokenPipeError:
            log.warning("Status pipe broken, worker may have stopped reading")
            return False
        except Exception as e:
            log.warning("Failed to send status message: %s", e)
            return False

    def load_artifact(self, param_name: str) -> Optional[bytes]:
        """
        Load a preloaded artifact by its parameter name.

        Artifacts are preloaded by the sandbox worker before execution
        and placed in the input directory.

        Args:
            param_name: The parameter name associated with the artifact

        Returns:
            The artifact content as bytes, or None if not found
        """
        file_path = self._artifact_paths.get(param_name)
        if not file_path:
            log.warning("No artifact found for parameter: %s", param_name)
            return None

        try:
            path = Path(file_path)
            if not path.exists():
                log.warning("Artifact file does not exist: %s", file_path)
                return None
            return path.read_bytes()
        except Exception as e:
            log.error("Failed to load artifact %s: %s", param_name, e)
            return None

    def load_artifact_text(self, param_name: str, encoding: str = "utf-8") -> Optional[str]:
        """
        Load a preloaded artifact as text.

        Args:
            param_name: The parameter name associated with the artifact
            encoding: Text encoding (default: utf-8)

        Returns:
            The artifact content as string, or None if not found
        """
        content = self.load_artifact(param_name)
        if content is None:
            return None
        return content.decode(encoding)

    def save_artifact(
        self,
        filename: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
    ) -> str:
        """
        Save an output artifact.

        The artifact is written to the output directory and will be
        collected by the sandbox worker after execution completes.

        Args:
            filename: Name for the artifact file
            content: The artifact content
            mime_type: MIME type (used for metadata, not stored in file)

        Returns:
            The local file path where the artifact was saved
        """
        file_path = self._output_dir / filename
        file_path.write_bytes(content)
        log.debug("Saved output artifact: %s (%d bytes)", filename, len(content))
        return str(file_path)

    def save_artifact_text(
        self,
        filename: str,
        content: str,
        encoding: str = "utf-8",
        mime_type: str = "text/plain",
    ) -> str:
        """
        Save a text output artifact.

        Args:
            filename: Name for the artifact file
            content: The text content
            encoding: Text encoding (default: utf-8)
            mime_type: MIME type (default: text/plain)

        Returns:
            The local file path where the artifact was saved
        """
        return self.save_artifact(filename, content.encode(encoding), mime_type)

    def list_artifacts(self) -> Dict[str, str]:
        """
        List all available preloaded artifacts.

        Returns:
            Dict mapping parameter names to file paths
        """
        return dict(self._artifact_paths)

    def list_output_artifacts(self) -> list[str]:
        """
        List all output artifacts created so far.

        Returns:
            List of filenames in the output directory
        """
        if not self._output_dir.exists():
            return []
        return [f.name for f in self._output_dir.iterdir() if f.is_file()]
