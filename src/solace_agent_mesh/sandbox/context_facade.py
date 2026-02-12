"""
SandboxToolContextFacade - Tool context interface for sandboxed execution.

This module provides a context facade that tools use inside the bwrap sandbox.
It matches the public API of ToolContextFacade (from agent/utils) so that the
same tool code can run in both in-process and sandbox environments.

Key differences from ToolContextFacade:
- Status messages go via named pipe (worker forwards to Solace)
- Artifacts are loaded from the local sandbox filesystem (preloaded by worker)
- No direct broker or artifact service access
- send_signal() is a no-op (worker only supports text status via pipe)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

log = logging.getLogger(__name__)


class SandboxToolContextFacade:
    """
    Provides the same tool-facing interface as ToolContextFacade, backed by
    local filesystem and named pipes instead of broker communication.

    Portable API (matches ToolContextFacade):
        - session_id, user_id, app_name properties
        - get_config(key, default)
        - async load_artifact(filename, version, as_text)
        - async load_artifact_metadata(filename, version)
        - async list_artifacts() -> List[str]
        - async artifact_exists(filename) -> bool
        - send_status(message) -> bool
        - send_signal(signal_data) -> bool
        - state property
        - raw_tool_context property

    Legacy methods (backward compat for sandbox-only tools):
        - save_artifact(), save_artifact_text()
        - list_output_artifacts()
    """

    def __init__(
        self,
        *,
        status_pipe_path: str,
        tool_config: Dict[str, Any],
        artifacts: Dict[str, Dict[str, Any]],
        output_dir: str,
        user_id: str,
        session_id: str,
        app_name: str = "",
        # Legacy support: artifact_paths for old-style tools
        artifact_paths: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the sandbox tool context.

        Args:
            status_pipe_path: Path to the named pipe for status messages
            tool_config: Tool-specific configuration dict
            artifacts: Mapping of filename to artifact info dict containing:
                       {"local_path": str, "mime_type": str, "version": int}
            output_dir: Directory for tool to write output artifacts
            user_id: User ID from the invocation context
            session_id: Session ID from the invocation context
            app_name: Application name from the invocation context
            artifact_paths: Legacy mapping of param_name to local path (backward compat)
        """
        self._status_pipe_path = status_pipe_path
        self._tool_config = tool_config or {}
        self._output_dir = Path(output_dir)
        self._user_id = user_id
        self._session_id = session_id
        self._app_name = app_name
        self._state: Dict[str, Any] = {}

        # Artifacts indexed by filename for the portable API
        self._artifacts: Dict[str, Dict[str, Any]] = artifacts or {}

        # Legacy artifact_paths (param_name → local_path) for backward compat
        self._artifact_paths: Dict[str, str] = artifact_paths or {}

        # Ensure output directory exists
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Properties (matching ToolContextFacade)
    # -------------------------------------------------------------------------

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
    def raw_tool_context(self):
        """Get the underlying ADK ToolContext. Not available in sandbox."""
        return None

    @property
    def state(self) -> Dict[str, Any]:
        """Get the tool context state dictionary."""
        return self._state

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Artifact Operations (async, matching ToolContextFacade)
    # -------------------------------------------------------------------------

    async def load_artifact(
        self,
        filename: str,
        version: Union[int, str] = "latest",
        as_text: bool = False,
    ) -> Union[bytes, str]:
        """
        Load artifact content from the preloaded artifacts.

        Args:
            filename: The artifact filename to load
            version: Version to load (ignored in sandbox — only preloaded version available)
            as_text: If True, decode bytes to string (UTF-8)

        Returns:
            The artifact content as bytes, or as string if as_text=True

        Raises:
            FileNotFoundError: If the artifact does not exist
            ValueError: If the artifact cannot be loaded
        """
        info = self._artifacts.get(filename)
        if not info:
            raise FileNotFoundError(
                f"Artifact '{filename}' not found in preloaded artifacts"
            )

        local_path = Path(info["local_path"])
        if not local_path.exists():
            raise FileNotFoundError(
                f"Artifact file not found on disk: {local_path}"
            )

        try:
            content = local_path.read_bytes()
        except Exception as e:
            raise ValueError(f"Failed to read artifact '{filename}': {e}") from e

        log.debug(
            "Loaded artifact: %s (%d bytes, version=%s)",
            filename,
            len(content),
            info.get("version", "?"),
        )

        if as_text:
            return content.decode("utf-8") if isinstance(content, bytes) else content
        return content

    async def load_artifact_metadata(
        self,
        filename: str,
        version: Union[int, str] = "latest",
    ) -> Dict[str, Any]:
        """
        Load artifact metadata without loading the content.

        Args:
            filename: The artifact filename
            version: Version (ignored in sandbox)

        Returns:
            Dictionary containing artifact metadata

        Raises:
            FileNotFoundError: If the artifact does not exist
        """
        info = self._artifacts.get(filename)
        if not info:
            raise FileNotFoundError(
                f"Artifact '{filename}' not found in preloaded artifacts"
            )

        local_path = Path(info["local_path"])
        size_bytes = local_path.stat().st_size if local_path.exists() else 0

        return {
            "mime_type": info.get("mime_type", "application/octet-stream"),
            "size_bytes": size_bytes,
            "version": info.get("version", 0),
        }

    async def list_artifacts(self) -> List[str]:
        """
        List all artifact filenames available in this session.

        Returns:
            List of artifact filenames
        """
        return list(self._artifacts.keys())

    async def artifact_exists(self, filename: str) -> bool:
        """
        Check if an artifact exists in the preloaded artifacts.

        Args:
            filename: The artifact filename to check

        Returns:
            True if the artifact exists, False otherwise
        """
        return filename in self._artifacts

    # -------------------------------------------------------------------------
    # Status Update Methods (matching ToolContextFacade)
    # -------------------------------------------------------------------------

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

    def send_signal(self, signal_data: Any, skip_buffer_flush: bool = False) -> bool:
        """
        Send a custom signal/data update. Not supported in sandbox.

        Returns:
            False (not supported in sandbox environment)
        """
        log.debug("send_signal not supported in sandbox, ignoring")
        return False

    # -------------------------------------------------------------------------
    # Legacy Methods (backward compat for sandbox-only tools)
    # -------------------------------------------------------------------------

    def load_artifact_by_param(self, param_name: str) -> Optional[bytes]:
        """
        Load a preloaded artifact by its parameter name (legacy API).

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

    def save_artifact(
        self,
        filename: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
    ) -> str:
        """
        Save an output artifact to the output directory (legacy API).

        Prefer using ToolResult with DataObject for portable tools.

        Args:
            filename: Name for the artifact file
            content: The artifact content
            mime_type: MIME type

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
        Save a text output artifact (legacy API).

        Args:
            filename: Name for the artifact file
            content: The text content
            encoding: Text encoding (default: utf-8)
            mime_type: MIME type (default: text/plain)

        Returns:
            The local file path where the artifact was saved
        """
        return self.save_artifact(filename, content.encode(encoding), mime_type)

    def list_output_artifacts(self) -> list[str]:
        """
        List all output artifacts created so far (legacy API).

        Returns:
            List of filenames in the output directory
        """
        if not self._output_dir.exists():
            return []
        return [f.name for f in self._output_dir.iterdir() if f.is_file()]

    def __repr__(self) -> str:
        return (
            f"SandboxToolContextFacade(app={self._app_name}, "
            f"user={self._user_id}, session={self._session_id})"
        )
