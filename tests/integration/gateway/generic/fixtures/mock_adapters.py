"""
Mock gateway adapters for integration testing.

These are simplified but real implementations of GatewayAdapter that can be used
to test the generic gateway framework without needing external services.
"""

import asyncio
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from solace_agent_mesh.gateway.adapter.base import GatewayAdapter
from solace_agent_mesh.gateway.adapter.types import (
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


class MinimalAdapterConfig(BaseModel):
    """Configuration for MinimalAdapter"""

    default_user_id: str = Field(default="test-user@example.com")
    default_target_agent: str = Field(default="TestAgent")


class MinimalAdapter(GatewayAdapter):
    """
    Minimal adapter that implements only the required methods.

    This adapter:
    - Returns text-only tasks
    - Uses simple authentication
    - Captures updates for test assertions
    - No external dependencies
    """

    ConfigModel = MinimalAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.received_updates: List[tuple[SamUpdate, ResponseContext]] = []
        self.completed_tasks: List[str] = []
        self.errors: List[tuple[SamError, ResponseContext]] = []

    async def init(self, context: GatewayContext) -> None:
        """Store context for later use"""
        self.context = context

    async def extract_auth_claims(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        """Extract simple auth claims"""
        config: MinimalAdapterConfig = self.context.adapter_config
        user_id = external_input.get("user_id", config.default_user_id)
        return AuthClaims(id=user_id, source="minimal_adapter")

    async def prepare_task(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """Convert input to simple text task"""
        config: MinimalAdapterConfig = self.context.adapter_config
        text = external_input.get("text", "")

        return SamTask(
            parts=[SamTextPart(text=text)],
            target_agent=external_input.get("target_agent", config.default_target_agent),
            session_id=external_input.get("session_id", "test-session"),
            platform_context={"source": "minimal_adapter"},
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """Capture updates for testing"""
        self.received_updates.append((update, context))

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """Capture completion for testing"""
        self.completed_tasks.append(context.task_id)

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """Capture errors for testing"""
        self.errors.append((error, context))


class EchoAdapterConfig(BaseModel):
    """Configuration for EchoAdapter"""

    echo_prefix: str = Field(default="Echo: ")
    simulate_delay_ms: int = Field(default=0)


class EchoAdapter(GatewayAdapter):
    """
    Echo adapter that echoes back all received updates.

    This adapter:
    - Returns tasks with the input text
    - Echoes back all update parts it receives
    - Useful for testing bidirectional communication
    - Can simulate processing delays
    """

    ConfigModel = EchoAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.echoed_updates: List[str] = []  # Just track text for simplicity
        self.completed_tasks: List[str] = []

    async def init(self, context: GatewayContext) -> None:
        self.context = context

    async def extract_auth_claims(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        return AuthClaims(
            id=external_input.get("user", "echo-user@example.com"),
            source="echo_adapter",
        )

    async def prepare_task(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """Prepare task from input"""
        text = external_input.get("text", "")
        return SamTask(
            parts=[SamTextPart(text=text)],
            target_agent=external_input.get("agent", "TestAgent"),
            session_id=external_input.get("session", "echo-session"),
            platform_context={"source": "echo"},
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """Echo back the update content"""
        config: EchoAdapterConfig = self.context.adapter_config

        # Simulate delay if configured
        if config.simulate_delay_ms > 0:
            await asyncio.sleep(config.simulate_delay_ms / 1000.0)

        # Echo text parts
        for part in update.parts:
            if isinstance(part, SamTextPart):
                echoed = f"{config.echo_prefix}{part.text}"
                self.echoed_updates.append(echoed)

    async def handle_task_complete(self, context: ResponseContext) -> None:
        self.completed_tasks.append(context.task_id)


class FileAdapterConfig(BaseModel):
    """Configuration for FileAdapter"""

    max_file_size: int = Field(default=1024 * 1024)  # 1MB default


class FileAdapter(GatewayAdapter):
    """
    File-handling adapter for testing file uploads and downloads.

    This adapter:
    - Accepts file uploads in tasks
    - Tracks received files
    - Can receive file parts from agent
    """

    ConfigModel = FileAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.uploaded_files: List[Dict[str, Any]] = []
        self.received_files: List[tuple[SamFilePart, ResponseContext]] = []

    async def init(self, context: GatewayContext) -> None:
        self.context = context

    async def extract_auth_claims(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        return AuthClaims(id="file-user@example.com", source="file_adapter")

    async def prepare_task(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """Prepare task with files"""
        parts = []

        # Add text if present
        if "text" in external_input:
            parts.append(SamTextPart(text=external_input["text"]))

        # Add files if present
        if "files" in external_input:
            for file_info in external_input["files"]:
                file_part = SamFilePart(
                    name=file_info["name"],
                    content_bytes=file_info.get("content"),
                    uri=file_info.get("uri"),
                    mime_type=file_info.get("mime_type"),
                )
                parts.append(file_part)
                self.uploaded_files.append(file_info)

        return SamTask(
            parts=parts,
            target_agent="TestAgent",
            session_id="file-session",
            platform_context={"source": "file_adapter"},
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """Capture file parts from agent responses"""
        for part in update.parts:
            if isinstance(part, SamFilePart):
                self.received_files.append((part, context))


class AuthTestAdapterConfig(BaseModel):
    """Configuration for AuthTestAdapter"""

    require_token: bool = Field(default=False)
    valid_token: str = Field(default="valid-test-token")


class AuthTestAdapter(GatewayAdapter):
    """
    Adapter for testing various authentication scenarios.

    This adapter:
    - Can test different auth claim patterns
    - Can simulate auth failures
    - Can test token-based auth
    """

    ConfigModel = AuthTestAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.auth_attempts: List[Dict[str, Any]] = []
        self.received_updates: List[tuple[SamUpdate, ResponseContext]] = []
        self.completed_tasks: List[str] = []
        self.errors: List[tuple[SamError, ResponseContext]] = []

    async def init(self, context: GatewayContext) -> None:
        self.context = context

    async def extract_auth_claims(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        """Extract auth claims with various patterns"""
        config: AuthTestAdapterConfig = self.context.adapter_config

        # Track the attempt
        self.auth_attempts.append(external_input.copy())

        # Simulate different auth scenarios
        auth_type = external_input.get("auth_type", "email")

        if auth_type == "none":
            # No auth claims - should fall back to default
            return None

        elif auth_type == "email":
            return AuthClaims(
                id=external_input.get("email", "test@example.com"),
                email=external_input.get("email", "test@example.com"),
                source="email_auth",
            )

        elif auth_type == "token":
            token = external_input.get("token")
            if config.require_token and token != config.valid_token:
                raise PermissionError("Invalid token")
            return AuthClaims(
                id=external_input.get("user_id", "token-user"),
                token=token,
                token_type="bearer",
                source="token_auth",
            )

        elif auth_type == "platform_id":
            # Use platform-specific ID without email
            return AuthClaims(
                id=f"platform:{external_input.get('platform_user_id')}",
                source="platform_auth",
                raw_context={"platform_id": external_input.get("platform_user_id")},
            )

        return AuthClaims(id="fallback@example.com", source="fallback")

    async def prepare_task(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """Simple task preparation"""
        return SamTask(
            parts=[SamTextPart(text=external_input.get("text", "Auth test"))],
            target_agent="TestAgent",
            session_id="auth-test-session",
            platform_context={"auth_type": external_input.get("auth_type")},
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """Capture updates for testing"""
        self.received_updates.append((update, context))

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """Capture completion for testing"""
        self.completed_tasks.append(context.task_id)

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """Capture errors for testing"""
        self.errors.append((error, context))


class ErrorAdapter(GatewayAdapter):
    """
    Adapter that can simulate various error conditions.

    This adapter:
    - Can fail at different lifecycle points
    - Can simulate timeouts
    - Can test error recovery
    """

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.fail_on: Optional[str] = None  # 'init', 'auth', 'prepare', 'update'
        self.error_count: int = 0

    async def init(self, context: GatewayContext) -> None:
        self.context = context
        if self.fail_on == "init":
            self.error_count += 1
            raise RuntimeError("Simulated init failure")

    async def extract_auth_claims(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        if self.fail_on == "auth":
            self.error_count += 1
            raise PermissionError("Simulated auth failure")
        return AuthClaims(id="error-test@example.com", source="error_adapter")

    async def prepare_task(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        if self.fail_on == "prepare":
            self.error_count += 1
            raise ValueError("Simulated task preparation failure")

        return SamTask(
            parts=[SamTextPart(text="Error test")],
            target_agent="TestAgent",
            session_id="error-session",
            platform_context={},
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        if self.fail_on == "update":
            self.error_count += 1
            raise RuntimeError("Simulated update handling failure")

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """Track that error handler was called"""
        self.error_count += 1


class DispatchingAdapterConfig(BaseModel):
    """Configuration for DispatchingAdapter"""

    default_user_id: str = Field(default="dispatch-user@example.com")
    default_target_agent: str = Field(default="TestAgent")


class DispatchingAdapter(GatewayAdapter):
    """
    Adapter that uses the default base class handle_update() dispatching.

    This adapter DOES NOT override handle_update(), allowing the base class
    to dispatch to individual part handlers. This tests the default dispatching
    logic in GatewayAdapter.handle_update().
    """

    ConfigModel = DispatchingAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        # Track what each handler receives
        self.text_chunks: List[tuple[str, ResponseContext]] = []
        self.files: List[tuple[SamFilePart, ResponseContext]] = []
        self.data_parts: List[tuple[SamDataPart, ResponseContext]] = []
        self.status_updates: List[tuple[str, ResponseContext]] = []
        self.completed_tasks: List[str] = []
        self.errors: List[tuple[SamError, ResponseContext]] = []

    async def init(self, context: GatewayContext) -> None:
        """Store context for later use"""
        self.context = context

    async def extract_auth_claims(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        """Extract simple auth claims"""
        config: DispatchingAdapterConfig = self.context.adapter_config
        user_id = external_input.get("user_id", config.default_user_id)
        return AuthClaims(id=user_id, source="dispatching_adapter")

    async def prepare_task(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """Convert input to task"""
        config: DispatchingAdapterConfig = self.context.adapter_config
        text = external_input.get("text", "")

        return SamTask(
            parts=[SamTextPart(text=text)],
            target_agent=external_input.get("target_agent", config.default_target_agent),
            session_id=external_input.get("session_id", "dispatch-session"),
            platform_context={"source": "dispatching_adapter"},
        )

    # Override individual handlers to track what the base class dispatches
    async def handle_text_chunk(self, text: str, context: ResponseContext) -> None:
        """Capture text chunks dispatched by base class"""
        self.text_chunks.append((text, context))

    async def handle_file(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> None:
        """Capture file parts dispatched by base class"""
        self.files.append((file_part, context))

    async def handle_data_part(
        self, data_part: SamDataPart, context: ResponseContext
    ) -> None:
        """Capture data parts dispatched by base class"""
        self.data_parts.append((data_part, context))

    async def handle_status_update(
        self, status_text: str, context: ResponseContext
    ) -> None:
        """Capture status updates dispatched by base class"""
        self.status_updates.append((status_text, context))

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """Capture completion for testing"""
        self.completed_tasks.append(context.task_id)

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """Capture errors for testing"""
        self.errors.append((error, context))
