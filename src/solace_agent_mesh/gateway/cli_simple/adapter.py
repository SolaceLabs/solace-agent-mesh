"""
Simple CLI Gateway Adapter - Minimal "Hello World" Example

This is the simplest possible gateway adapter implementation,
designed to help you understand the adapter pattern with minimal code.

Features:
- Basic REPL loop
- Plain text output (no fancy formatting)
- Streaming text responses
- Simple status updates
- Artifact info display (no auto-save)

Dependencies: None (pure Python + Pydantic)
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from ..adapter.base import GatewayAdapter
from ..adapter.types import (
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

log = logging.getLogger(__name__)


class SimpleCliAdapterConfig(BaseModel):
    """Configuration for the simple CLI adapter."""

    default_agent_name: str = Field(
        default="default",
        description="Name of the agent to send requests to.",
    )


class SimpleCliAdapter(GatewayAdapter):
    """
    The simplest possible CLI gateway adapter.

    Perfect for learning how to build a gateway adapter.
    Uses only Python standard library (no Rich, no prompt_toolkit).
    """

    ConfigModel = SimpleCliAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.running = False
        self.processing = False  # Track if agent is processing
        self.session_id = f"cli-simple-{int(datetime.now().timestamp() * 1000)}"

    async def init(self, context: GatewayContext) -> None:
        """Initialize and start the REPL."""
        self.context = context
        log.info("Starting Simple CLI Gateway...")

        # Start REPL in background
        asyncio.create_task(self._run_repl())

    async def cleanup(self) -> None:
        """Stop the gateway."""
        self.running = False
        log.info("Simple CLI Gateway stopped.")

    async def _run_repl(self):
        """Simple REPL loop."""
        self.running = True

        print("\n=== SAM Simple CLI Gateway ===")
        print("Type your message and press Enter.")
        print("Type /exit or press Ctrl+D to quit.\n")

        while self.running:
            try:
                # Wait until previous task completes before showing prompt
                while self.processing:
                    await asyncio.sleep(0.1)

                # Read input (blocking, so run in thread)
                user_input = await asyncio.to_thread(input, "sam> ")
                user_input = user_input.strip()

                if not user_input:
                    continue

                if user_input == "/exit":
                    break

                # Mark as processing and send to agent
                self.processing = True
                await self._send_to_agent(user_input)

            except EOFError:
                # Ctrl+D
                break
            except Exception as e:
                log.exception(f"Error in REPL: {e}")
                print(f"Error: {e}")
                self.processing = False  # Reset on error

        print("\nGoodbye!\n")
        self.running = False

    async def _send_to_agent(self, message: str):
        """Send message to the agent."""
        try:
            external_input = {
                "text": message,
                "session_id": self.session_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.context.handle_external_input(external_input)
        except Exception as e:
            log.exception(f"Error sending to agent: {e}")
            print(f"Error: {e}")

    # --- Required GatewayAdapter Methods ---

    async def extract_auth_claims(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        """
        Extract authentication info from input.
        For this simple CLI, we just use a default user.
        """
        return AuthClaims(id="cli_user", source="cli")

    async def prepare_task(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """
        Convert user input into a task for the agent.
        This is where you transform your platform's format into SamTask.
        """
        text = external_input.get("text", "")
        if not text.strip():
            raise ValueError("Empty message")

        # Get config
        config: SimpleCliAdapterConfig = self.context.adapter_config

        # Create a simple text task
        return SamTask(
            parts=[self.context.create_text_part(text)],
            session_id=external_input.get("session_id"),
            target_agent=config.default_agent_name,
            is_streaming=True,
            platform_context={},
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """
        Handle updates from the agent.
        This is called multiple times as the agent streams its response.
        """
        for part in update.parts:
            if isinstance(part, SamTextPart):
                # Print text as it arrives
                print(part.text, end="", flush=True)

            elif isinstance(part, SamFilePart):
                # Just show that we got a file
                print(f"\n📄 File: {part.name}")

            elif isinstance(part, SamDataPart):
                # Handle special data types
                data_type = part.data.get("type")

                if data_type == "agent_progress_update":
                    # Show status
                    status = part.data.get("status_text", "")
                    print(f"⏳ {status}")

                elif data_type == "artifact_creation_progress":
                    # Show artifact progress
                    status = part.data.get("status")
                    filename = part.data.get("filename", "unknown")

                    if status == "in-progress":
                        print(f"📄 Creating {filename}...")
                    elif status == "completed":
                        version = part.data.get("version", 1)
                        description = part.data.get("description", "")
                        print(f"✅ Artifact created: {filename} (v{version})")
                        if description:
                            print(f"   {description[:80]}")
                    elif status == "failed":
                        print(f"❌ Failed to create artifact: {filename}")

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """Called when the agent finishes processing."""
        print("\n\n✅ Task complete.\n")
        self.processing = False  # Allow next prompt to show

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """Called when an error occurs."""
        if error.category == "CANCELED":
            print("\n🛑 Task canceled.\n")
        else:
            print(f"\n❌ Error: {error.message}\n")
        self.processing = False  # Allow next prompt to show
