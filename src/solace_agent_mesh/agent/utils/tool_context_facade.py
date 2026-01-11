"""
Provides a clean, simplified interface for tool authors to access context and artifacts.

The ToolContextFacade hides all the boilerplate of extracting session info,
accessing the artifact service, managing context, and sending status updates
from the raw ADK ToolContext.

This class extends ToolContextBase from the shared agent_tools package,
allowing tools to be written against the abstract interface and work in
both SAM and Lambda execution environments.

Example usage:
    from solace_agent_mesh.agent.utils import ToolContextFacade
    from solace_agent_mesh.agent.tools import ToolResult, DataObject

    async def my_tool(filename: str, ctx: ToolContextFacade) -> ToolResult:
        # Send status updates - no boilerplate!
        ctx.send_status("Loading artifact...")

        # Load artifact - no boilerplate!
        data = await ctx.load_artifact(filename, as_text=True)

        # Access context properties
        print(f"User: {ctx.user_id}, Session: {ctx.session_id}")

        # Send progress update
        ctx.send_status("Processing data...")

        # Process and return
        result = process(data)
        return ToolResult.ok(
            "Done",
            data_objects=[DataObject(name="output.json", content=result)]
        )

    # For portable tools, type-hint with ToolContextBase:
    from agent_tools import ToolContextBase

    async def portable_tool(data: str, ctx: ToolContextBase) -> ToolResult:
        ctx.send_status("Working...")  # Works in SAM and Lambda
        return ToolResult.ok("Done")
"""

import logging
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from google.adk.tools import ToolContext

from agent_tools import ToolContextBase

from .artifact_helpers import load_artifact_content_or_metadata
from .context_helpers import get_original_session_id

if TYPE_CHECKING:
    from google.adk.artifacts import BaseArtifactService
    from pydantic import BaseModel

log = logging.getLogger(__name__)


class ToolContextFacade(ToolContextBase):
    """
    A simplified interface for tool authors to access context, artifacts, and status updates.

    This facade provides:
    - Easy access to session/user/app context
    - Simplified artifact loading (content and metadata)
    - Artifact listing
    - Tool configuration access
    - Status update methods for sending progress to the frontend

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
        self._host_component: Optional[Any] = None
        self._host_component_resolved: bool = False

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

    # -------------------------------------------------------------------------
    # Status Update Methods
    # -------------------------------------------------------------------------

    def _ensure_host_component(self) -> Optional[Any]:
        """
        Extract and cache the host component from the invocation context.

        The host component is needed for publishing status updates.
        Returns None if the component cannot be accessed (e.g., in tests).
        """
        if self._host_component_resolved:
            return self._host_component

        self._host_component_resolved = True
        try:
            inv_context = getattr(self._ctx, "_invocation_context", None)
            if inv_context:
                agent = getattr(inv_context, "agent", None)
                if agent:
                    self._host_component = getattr(agent, "host_component", None)
        except Exception as e:
            log.debug(
                "[ToolContextFacade] Could not get host_component: %s", e
            )

        return self._host_component

    @property
    def a2a_context(self) -> Optional[Dict[str, Any]]:
        """
        Get the A2A context for this request.

        The A2A context contains routing information needed for status updates.
        Returns None if not available (e.g., in tests).
        """
        return self._ctx.state.get("a2a_context")

    def send_status(self, message: str) -> bool:
        """
        Send a simple text status update to the frontend.

        This is the easiest way to show progress during long-running tool operations.
        The message will appear in the UI as a progress indicator.

        Args:
            message: Human-readable progress message (e.g., "Analyzing data...",
                    "Processing file 3 of 10...", "Fetching results...")

        Returns:
            True if the update was successfully scheduled, False otherwise.
            Returns False if the context is not available (e.g., in unit tests).

        Example:
            async def my_tool(data: str, ctx: ToolContextFacade) -> ToolResult:
                ctx.send_status("Starting analysis...")
                # ... do work ...
                ctx.send_status("Almost done...")
                return ToolResult.ok("Complete")
        """
        from ...common.data_parts import AgentProgressUpdateData

        host = self._ensure_host_component()
        a2a_ctx = self.a2a_context

        if not host or not a2a_ctx:
            log.debug(
                "[ToolContextFacade] Cannot send status: missing host_component or a2a_context"
            )
            return False

        signal = AgentProgressUpdateData(status_text=message)
        return host.publish_data_signal_from_thread(
            a2a_context=a2a_ctx,
            signal_data=signal,
        )

    def send_signal(
        self,
        signal_data: "BaseModel",
        skip_buffer_flush: bool = False,
    ) -> bool:
        """
        Send a custom signal/data update to the frontend.

        Use this for specialized signals that need structured data beyond
        a simple text message. For simple progress messages, prefer send_status().

        Args:
            signal_data: A Pydantic model instance from solace_agent_mesh.common.data_parts.
                        Common types include:
                        - AgentProgressUpdateData: Simple text status
                        - ArtifactCreationProgressData: Artifact streaming progress
                        - DeepResearchProgressData: Structured research progress
            skip_buffer_flush: If True, skip flushing the output buffer before
                              sending. Usually False for immediate updates.

        Returns:
            True if the update was successfully scheduled, False otherwise.
            Returns False if the context is not available (e.g., in unit tests).

        Example:
            from solace_agent_mesh.common.data_parts import DeepResearchProgressData

            async def research_tool(query: str, ctx: ToolContextFacade) -> ToolResult:
                ctx.send_signal(DeepResearchProgressData(
                    phase="searching",
                    status_text="Searching for sources...",
                    progress_percentage=25,
                    current_iteration=1,
                    total_iterations=3,
                    sources_found=5,
                    elapsed_seconds=10,
                ))
                # ... do work ...
                return ToolResult.ok("Complete")
        """
        host = self._ensure_host_component()
        a2a_ctx = self.a2a_context

        if not host or not a2a_ctx:
            log.debug(
                "[ToolContextFacade] Cannot send signal: missing host_component or a2a_context"
            )
            return False

        return host.publish_data_signal_from_thread(
            a2a_context=a2a_ctx,
            signal_data=signal_data,
            skip_buffer_flush=skip_buffer_flush,
        )

    def __repr__(self) -> str:
        self._ensure_context()
        return (
            f"ToolContextFacade(app={self._app_name}, "
            f"user={self._user_id}, session={self._session_id})"
        )
