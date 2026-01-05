"""
Defines the abstract base class for Generic Gateway Adapters.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Generic, Optional, Type, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from a2a.types import AgentCard


from .types import (
    AuthClaims,
    GatewayContext,
    ResponseContext,
    SamDataPart,
    SamError,
    SamFilePart,
    SamTask,
    SamTextPart,
    SamUpdate,
)

T_ExternalInput = TypeVar("T_ExternalInput", bound=Any)
T_PlatformContext = TypeVar("T_PlatformContext", bound=Dict[str, Any])
T_AdapterConfig = TypeVar("T_AdapterConfig", bound=BaseModel)


class GatewayAdapter(
    ABC, Generic[T_ExternalInput, T_PlatformContext, T_AdapterConfig]
):
    """
    Abstract base class for gateway adapter plugins.

    Gateway adapters handle platform-specific communication while the
    GenericGatewayComponent manages A2A protocol complexity.
    """

    ConfigModel: Optional[Type[BaseModel]] = None

    # --- Lifecycle ---
    async def init(self, context: GatewayContext) -> None:
        """
        Initialize the gateway adapter.

        This is where you should:
        - Start platform listeners (WebSocket, HTTP server, stdin reader, etc.)
        - Connect to external services and store the context for later use.
        """
        pass

    async def cleanup(self) -> None:
        """
        Clean up resources on shutdown.

        This is where you should:
        - Stop platform listeners, close connections, and release resources.
        """
        pass

    # --- Authentication ---
    async def extract_auth_claims(
        self,
        external_input: T_ExternalInput,
        endpoint_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[AuthClaims]:
        """
        Extract authentication claims from platform input.

        Return AuthClaims with user info/tokens, or None to use config-based auth.
        """
        return None

    # --- Inbound: Platform -> A2A ---
    @abstractmethod
    async def prepare_task(
        self,
        external_input: T_ExternalInput,
        endpoint_context: Optional[Dict[str, Any]] = None,
    ) -> SamTask:
        """
        Prepare a task from platform input.

        This method is called after authentication succeeds. Convert your
        platform's event format into a SamTask with parts.
        """
        pass

    # --- Outbound: A2A -> Platform ---
    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """
        Handle an update from the agent (batch handler).

        By default, this method dispatches to individual part handlers.
        Override for custom batch processing.
        """
        for part in update.parts:
            if isinstance(part, SamTextPart):
                await self.handle_text_chunk(part.text, context)
            elif isinstance(part, SamFilePart):
                await self.handle_file(part, context)
            elif isinstance(part, SamDataPart):
                # Check for special data part types that have their own handlers
                if part.data.get("type") == "agent_progress_update":
                    status_text = part.data.get("status_text")
                    if status_text:
                        await self.handle_status_update(status_text, context)
                else:
                    # Fallback to the generic data part handler
                    await self.handle_data_part(part, context)

    async def handle_text_chunk(self, text: str, context: ResponseContext) -> None:
        """
        Handle streaming text chunk from the agent.

        This is called by the default `handle_update` implementation.
        An adapter can override this method to process text parts individually.
        """
        pass

    async def handle_file(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> None:
        """Handle file/artifact from the agent."""
        pass

    async def handle_data_part(
        self, data_part: SamDataPart, context: ResponseContext
    ) -> None:
        """Handle structured data part from the agent."""
        pass

    async def handle_status_update(
        self, status_text: str, context: ResponseContext
    ) -> None:
        """Handle agent status update (progress indicator)."""
        pass

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """Handle task completion notification."""
        pass

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """Handle error from the agent or gateway."""
        pass

    # --- Agent Registry Change Handlers ---

    async def handle_agent_registered(self, agent_card: "AgentCard") -> None:
        """
        Called when a new agent is registered in the agent registry.

        This allows adapters to react to new agents becoming available.
        For example, the MCP adapter can register new tools dynamically.

        Args:
            agent_card: The AgentCard of the newly registered agent
        """
        pass  # Optional - default is no-op

    async def handle_agent_deregistered(self, agent_name: str) -> None:
        """
        Called when an agent is removed from the registry (e.g., TTL expiry).

        Args:
            agent_name: Name of the agent that was removed
        """
        pass  # Optional - default is no-op
