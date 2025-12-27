"""
Provides a clean, simplified interface for tool authors to access context and artifacts.

The ToolContextFacade hides all the boilerplate of extracting session info,
accessing the artifact service, and managing context from the raw ADK ToolContext.

Example usage:
    from solace_agent_mesh.agent.utils import ToolContextFacade
    from solace_agent_mesh.agent.tools import ToolResult, DataObject

    async def my_tool(filename: str, ctx: ToolContextFacade) -> ToolResult:
        # Load artifact - no boilerplate!
        data = await ctx.load_artifact(filename, as_text=True)

        # Access context properties
        print(f"User: {ctx.user_id}, Session: {ctx.session_id}")

        # Process and return
        result = process(data)
        return ToolResult.ok(
            "Done",
            data_objects=[DataObject(name="output.json", content=result)]
        )
"""

import logging
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from google.adk.tools import ToolContext

from .artifact_helpers import load_artifact_content_or_metadata
from .context_helpers import get_original_session_id

if TYPE_CHECKING:
    from google.adk.artifacts import BaseArtifactService

log = logging.getLogger(__name__)


class ToolContextFacade:
    """
    A simplified, read-only interface for tool authors to access context and artifacts.

    This facade provides:
    - Easy access to session/user/app context
    - Simplified artifact loading (content and metadata)
    - Artifact listing
    - Tool configuration access

    Note: This facade is intentionally read-only for artifact operations.
    All artifact saving should be done through the ToolResult/DataObject pattern,
    which provides a single, clear path for artifact creation.
    """

    def __init__(
        self,
        tool_context: ToolContext,
        tool_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the facade.

        Args:
            tool_context: The raw ADK ToolContext
            tool_config: Optional tool-specific configuration dict
        """
        self._ctx = tool_context
        self._tool_config = tool_config or {}

        # Cache context values for efficiency
        self._session_id: Optional[str] = None
        self._user_id: Optional[str] = None
        self._app_name: Optional[str] = None
        self._artifact_service: Optional["BaseArtifactService"] = None

    def _ensure_context(self) -> None:
        """Extract and cache context values from the invocation context."""
        if self._session_id is not None:
            return  # Already cached

        try:
            inv_context = self._ctx._invocation_context
            self._artifact_service = inv_context.artifact_service
            self._app_name = inv_context.app_name
            self._user_id = inv_context.user_id
            self._session_id = get_original_session_id(inv_context)
        except AttributeError as e:
            log.warning(
                "[ToolContextFacade] Could not extract context: %s", e
            )
            # Set defaults to avoid repeated attempts
            self._session_id = ""
            self._user_id = ""
            self._app_name = ""

    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        self._ensure_context()
        return self._session_id or ""

    @property
    def user_id(self) -> str:
        """Get the current user ID."""
        self._ensure_context()
        return self._user_id or ""

    @property
    def app_name(self) -> str:
        """Get the application name."""
        self._ensure_context()
        return self._app_name or ""

    @property
    def raw_tool_context(self) -> ToolContext:
        """
        Get the underlying ADK ToolContext.

        Use this escape hatch when you need access to ADK-specific features
        not exposed by the facade.
        """
        return self._ctx

    @property
    def state(self) -> Dict[str, Any]:
        """
        Get the tool context state dictionary.

        This provides access to shared state across tool invocations.
        """
        return self._ctx.state

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

    async def load_artifact(
        self,
        filename: str,
        version: Union[int, str] = "latest",
        as_text: bool = False,
    ) -> Union[bytes, str]:
        """
        Load artifact content from the artifact store.

        Args:
            filename: The artifact filename to load
            version: Version to load ("latest" or specific version number)
            as_text: If True, decode bytes to string (UTF-8)

        Returns:
            The artifact content as bytes, or as string if as_text=True

        Raises:
            ValueError: If the artifact cannot be loaded
            FileNotFoundError: If the artifact does not exist
        """
        self._ensure_context()

        if not self._artifact_service:
            raise ValueError("Artifact service not available in context")

        log_id = f"[ToolContextFacade:load_artifact:{filename}]"

        result = await load_artifact_content_or_metadata(
            artifact_service=self._artifact_service,
            app_name=self._app_name,
            user_id=self._user_id,
            session_id=self._session_id,
            filename=filename,
            version=version,
            return_raw_bytes=True,
        )

        status = result.get("status")
        if status == "not_found":
            raise FileNotFoundError(
                f"Artifact '{filename}' not found: {result.get('message')}"
            )
        elif status != "success":
            raise ValueError(
                f"Failed to load artifact '{filename}': {result.get('message')}"
            )

        content = result.get("raw_bytes")
        if content is None:
            # Fallback for text content returned directly
            content = result.get("content", b"")
            if isinstance(content, str):
                content = content.encode("utf-8")

        log.debug(
            "%s Loaded %d bytes (version: %s)",
            log_id,
            len(content) if content else 0,
            result.get("version"),
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
            version: Version to load metadata for ("latest" or specific version)

        Returns:
            Dictionary containing artifact metadata (mime_type, size_bytes,
            description, schema, etc.)

        Raises:
            ValueError: If metadata cannot be loaded
            FileNotFoundError: If the artifact does not exist
        """
        self._ensure_context()

        if not self._artifact_service:
            raise ValueError("Artifact service not available in context")

        result = await load_artifact_content_or_metadata(
            artifact_service=self._artifact_service,
            app_name=self._app_name,
            user_id=self._user_id,
            session_id=self._session_id,
            filename=filename,
            version=version,
            load_metadata_only=True,
        )

        status = result.get("status")
        if status == "not_found":
            raise FileNotFoundError(
                f"Artifact '{filename}' not found: {result.get('message')}"
            )
        elif status != "success":
            raise ValueError(
                f"Failed to load metadata for '{filename}': {result.get('message')}"
            )

        metadata = result.get("metadata", {})
        metadata["version"] = result.get("version")
        return metadata

    async def list_artifacts(self) -> List[str]:
        """
        List all artifact filenames in the current session.

        Returns:
            List of artifact filenames (excluding metadata files)

        Raises:
            ValueError: If artifacts cannot be listed
        """
        self._ensure_context()

        if not self._artifact_service:
            raise ValueError("Artifact service not available in context")

        try:
            list_keys_method = getattr(self._artifact_service, "list_artifact_keys")
            keys = await list_keys_method(
                app_name=self._app_name,
                user_id=self._user_id,
                session_id=self._session_id,
            )

            # Filter out metadata files
            return [k for k in keys if not k.endswith(".metadata.json")]

        except Exception as e:
            log.error("[ToolContextFacade] Failed to list artifacts: %s", e)
            raise ValueError(f"Failed to list artifacts: {e}") from e

    async def artifact_exists(self, filename: str) -> bool:
        """
        Check if an artifact exists in the current session.

        Args:
            filename: The artifact filename to check

        Returns:
            True if the artifact exists, False otherwise
        """
        try:
            artifacts = await self.list_artifacts()
            return filename in artifacts
        except ValueError:
            return False

    def __repr__(self) -> str:
        self._ensure_context()
        return (
            f"ToolContextFacade(app={self._app_name}, "
            f"user={self._user_id}, session={self._session_id})"
        )
