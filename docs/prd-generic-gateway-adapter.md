# PRD: Generic Gateway Adapter Framework (v2)

## 1. Executive Summary

### Overview
Create a plugin-based Generic Gateway system that dramatically simplifies the development of new gateway implementations in Solace Agent Mesh (SAM). This feature introduces a clean abstraction layer between platform-specific logic and A2A protocol handling, reducing gateway development effort from hundreds of lines to tens of lines for simple use cases.

### Goals
1. **Reduce Complexity**: Enable developers to create basic gateways (e.g., CLI, simple HTTP) in ~50 lines of code instead of ~500+
2. **Maintain Power**: Support all features of complex gateways like Slack (streaming, files, status updates, cancellation, etc.)
3. **Support Multi-Endpoint Gateways**: Enable a single adapter to handle multiple entry points with different configurations (e.g., webhook gateway with multiple HTTP endpoints)
4. **Decouple A2A Protocol**: Shield gateway developers from A2A protocol details (JSONRPCResponse, TaskStatusUpdateEvent, etc.)
5. **Plugin Architecture**: Make gateways as easy to develop as agent tools - just implement an adapter and configure
6. **Future-Proof**: Protect gateway implementations from A2A protocol evolution through a stable SAM abstraction layer

### Current Pain Points
- Gateway developers must understand A2A protocol internals
- Must manage complex lifecycle hooks and async message processing
- Significant boilerplate for handling embed resolution, artifact URIs, and message routing
- Tight coupling to Solace AI Connector component architecture
- High barrier to entry for simple use cases

### Value Proposition
**Before**: Implementing a basic CLI gateway requires:
- Extending `BaseGatewayComponent` (understanding SAC component model)
- Implementing 5+ abstract methods with complex signatures
- Managing A2A protocol types and message construction
- Handling streaming buffers, embed resolution, and error states
- ~500+ lines of code

**After**: Implementing the same CLI gateway requires:
- Implementing `GatewayAdapter` with clear, focused methods
- Working with simple SAM types (`SamTask`, `SamTextPart`, etc.)
- No knowledge of A2A protocol internals needed
- ~50 lines of code

---

## 2. Requirements

### Functional Requirements

#### FR-1: Gateway Adapter Interface
- SHALL provide an abstract base class `GatewayAdapter` that gateway plugins implement
- SHALL define lifecycle methods: `init()`, `cleanup()`
- SHALL define inbound methods: `extract_auth_claims()`, `prepare_task()`
- SHALL support optional `endpoint_context` parameter in inbound methods for multi-endpoint gateways
- SHALL define outbound methods with hybrid design:
  - Individual part handlers: `handle_text_chunk()`, `handle_file()`, `handle_data_part()`, `handle_status_update()`, `handle_task_complete()`, `handle_error()`
  - Aggregate handler: `handle_update()` (optional override for batch processing)
- SHALL call individual handlers from base `handle_update()` implementation by default
- SHALL allow adapters to override `handle_update()` for custom batch processing
- SHALL make all outbound handlers optional with no-op defaults (for fire-and-forget gateways)

#### FR-2: SAM Type System
- SHALL define SAM-specific Pydantic models that decouple from A2A protocol: `SamTask`, `SamTextPart`, `SamFilePart`, `SamDataPart`, `AuthClaims`, `SamUpdate`
- SHALL provide translation functions between SAM types and A2A types
- SHALL ensure SAM types can represent all A2A capabilities (text, files with bytes/URIs, structured data)
- SHALL use Pydantic for validation, IDE support, and automatic documentation

#### FR-3: Generic Gateway Component
- SHALL provide `GenericGatewayComponent` that extends `BaseGatewayComponent`
- SHALL dynamically load adapter plugins from configuration (Python module path)
- SHALL orchestrate the request flow: auth extraction → enrichment → task preparation → A2A submission
- SHALL route A2A responses to appropriate adapter handlers
- SHALL manage all A2A protocol complexity internally

#### FR-4: Context Objects
- SHALL provide `GatewayContext` to adapters during initialization with access to:
  - Gateway configuration via `config` dict
  - Adapter-specific configuration via `adapter_config` dict
  - Method to process external input: `handle_external_input()` (supports optional endpoint_context)
  - Helper methods to create SAM parts
  - SAC template processing: `process_sac_template()` for template-based text generation
  - Artifact service access
  - Timer management functions
  - State management helpers (task and session state)
- SHALL provide `ResponseContext` with each outbound callback containing:
  - Task ID, conversation ID, user identity
  - Platform-specific context for response routing

#### FR-5: Authentication Support
- SHALL support multiple authentication modes via configuration:
  - OAuth 2.0 Client Credentials flow
  - OAuth 2.0 User/Authorization Code flow
  - Static Bearer Token
  - API Key (custom header)
  - Custom (adapter-implemented)
- SHALL handle OAuth token caching and refresh automatically
- SHALL integrate with existing `identity_service` for user enrichment
- SHALL allow adapters to provide tokens via `extract_auth_claims()` for token-based flows
- SHALL allow adapters to return None for user_id (host uses config-based default)

#### FR-6: State Management
- SHALL provide task-specific state storage: `get_task_state()`, `set_task_state()`
- SHALL provide session-specific state storage: `get_session_state()`, `set_session_state()`
- SHALL abstract underlying storage mechanism (memory, cache service, etc.)
- SHALL automatically clean up task state on completion

#### FR-7: Feature Completeness
- SHALL support all features of existing complex gateways:
  - Streaming text with buffering (Slack, HTTP SSE)
  - File upload/download (inline bytes and URI references)
  - Status updates and progress indicators
  - Task cancellation
  - Error handling and reporting
  - Platform-specific formatting (e.g., markdown conversion)
  - Session/conversation tracking
  - Structured data parts
  - Fire-and-forget patterns (Webhook gateway - immediate HTTP response, no streaming)
  - Multi-endpoint configuration (Webhook gateway - multiple paths with different auth/config)
  - Template-based payload transformation (Webhook gateway - SAC templates)

#### FR-8: Configuration
- SHALL support YAML configuration specifying:
  - Gateway adapter module path (`gateway_adapter`)
  - Adapter-specific settings (`adapter_config` block)
  - Authentication configuration (`auth_config`)
  - Platform-specific settings
  - Artifact service configuration
  - All standard gateway settings (namespace, gateway_id, etc.)

### Non-Functional Requirements

#### NFR-1: Developer Experience
- Gateway adapters SHOULD be implementable in <100 lines for simple cases
- API SHOULD be intuitive with clear naming conventions
- Documentation SHOULD include multiple working examples
- Type hints MUST be comprehensive for IDE support using Pydantic models

#### NFR-2: Backward Compatibility
- SHALL NOT break existing gateway implementations
- SHALL coexist with current gateway pattern
- Existing gateways MAY be migrated but are not required to

#### NFR-3: Performance
- SHALL NOT introduce significant overhead vs. direct BaseGatewayComponent implementation
- SHALL handle streaming responses efficiently with minimal buffering overhead
- SHALL support high-throughput scenarios (1000+ concurrent tasks)

#### NFR-4: Maintainability
- SAM type definitions SHALL be in a single, well-documented module
- Translation functions SHALL have comprehensive tests
- Adapter interface SHALL be stable across minor A2A protocol updates

---

## 3. Architecture Overview

### Component Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    YAML Configuration                        │
│  - gateway_adapter: "my_plugin.MyAdapter"                   │
│  - adapter_config: {...}                                     │
│  - auth_config: {...}                                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   GenericGatewayApp                          │
│  (extends BaseGatewayApp)                                    │
│  - Validates configuration                                   │
│  - Generates Solace subscriptions                           │
│  - Creates GenericGatewayComponent instance                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              GenericGatewayComponent                         │
│  (extends BaseGatewayComponent)                              │
│  - Loads adapter plugin dynamically                          │
│  - Implements all BaseGatewayComponent abstract methods     │
│  - Manages A2A protocol complexity                          │
│  - Handles authentication (OAuth, tokens, etc.)             │
│  - Routes responses to adapter handlers                     │
│  - Manages state storage (task and session)                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 GatewayAdapter (ABC)                         │
│  User implements:                                            │
│  - init() / cleanup()                                        │
│  - extract_auth_claims()                                     │
│  - prepare_task()                                            │
│  - handle_text_chunk() OR handle_update()                   │
│  - handle_file(), handle_status_update(), etc. (optional)   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                External Platform                             │
│  (Slack, HTTP, CLI, Discord, Teams, etc.)                   │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow

```
1. Platform Event Arrives
   └─→ Adapter's listener (e.g., Slack @mention, webhook HTTP request) receives it

2. Adapter Calls context.handle_external_input(raw_event, endpoint_context=...)
   └─→ GenericGatewayComponent orchestrates:
   └─→ Note: endpoint_context is optional, for multi-endpoint gateways (e.g., webhooks)

3. Authentication Flow
   ├─→ Calls adapter.extract_auth_claims(raw_event, endpoint_context)
   ├─→ Returns AuthClaims (with optional user_id, token, etc.)
   ├─→ If user_id is None, uses default from auth_config
   ├─→ If token provided, validates it
   ├─→ Enriches via identity_service if configured
   └─→ Validates final user_id present

4. Task Preparation
   ├─→ Calls adapter.prepare_task(raw_event, endpoint_context)
   ├─→ Returns SamTask with parts, conversation_id, etc.
   ├─→ Adapter may use context.process_sac_template() for payload transformation
   └─→ Translates SamTask → A2A Message

5. A2A Submission
   ├─→ Creates A2A JSONRPCRequest
   ├─→ Publishes to agent request topic
   ├─→ Stores platform_context for response routing
   ├─→ Initializes task state storage
   └─→ Returns task_id

6. Response Handling (streaming)
   ├─→ GenericGatewayComponent receives A2A events
   ├─→ Parses TaskStatusUpdateEvent, Task, etc.
   ├─→ Resolves embeds and artifact URIs
   ├─→ Translates to SamUpdate with typed parts
   └─→ Calls adapter.handle_update() (or individual handlers)
   └─→ Note: For fire-and-forget gateways, handlers can be no-ops

7. Task Completion
   ├─→ Calls adapter.handle_task_complete()
   └─→ Cleans up task state
```

### Class Prototypes

```python
# ============================================
# SAM Gateway Types (solace_agent_mesh/gateway/adapter/types.py)
# ============================================

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional, List, Union, Literal
from google.adk.artifacts import BaseArtifactService

class SamTextPart(BaseModel):
    """Text content in a SAM task"""
    type: Literal["text"] = "text"
    text: str


class SamFilePart(BaseModel):
    """File content in a SAM task"""
    type: Literal["file"] = "file"
    name: str
    content_bytes: Optional[bytes] = None  # Inline bytes
    uri: Optional[str] = None  # Reference to artifact://
    mime_type: Optional[str] = None

    @field_validator('content_bytes', 'uri')
    @classmethod
    def validate_content_or_uri(cls, v, info):
        # Must have either content_bytes or uri
        values = info.data
        if not values.get('content_bytes') and not values.get('uri'):
            raise ValueError("Must have either content_bytes or uri")
        return v


class SamDataPart(BaseModel):
    """Structured data in a SAM task"""
    type: Literal["data"] = "data"
    data: Dict[str, Any]


# Union type for convenience
SamContentPart = Union[SamTextPart, SamFilePart, SamDataPart]


class SamTask(BaseModel):
    """
    A task prepared for submission to the SAM agent mesh.
    This is SAM's canonical representation of an inbound task,
    independent of the underlying A2A protocol wire format.
    """
    parts: List[SamContentPart]
    conversation_id: Optional[str] = None
    target_agent: str = Field(..., description="Target agent name (required)")
    is_streaming: bool = Field(default=True, description="Enable streaming responses")
    platform_context: Dict[str, Any] = Field(default_factory=dict)


class AuthClaims(BaseModel):
    """Authentication claims extracted from platform"""
    user_id: Optional[str] = Field(
        default=None,
        description="User identifier. If None, generic gateway uses auth_config default"
    )
    email: Optional[str] = None
    token: Optional[str] = Field(
        default=None,
        description="Bearer token or API key for token-based auth flows"
    )
    token_type: Optional[Literal["bearer", "api_key"]] = None
    source: str = Field(default="platform", description="Authentication source")
    raw_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific auth context"
    )


class SamUpdate(BaseModel):
    """
    An update event from the agent containing one or more parts.
    Used for streaming responses and intermediate updates.
    """
    parts: List[SamContentPart] = Field(default_factory=list)
    is_final: bool = Field(
        default=False,
        description="True if this is the final update before task completion"
    )


class GatewayContext:
    """
    Context provided to gateway adapter during initialization.
    Provides access to gateway services and helper methods.
    """
    gateway_id: str
    namespace: str
    config: Dict[str, Any]  # Full gateway configuration
    adapter_config: Dict[str, Any]  # Adapter-specific configuration
    artifact_service: BaseArtifactService

    async def handle_external_input(
        self,
        external_input: Any,
        endpoint_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Process external input through auth → prepare → submit flow.

        Args:
            external_input: Raw platform event (opaque to generic gateway)
            endpoint_context: Optional endpoint-specific configuration
                            (for multi-endpoint gateways like webhooks)

        Returns:
            task_id: Unique identifier for the submitted task

        Flow:
            1. Calls adapter.extract_auth_claims(external_input, endpoint_context)
            2. Enriches via identity_service
            3. Calls adapter.prepare_task(external_input, endpoint_context)
            4. Translates SamTask to A2A message
            5. Submits to agent via A2A protocol
            6. Returns task_id for tracking

        Example (Multi-endpoint webhook):
            # Each endpoint has different config
            for endpoint_config in webhook_endpoints:
                @app.post(endpoint_config["path"])
                async def handler(request):
                    task_id = await context.handle_external_input(
                        external_input=request,
                        endpoint_context=endpoint_config
                    )
                    return {"taskId": task_id}
        """
        pass

    async def cancel_task(self, task_id: str) -> None:
        """
        Cancel an in-flight task.

        Args:
            task_id: Task identifier returned from handle_external_input()
        """
        pass

    def add_timer(
        self,
        delay_ms: int,
        callback: Callable,
        interval_ms: Optional[int] = None
    ) -> str:
        """
        Add a timer for periodic operations.

        Args:
            delay_ms: Initial delay in milliseconds
            callback: Async function to call
            interval_ms: Repeat interval (None for one-shot)

        Returns:
            timer_id: Identifier for timer management
        """
        pass

    def cancel_timer(self, timer_id: str) -> None:
        """Cancel a previously registered timer"""
        pass

    # State management
    def get_task_state(self, task_id: str, key: str, default: Any = None) -> Any:
        """
        Get task-specific state.
        Useful for tracking per-task UI state (message timestamps, buffers, etc.)

        Args:
            task_id: Task identifier
            key: State key
            default: Default value if key not found

        Returns:
            Stored value or default
        """
        pass

    def set_task_state(self, task_id: str, key: str, value: Any) -> None:
        """
        Set task-specific state.
        Automatically cleaned up when task completes.

        Args:
            task_id: Task identifier
            key: State key
            value: Value to store
        """
        pass

    def get_session_state(self, session_id: str, key: str, default: Any = None) -> Any:
        """
        Get session-specific state.
        Useful for tracking conversation state across multiple tasks.

        Args:
            session_id: Session/conversation identifier
            key: State key
            default: Default value if key not found

        Returns:
            Stored value or default
        """
        pass

    def set_session_state(self, session_id: str, key: str, value: Any) -> None:
        """
        Set session-specific state.
        Persists across tasks in the same conversation.

        Args:
            session_id: Session/conversation identifier
            key: State key
            value: Value to store
        """
        pass

    # Convenience methods for creating SAM parts
    def create_text_part(self, text: str) -> SamTextPart:
        """Create a text part"""
        return SamTextPart(text=text)

    def create_file_part_from_bytes(
        self,
        name: str,
        content_bytes: bytes,
        mime_type: str
    ) -> SamFilePart:
        """Create a file part from inline bytes"""
        return SamFilePart(name=name, content_bytes=content_bytes, mime_type=mime_type)

    def create_file_part_from_uri(
        self,
        uri: str,
        name: str,
        mime_type: Optional[str] = None
    ) -> SamFilePart:
        """Create a file part from artifact URI"""
        return SamFilePart(name=name, uri=uri, mime_type=mime_type)

    def create_data_part(self, data: Dict[str, Any]) -> SamDataPart:
        """Create a structured data part"""
        return SamDataPart(data=data)

    def process_sac_template(
        self,
        template: str,
        payload: Any = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        user_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Process a Solace AI Connector message template.

        Useful for gateways that need to transform structured payloads into
        text using templates (e.g., webhook gateway).

        Supports all SAC template features:
        - {{text://input.payload:path.to.field}}
        - {{text://user_data.headers:header_name}}
        - {{text://input.user_properties:param_name}}
        - {{invoke:module.function:args}}
        - Handlebars helpers: {{#if}}, {{#each}}, etc.

        Args:
            template: SAC template string
            payload: Parsed payload data (dict, list, or primitive)
            headers: HTTP headers dict
            query_params: Query parameters dict
            user_data: Additional context data

        Returns:
            Rendered template string

        Example (Webhook):
            text = context.process_sac_template(
                template="User: {{text://input.payload:user_name}}, Event: {{text://input.payload:event_type}}",
                payload={"user_name": "Alice", "event_type": "login"},
                headers=request.headers,
                query_params=request.query_params
            )
        """
        pass


class ResponseContext(BaseModel):
    """
    Context provided with each outbound response callback.
    Contains information needed to route responses back to the platform.
    """
    task_id: str
    conversation_id: str  # Same as provided in SamTask
    user_id: str
    platform_context: Dict[str, Any]  # Retrieved from task storage


# ============================================
# Gateway Adapter (solace_agent_mesh/gateway/adapter/base.py)
# ============================================

from abc import ABC, abstractmethod
from a2a.types import FilePart, DataPart

class GatewayAdapter(ABC):
    """
    Abstract base class for gateway adapter plugins.

    Gateway adapters handle platform-specific communication while the
    GenericGatewayComponent manages A2A protocol complexity.

    Lifecycle:
        1. init() called with GatewayContext
        2. Platform events trigger adapter listeners
        3. Adapter calls context.handle_external_input(event)
        4. Generic gateway calls extract_auth_claims(event)
        5. Generic gateway calls prepare_task(event)
        6. Generic gateway submits to A2A and manages responses
        7. Generic gateway calls handle_update() (or individual handlers)
        8. cleanup() called on shutdown

    Handler Design (Hybrid):
        - By default, handle_update() calls individual part handlers
        - Adapters can implement individual handlers for fine-grained control
        - Adapters can override handle_update() for batch processing
        - Most handlers are optional (have default implementations)
    """

    # ==================== LIFECYCLE ====================

    async def init(self, context: GatewayContext) -> None:
        """
        Initialize the gateway adapter.

        This is where you should:
        - Start platform listeners (WebSocket, HTTP server, stdin reader, etc.)
        - Connect to external services
        - Register event handlers
        - Store the context for later use

        Args:
            context: GatewayContext with access to services and helpers

        Note:
            This method is async to support async initialization tasks.
            For synchronous setup, simply don't use await.
        """
        pass

    async def cleanup(self) -> None:
        """
        Clean up resources on shutdown.

        This is where you should:
        - Stop platform listeners
        - Close connections
        - Release resources
        """
        pass

    # ==================== AUTHENTICATION ====================

    async def extract_auth_claims(
        self,
        external_input: Any,
        endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        """
        Extract authentication claims from platform input.

        This method is called by the generic gateway to determine user identity.
        You can return:
        - AuthClaims with user_id: Explicit user identification
        - AuthClaims without user_id: Gateway uses auth_config default
        - AuthClaims with token: For OAuth/Bearer token validation
        - None: Gateway uses configured authentication entirely

        Args:
            external_input: Raw platform event (same object passed to prepare_task)
            endpoint_context: Optional endpoint-specific configuration
                            (for multi-endpoint gateways with per-endpoint auth)

        Returns:
            AuthClaims with user info/tokens, or None

        Examples:
            # Slack: Extract user_id and fetch email
            user_id = event.get("user")
            email = await self.slack_client.get_user_email(user_id)
            return AuthClaims(user_id=email, email=email, source="slack_api")

            # CLI: Simple static identity
            return AuthClaims(user_id="cli_user", source="local")

            # HTTP: Extract from JWT
            token = request.headers.get("Authorization")
            return AuthClaims(
                token=token,
                token_type="bearer",
                source="jwt"
            )

            # Webhook: Per-endpoint auth
            auth_config = endpoint_context.get("auth", {})
            if auth_config.get("type") == "token":
                token_config = auth_config["token_config"]
                token = request.headers.get(token_config["name"])
                assumed_user = endpoint_context.get("assumed_user_identity")
                return AuthClaims(
                    user_id=assumed_user,
                    token=token,
                    token_type="api_key",
                    source="webhook_endpoint"
                )

            # Use config-based auth entirely
            return None
        """
        return None

    # ==================== INBOUND: Platform → A2A ====================

    @abstractmethod
    async def prepare_task(
        self,
        external_input: Any,
        endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """
        Prepare a task from platform input.

        This method is called after authentication succeeds. Convert your
        platform's event format into a SamTask with parts.

        Args:
            external_input: Raw platform event (opaque to generic gateway)
            endpoint_context: Optional endpoint-specific configuration
                            (for multi-endpoint gateways with per-endpoint settings)

        Returns:
            SamTask with parts, conversation_id, and platform context

        Raises:
            ValueError: If the input cannot be translated (will be reported as error)

        Example (Simple Slack):
            parts = [
                context.create_text_part(event["message"]),
                context.create_file_part_from_bytes(
                    name="attachment.pdf",
                    content_bytes=await download_file(event["file_url"]),
                    mime_type="application/pdf"
                )
            ]

            return SamTask(
                parts=parts,
                conversation_id=event["thread_id"],
                target_agent=event.get("agent_name", "default_agent"),
                is_streaming=True,
                platform_context={
                    "channel": event["channel"],
                    "thread_id": event["thread_id"]
                }
            )

        Example (Webhook with endpoint_context):
            # Extract endpoint-specific configuration
            target_agent = endpoint_context.get("target_agent_name")
            input_template = endpoint_context.get("input_template")

            # Process template with webhook payload
            text = context.process_sac_template(
                template=input_template,
                payload=external_input.json(),
                headers=external_input.headers,
                query_params=external_input.query_params
            )

            return SamTask(
                parts=[context.create_text_part(text)],
                target_agent=target_agent,
                is_streaming=False,  # Webhook is fire-and-forget
                platform_context={"webhook_path": external_input.url.path}
            )
        """
        pass

    # ==================== OUTBOUND: A2A → Platform ====================
    # Hybrid Design: Implement individual handlers OR override handle_update()

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """
        Handle an update from the agent (batch handler).

        This is the main entry point for all agent responses. By default,
        this method dispatches to individual part handlers based on type.

        Override this method if you want to:
        - Process multiple parts atomically
        - Implement custom batching logic
        - Handle parts in a different order

        Default implementation:
            for part in update.parts:
                if isinstance(part, SamTextPart):
                    await self.handle_text_chunk(part.text, context)
                elif isinstance(part, SamFilePart):
                    await self.handle_file(part, context)
                elif isinstance(part, SamDataPart):
                    await self.handle_data_part(part, context)

        Args:
            update: SamUpdate containing list of parts
            context: Response context with task_id, platform_context, etc.
        """
        # Default implementation: dispatch to individual handlers
        for part in update.parts:
            if isinstance(part, SamTextPart):
                await self.handle_text_chunk(part.text, context)
            elif isinstance(part, SamFilePart):
                await self.handle_file(part, context)
            elif isinstance(part, SamDataPart):
                await self.handle_data_part(part, context)

    @abstractmethod
    async def handle_text_chunk(self, text: str, context: ResponseContext) -> None:
        """
        Handle streaming text chunk from the agent.

        Called multiple times during streaming responses. You may want to:
        - Buffer text and update a single message
        - Post each chunk as a separate message
        - Apply platform-specific formatting

        This is the only required outbound handler. If you override handle_update(),
        you don't need to implement this, but it's recommended for clarity.

        Args:
            text: Text content from agent (may be partial sentence)
            context: Response context with task_id, conversation_id, platform_context

        Example (Slack with buffering):
            task_id = context.task_id

            # Use state management
            buffer = self.context.get_task_state(task_id, "buffer", "")
            buffer += text
            self.context.set_task_state(task_id, "buffer", buffer)

            # Update Slack message
            msg_ts = self.context.get_task_state(task_id, "message_ts")
            await self.slack_client.update_message(
                channel=context.platform_context["channel"],
                ts=msg_ts,
                text=buffer
            )
        """
        pass

    async def handle_file(self, file_part: SamFilePart, context: ResponseContext) -> None:
        """
        Handle file/artifact from the agent.

        The SamFilePart will have either:
        - content_bytes: Inline file content
        - uri: Artifact URI reference

        You should upload the file to your platform or provide a link.

        Args:
            file_part: SamFilePart with file data
            context: Response context

        Example (Slack):
            if file_part.content_bytes:
                await self.slack_client.upload_file(
                    channel=context.platform_context["channel"],
                    thread_ts=context.platform_context["thread_ts"],
                    filename=file_part.name,
                    content=file_part.content_bytes
                )
            elif file_part.uri:
                await self.slack_client.post_message(
                    channel=context.platform_context["channel"],
                    thread_ts=context.platform_context["thread_ts"],
                    text=f"Artifact: {file_part.name} - {file_part.uri}"
                )
        """
        pass

    async def handle_data_part(self, data_part: SamDataPart, context: ResponseContext) -> None:
        """
        Handle structured data part from the agent.

        DataParts carry structured information like:
        - Progress updates: {"type": "agent_progress_update", "status_text": "..."}
        - Tool results: {"type": "tool_result", "tool_name": "...", ...}
        - Custom agent data: {"type": "custom", ...}

        Args:
            data_part: SamDataPart with structured data
            context: Response context

        Example (Slack - format as code block):
            formatted = json.dumps(data_part.data, indent=2)
            await self.slack_client.post_message(
                channel=context.platform_context["channel"],
                text=f"```\\n{formatted}\\n```"
            )
        """
        pass

    async def handle_status_update(self, status_text: str, context: ResponseContext) -> None:
        """
        Handle agent status update (progress indicator).

        Called when the agent sends a status signal like:
        - "Analyzing data..."
        - "Calling web API..."
        - "Generating image..."

        Note: This is extracted from DataParts with type "agent_progress_update"
        by the generic gateway before calling handlers.

        You might display this as:
        - Slack: Update a status message with emoji
        - CLI: Print to stderr
        - HTTP SSE: Send as event

        Args:
            status_text: Human-readable status message
            context: Response context

        Example (Slack with state management):
            task_id = context.task_id
            status_msg = f":thinking_face: {status_text}"

            status_ts = self.context.get_task_state(task_id, "status_ts")
            await self.slack_client.update_message(
                channel=context.platform_context["channel"],
                ts=status_ts,
                text=status_msg
            )
        """
        pass

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """
        Handle task completion notification.

        Called after all content has been delivered via handle_text_chunk(),
        handle_file(), etc. Use this for:
        - Updating status indicators
        - Cleaning up UI state
        - Logging completion
        - Showing feedback buttons

        Note: Task state is automatically cleaned up after this call.

        Args:
            context: Response context

        Example (Slack):
            task_id = context.task_id
            status_ts = self.context.get_task_state(task_id, "status_ts")

            await self.slack_client.update_message(
                channel=context.platform_context["channel"],
                ts=status_ts,
                text=":checkered_flag: Complete!"
            )

            # No need to manually clean up task state - done automatically
        """
        pass

    async def handle_error(self, error_message: str, context: ResponseContext) -> None:
        """
        Handle error from the agent or gateway.

        Called when:
        - Agent returns a TaskState.failed
        - A2A protocol error occurs
        - Gateway processing error

        Args:
            error_message: Human-readable error description
            context: Response context

        Example (Slack):
            await self.slack_client.post_message(
                channel=context.platform_context["channel"],
                thread_ts=context.conversation_id,
                text=f":x: Error: {error_message}"
            )
        """
        pass
```

---

## 4. Complete API Reference

### Core Classes

#### `GatewayAdapter` (Abstract Base Class)
Base class for all gateway adapter plugins. Located in `solace_agent_mesh/gateway/adapter/base.py`.

**Lifecycle Methods:**
- `async init(context: GatewayContext) -> None`: Initialize adapter, start listeners
- `async cleanup() -> None`: Clean up resources on shutdown

**Inbound Methods (called by generic gateway):**
- `async extract_auth_claims(external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None) -> Optional[AuthClaims]`: Extract user identity/tokens (endpoint_context for multi-endpoint gateways)
- `async prepare_task(external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None) -> SamTask`: Convert platform event to SamTask (endpoint_context for multi-endpoint gateways)

**Outbound Methods (hybrid design):**

*Option 1: Implement individual handlers (recommended for simple adapters):*
- `async handle_text_chunk(text: str, context: ResponseContext) -> None`: Handle streaming text (required)
- `async handle_file(file_part: SamFilePart, context: ResponseContext) -> None`: Handle files/artifacts
- `async handle_data_part(data_part: SamDataPart, context: ResponseContext) -> None`: Handle structured data
- `async handle_status_update(status_text: str, context: ResponseContext) -> None`: Handle progress updates
- `async handle_task_complete(context: ResponseContext) -> None`: Handle task completion
- `async handle_error(error_message: str, context: ResponseContext) -> None`: Handle errors

*Option 2: Override batch handler (for complex adapters):*
- `async handle_update(update: SamUpdate, context: ResponseContext) -> None`: Handle all parts in batch

### Type Definitions

#### `SamTask` (Pydantic Model)
**Fields:**
- `parts: List[SamContentPart]` - Ordered list of content parts (text, files, data)
- `conversation_id: Optional[str]` - Session/thread identifier for multi-turn conversations
- `target_agent: str` - Specific agent to target (required)
- `is_streaming: bool` - Enable streaming responses (default: True)
- `platform_context: Dict[str, Any]` - Platform-specific data for response routing

#### `SamTextPart` (Pydantic Model)
**Fields:**
- `type: Literal["text"]` - Type discriminator
- `text: str` - Text content

#### `SamFilePart` (Pydantic Model)
**Fields:**
- `type: Literal["file"]` - Type discriminator
- `name: str` - Filename
- `content_bytes: Optional[bytes]` - Inline file content (mutually exclusive with uri)
- `uri: Optional[str]` - Artifact URI reference (mutually exclusive with content_bytes)
- `mime_type: Optional[str]` - MIME type

**Validation:** Must have either `content_bytes` or `uri` (not both, not neither)

#### `SamDataPart` (Pydantic Model)
**Fields:**
- `type: Literal["data"]` - Type discriminator
- `data: Dict[str, Any]` - Structured data (JSON-serializable)

#### `AuthClaims` (Pydantic Model)
**Fields:**
- `user_id: Optional[str]` - Primary user identifier (can be None, gateway uses default)
- `email: Optional[str]` - User email address
- `token: Optional[str]` - Bearer token or API key for token-based auth
- `token_type: Optional[Literal["bearer", "api_key"]]` - Token type
- `source: str` - Authentication source (default: "platform")
- `raw_context: Dict[str, Any]` - Extra platform-specific auth context

#### `SamUpdate` (Pydantic Model)
**Fields:**
- `parts: List[SamContentPart]` - List of content parts in this update
- `is_final: bool` - True if this is the final update before completion (default: False)

#### `GatewayContext`
**Fields:**
- `gateway_id: str` - Unique gateway instance identifier
- `namespace: str` - A2A namespace (e.g., "myorg/production")
- `config: Dict[str, Any]` - Full gateway configuration from YAML
- `adapter_config: Dict[str, Any]` - Adapter-specific configuration block
- `artifact_service: BaseArtifactService` - Shared artifact service instance

**Methods:**
- `async handle_external_input(external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None) -> str` - Process and submit external input (supports multi-endpoint gateways)
- `async cancel_task(task_id: str) -> None` - Cancel a task
- `def add_timer(...) -> str` - Add periodic timer
- `def cancel_timer(timer_id: str) -> None` - Cancel timer
- `def get_task_state(task_id, key, default) -> Any` - Get task-specific state
- `def set_task_state(task_id, key, value) -> None` - Set task-specific state
- `def get_session_state(session_id, key, default) -> Any` - Get session-specific state
- `def set_session_state(session_id, key, value) -> None` - Set session-specific state
- `def create_text_part(text: str) -> SamTextPart` - Helper to create text part
- `def create_file_part_from_bytes(...) -> SamFilePart` - Helper to create file part from bytes
- `def create_file_part_from_uri(...) -> SamFilePart` - Helper to create file part from URI
- `def create_data_part(data: Dict) -> SamDataPart` - Helper to create data part
- `def process_sac_template(template: str, payload: Any, headers: Optional[Dict], query_params: Optional[Dict], user_data: Optional[Dict]) -> str` - Process SAC message templates for payload transformation

#### `ResponseContext` (Pydantic Model)
**Fields:**
- `task_id: str` - Task identifier
- `conversation_id: str` - Conversation/session identifier
- `user_id: str` - Authenticated user identifier
- `platform_context: Dict[str, Any]` - Platform-specific context from SamTask.platform_context

### `GenericGatewayApp`
Extends `BaseGatewayApp`. Located in `solace_agent_mesh/gateway/generic/app.py`.

**Configuration Requirements:**
- `gateway_adapter: str` - Python module path to adapter class (e.g., "my_plugin.cli.CLIAdapter")
- `adapter_config: Dict[str, Any]` - Dedicated configuration block for adapter (passed via context.adapter_config)
- `auth_config: Dict[str, Any]` - Authentication configuration
- All standard `BaseGatewayApp` configuration (namespace, gateway_id, artifact_service, etc.)

### `GenericGatewayComponent`
Extends `BaseGatewayComponent`. Located in `solace_agent_mesh/gateway/generic/component.py`.

**Responsibilities:**
- Load adapter plugin dynamically from configured module path
- Call adapter.init() during startup
- Implement all BaseGatewayComponent abstract methods by delegating to adapter
- Orchestrate auth → prepare → submit flow
- Translate between SAM types and A2A types
- Route A2A responses to adapter handlers
- Manage task and session state storage
- Call adapter.cleanup() on shutdown

---

## 5. Simple CLI Gateway Example

This example demonstrates how simple it is to create a basic gateway with the new adapter system.

### CLI Adapter Implementation

**File:** `examples/gateways/adapters/cli_adapter.py`

```python
"""
Simple CLI Gateway Adapter - demonstrates minimal implementation.
Reads from stdin, sends to agent, prints responses to stdout.
"""

import asyncio
import sys
from typing import Any, Optional
from solace_agent_mesh.gateway.adapter.base import GatewayAdapter
from solace_agent_mesh.gateway.adapter.types import (
    GatewayContext,
    ResponseContext,
    AuthClaims,
    SamTask,
    SamFilePart,
    SamDataPart,
)


class CLIAdapter(GatewayAdapter):
    """Minimal CLI gateway - no authentication, simple text I/O"""

    async def init(self, context: GatewayContext) -> None:
        """Start stdin reader"""
        self.context = context
        self.running = True

        # Start async stdin reader
        asyncio.create_task(self._read_input_loop())

        print("CLI Gateway ready. Type your messages:")

    async def cleanup(self) -> None:
        """Stop reading input"""
        self.running = False

    async def extract_auth_claims(self, external_input: str) -> Optional[AuthClaims]:
        """Simple static user identity"""
        return AuthClaims(user_id="cli_user", source="local")

    async def prepare_task(self, external_input: str) -> SamTask:
        """Convert text input to SamTask"""
        text_part = self.context.create_text_part(external_input)

        return SamTask(
            parts=[text_part],
            conversation_id="cli_session",  # Single persistent session
            target_agent=self.context.config.get("default_agent_name", "default"),
            is_streaming=True,
            platform_context={}
        )

    async def handle_text_chunk(self, text: str, context: ResponseContext) -> None:
        """Print text to stdout"""
        print(text, end='', flush=True)

    async def handle_file(self, file_part: SamFilePart, context: ResponseContext) -> None:
        """Print file info"""
        print(f"\n[File: {file_part.name}]", flush=True)
        if file_part.uri:
            print(f"[URI: {file_part.uri}]", flush=True)

    async def handle_status_update(self, status_text: str, context: ResponseContext) -> None:
        """Print status to stderr"""
        print(f"\r[{status_text}]", end='', file=sys.stderr, flush=True)

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """Print completion marker"""
        print("\n\n---\n")
        print("Next query:", flush=True)

    async def handle_error(self, error_message: str, context: ResponseContext) -> None:
        """Print error"""
        print(f"\nError: {error_message}\n", file=sys.stderr)

    # Helper: Input reading loop
    async def _read_input_loop(self):
        """Async loop reading from stdin"""
        loop = asyncio.get_event_loop()
        while self.running:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:  # EOF
                    break

                line = line.strip()
                if line:
                    # Submit to gateway
                    await self.context.handle_external_input(line)

            except Exception as e:
                print(f"Error reading input: {e}", file=sys.stderr)
                break
```

### CLI Gateway Configuration

**File:** `examples/gateways/cli_gateway_example.yaml`

```yaml
name: cli_gateway
log_level: INFO

broker:
  host: localhost:55555
  vpn_name: default
  username: default
  password: default

app:
  class_name: solace_agent_mesh.gateway.generic.app.GenericGatewayApp
  app_config:
    namespace: "myorg/dev"
    gateway_id: "cli-gateway"

    # Point to the adapter implementation
    gateway_adapter: "examples.gateways.adapters.cli_adapter.CLIAdapter"

    # Adapter-specific configuration (none needed for CLI)
    adapter_config: {}

    # Authentication config
    auth_config:
      type: "custom"  # Uses adapter's extract_auth_claims()

    # Default agent to target
    default_agent_name: "my_agent"

    # Artifact service
    artifact_service:
      type: "filesystem"
      base_path: "./artifacts"

    # Standard gateway settings
    enable_embed_resolution: true
    artifact_handling_mode: "reference"
```

### Running the CLI Gateway

```bash
# Start the gateway
python -m solace_ai_connector examples/gateways/cli_gateway_example.yaml

# Output:
# CLI Gateway ready. Type your messages:
# > What is the weather today?
# [Calling weather API...]
# The current weather is sunny, 72°F.
#
# ---
# Next query:
```

**Total Implementation:** ~80 lines (including comments and blank lines)

---

## 6. Slack Gateway v2 Example

This example demonstrates that the adapter can fully support complex gateways with all advanced features using the hybrid handler design.

### Slack Adapter Implementation (Abbreviated)

**File:** `examples/gateways/adapters/slack_adapter_v2.py`

```python
"""
Slack Gateway Adapter v2 - Full-featured implementation.
Demonstrates:
- User authentication via Slack API
- File upload/download
- Message buffering with state management
- Status indicators with emoji
- Task cancellation buttons
- Thread-based conversation tracking
- Batch update processing (override handle_update)
"""

import asyncio
import base64
import logging
from typing import Any, Optional, Dict, Set
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.errors import SlackApiError
import requests

from solace_agent_mesh.gateway.adapter.base import GatewayAdapter
from solace_agent_mesh.gateway.adapter.types import (
    GatewayContext,
    ResponseContext,
    AuthClaims,
    SamTask,
    SamUpdate,
    SamTextPart,
    SamFilePart,
    SamDataPart,
)

log = logging.getLogger(__name__)


class SlackAdapterV2(GatewayAdapter):
    """
    Full-featured Slack gateway adapter.

    Demonstrates hybrid handler design:
    - Overrides handle_update() for atomic batch processing
    - Uses state management for tracking UI state
    """

    def __init__(self):
        self.slack_app: Optional[AsyncApp] = None
        self.slack_handler: Optional[AsyncSocketModeHandler] = None
        self.context: Optional[GatewayContext] = None

    # ==================== LIFECYCLE ====================

    async def init(self, context: GatewayContext) -> None:
        """Initialize Slack connection and event handlers"""
        self.context = context
        config = context.adapter_config

        # Initialize Slack app
        self.slack_app = AsyncApp(token=config["slack_bot_token"])

        # Register event handlers
        @self.slack_app.event("app_mention")
        async def on_mention(event, client):
            log.info("Received app_mention event")
            try:
                await context.handle_external_input(event)
            except Exception as e:
                log.error(f"Error handling mention: {e}")
                await client.chat_postMessage(
                    channel=event["channel"],
                    thread_ts=event.get("thread_ts") or event["ts"],
                    text=f":warning: Error: {e}"
                )

        @self.slack_app.event("message")
        async def on_message(event, client):
            # Only handle DMs
            if event.get("channel_type") == "im":
                await context.handle_external_input(event)

        # Register cancel button handler
        @self.slack_app.action("cancel_task_button")
        async def on_cancel(ack, body, client):
            await ack()
            task_id = body["actions"][0]["value"]
            log.info(f"Cancel requested for task {task_id}")
            await context.cancel_task(task_id)

            # Update UI
            await client.chat_update(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
                text=":octagonal_sign: Cancelling..."
            )

        # Start Socket Mode handler
        self.slack_handler = AsyncSocketModeHandler(
            self.slack_app,
            config["slack_app_token"]
        )

        asyncio.create_task(self.slack_handler.start_async())
        log.info("Slack adapter initialized and listening")

    async def cleanup(self) -> None:
        """Stop Slack handler"""
        if self.slack_handler:
            self.slack_handler.close()

    # ==================== AUTHENTICATION ====================

    async def extract_auth_claims(self, event: Dict) -> Optional[AuthClaims]:
        """
        Extract Slack user identity.
        Fetches email from Slack API, falls back to slack:team:user format.
        """
        user_id = event.get("user")
        team_id = event.get("team") or event.get("team_id")

        if not user_id or not team_id:
            log.warning("Missing user_id or team_id in Slack event")
            return None

        # Try to get user email
        try:
            response = await self.slack_app.client.users_info(user=user_id)
            email = response["user"]["profile"].get("email")

            if email:
                return AuthClaims(
                    user_id=email,
                    email=email,
                    source="slack_api",
                    raw_context={
                        "slack_user_id": user_id,
                        "slack_team_id": team_id
                    }
                )
        except SlackApiError as e:
            log.warning(f"Failed to fetch Slack user email: {e}")

        # Fallback to Slack IDs
        return AuthClaims(
            user_id=f"slack:{team_id}:{user_id}",
            source="slack_fallback",
            raw_context={
                "slack_user_id": user_id,
                "slack_team_id": team_id
            }
        )

    # ==================== INBOUND ====================

    async def prepare_task(self, event: Dict) -> SamTask:
        """
        Convert Slack event to SamTask.
        Handles text, file downloads, and thread context.
        """
        parts = []

        # Extract text and resolve mentions
        text = event.get("text", "")
        if text:
            resolved_text = await self._resolve_mentions(text)
            parts.append(self.context.create_text_part(resolved_text))

        # Download and attach files
        files_info = event.get("files", [])
        if files_info:
            for file_info in files_info:
                file_bytes = await self._download_file(file_info)
                parts.append(
                    self.context.create_file_part_from_bytes(
                        name=file_info["name"],
                        content_bytes=file_bytes,
                        mime_type=file_info.get("mimetype", "application/octet-stream")
                    )
                )

        # Add Slack context as data part
        parts.append(
            self.context.create_data_part({
                "type": "slack_context",
                "channel_type": event.get("channel_type"),
                "event_type": event.get("type"),
                "timestamp": event.get("ts")
            })
        )

        # Generate conversation ID from thread
        channel_id = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]
        conversation_id = f"slack:{channel_id}:{thread_ts}"

        return SamTask(
            parts=parts,
            conversation_id=conversation_id,
            target_agent=self.context.config.get("default_agent_name", "assistant"),
            is_streaming=True,
            platform_context={
                "channel": channel_id,
                "thread_ts": thread_ts,
                "message_ts": event["ts"]
            }
        )

    # ==================== OUTBOUND (BATCH PROCESSING) ====================

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """
        Override handle_update for atomic batch processing.

        This allows us to:
        1. Accumulate all text parts before updating UI
        2. Process files separately
        3. Extract status signals for separate status message
        """
        task_id = context.task_id
        channel = context.platform_context["channel"]
        thread_ts = context.platform_context["thread_ts"]

        # Separate parts by type
        text_parts = []
        file_parts = []
        status_signal = None

        for part in update.parts:
            if isinstance(part, SamTextPart):
                text_parts.append(part)
            elif isinstance(part, SamFilePart):
                file_parts.append(part)
            elif isinstance(part, SamDataPart):
                # Extract status signals
                if part.data.get("type") == "agent_progress_update":
                    status_signal = part.data.get("status_text")

        # Update content message with accumulated text
        if text_parts:
            combined_text = "".join(p.text for p in text_parts)
            await self._update_content_message(task_id, combined_text, channel, thread_ts)

        # Upload files
        for file_part in file_parts:
            await self._upload_file(file_part, channel, thread_ts)

        # Update status message
        if status_signal:
            await self._update_status_message(task_id, status_signal, channel, thread_ts)

    async def handle_text_chunk(self, text: str, context: ResponseContext) -> None:
        """
        Not called (we override handle_update).
        But required by ABC, so provide implementation.
        """
        # This won't be called since we override handle_update
        pass

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """Update status to complete"""
        task_id = context.task_id
        channel = context.platform_context["channel"]

        # Update status message
        status_ts = self.context.get_task_state(task_id, "status_ts")
        if status_ts:
            await self.slack_app.client.chat_update(
                channel=channel,
                ts=status_ts,
                text=":checkered_flag: Complete!"
            )

        # Flush final content buffer
        buffer = self.context.get_task_state(task_id, "buffer", "")
        content_ts = self.context.get_task_state(task_id, "content_ts")
        if buffer and content_ts:
            formatted = self._format_for_slack(buffer)
            await self.slack_app.client.chat_update(
                channel=channel,
                ts=content_ts,
                text=formatted
            )

        # State automatically cleaned up after this method returns

    async def handle_error(self, error_message: str, context: ResponseContext) -> None:
        """Display error in Slack"""
        channel = context.platform_context["channel"]
        thread_ts = context.platform_context["thread_ts"]

        await self.slack_app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f":x: Error: {error_message}"
        )

    # ==================== HELPER METHODS ====================

    async def _update_content_message(
        self, task_id: str, text: str, channel: str, thread_ts: str
    ) -> None:
        """Update or create content message with buffering"""
        # Get/update buffer
        buffer = self.context.get_task_state(task_id, "buffer", "")
        buffer += text
        self.context.set_task_state(task_id, "buffer", buffer)

        # Format for Slack
        formatted = self._format_for_slack(buffer)

        # Update or create message
        content_ts = self.context.get_task_state(task_id, "content_ts")
        if content_ts:
            await self.slack_app.client.chat_update(
                channel=channel,
                ts=content_ts,
                text=formatted
            )
        else:
            response = await self.slack_app.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=formatted
            )
            self.context.set_task_state(task_id, "content_ts", response["ts"])

    async def _update_status_message(
        self, task_id: str, status_text: str, channel: str, thread_ts: str
    ) -> None:
        """Update or create status message"""
        formatted_status = f":thinking_face: {status_text}"

        # Add cancel button
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": formatted_status}
            },
            {
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "style": "danger",
                    "action_id": "cancel_task_button",
                    "value": task_id
                }]
            }
        ]

        status_ts = self.context.get_task_state(task_id, "status_ts")
        if status_ts:
            await self.slack_app.client.chat_update(
                channel=channel,
                ts=status_ts,
                text=formatted_status,
                blocks=blocks
            )
        else:
            response = await self.slack_app.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=formatted_status,
                blocks=blocks
            )
            self.context.set_task_state(task_id, "status_ts", response["ts"])

    async def _upload_file(
        self, file_part: SamFilePart, channel: str, thread_ts: str
    ) -> None:
        """Upload file to Slack"""
        if file_part.content_bytes:
            await self.slack_app.client.files_upload_v2(
                channel=channel,
                thread_ts=thread_ts,
                filename=file_part.name,
                content=file_part.content_bytes
            )
        elif file_part.uri:
            await self.slack_app.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f":link: {file_part.name}\n{file_part.uri}"
            )

    async def _resolve_mentions(self, text: str) -> str:
        """Replace <@USER_ID> with email or name"""
        import re
        mention_pattern = re.compile(r"<@([UW][A-Z0-9]+)>")
        user_ids = set(mention_pattern.findall(text))

        for user_id in user_ids:
            try:
                response = await self.slack_app.client.users_info(user=user_id)
                email = response["user"]["profile"].get("email")
                if email:
                    text = text.replace(f"<@{user_id}>", email)
            except SlackApiError:
                pass

        return text

    async def _download_file(self, file_info: Dict) -> bytes:
        """Download file from Slack"""
        url = file_info["url_private"]
        headers = {"Authorization": f"Bearer {self.context.adapter_config['slack_bot_token']}"}

        response = await asyncio.to_thread(
            requests.get, url, headers=headers, timeout=30
        )
        response.raise_for_status()
        return response.content

    def _format_for_slack(self, text: str) -> str:
        """Convert markdown to Slack format"""
        import re
        # Convert [text](url) to <url|text>
        text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<\2|\1>', text)
        return text
```

### Slack Gateway v2 Configuration

**File:** `examples/gateways/slack_gateway_v2_example.yaml`

```yaml
name: slack_gateway_v2
log_level: INFO

broker:
  host: localhost:55555
  vpn_name: default
  username: default
  password: default

app:
  class_name: solace_agent_mesh.gateway.generic.app.GenericGatewayApp
  app_config:
    namespace: "myorg/production"
    gateway_id: "slack-gateway-v2"

    # Adapter implementation
    gateway_adapter: "examples.gateways.adapters.slack_adapter_v2.SlackAdapterV2"

    # Adapter-specific configuration
    adapter_config:
      slack_bot_token: "${SLACK_BOT_TOKEN}"
      slack_app_token: "${SLACK_APP_TOKEN}"
      initial_status_message: ":thinking_face: Thinking..."
      correct_markdown_formatting: true

    # Authentication (custom via adapter)
    auth_config:
      type: "custom"

    # Default agent
    default_agent_name: "assistant"

    # Identity enrichment (optional)
    identity_service:
      type: "ldap"
      ldap_server: "ldap://ldap.example.com"
      base_dn: "dc=example,dc=com"

    # Artifact service
    artifact_service:
      type: "gcs"
      bucket_name: "my-artifacts-bucket"
      artifact_scope: "namespace"

    # Gateway settings
    enable_embed_resolution: true
    artifact_handling_mode: "embed"  # Embed bytes for Slack
    gateway_max_artifact_resolve_size_bytes: 10485760  # 10MB
```

### Key Features Demonstrated

1. **Hybrid Handler Design**: Overrides `handle_update()` for atomic batch processing
2. **State Management**: Uses `get_task_state()` / `set_task_state()` for tracking UI elements
3. **User Authentication**: Fetches email from Slack API, falls back to ID
4. **File Handling**: Downloads Slack files, converts to SamFilePart
5. **Message Buffering**: Accumulates streaming text, updates single message
6. **Status Updates**: Shows progress with emoji, includes cancel button
7. **Task Cancellation**: Interactive button triggers `context.cancel_task()`
8. **Conversation Tracking**: Thread TS → conversation_id mapping
9. **Markdown Formatting**: Converts to Slack's format

**Total Implementation:** ~300 lines (vs ~1500 in current implementation)

---

## 7. Configuration Examples

### Example 1: CLI Gateway (No Auth)

```yaml
app:
  class_name: solace_agent_mesh.gateway.generic.app.GenericGatewayApp
  app_config:
    namespace: "myorg/dev"
    gateway_adapter: "my_gateways.cli.CLIAdapter"

    adapter_config: {}

    auth_config:
      type: "custom"  # Uses adapter's extract_auth_claims()

    default_agent_name: "my_agent"

    artifact_service:
      type: "filesystem"
      base_path: "./artifacts"
```

### Example 2: HTTP Gateway with OAuth Client Credentials

```yaml
app:
  class_name: solace_agent_mesh.gateway.generic.app.GenericGatewayApp
  app_config:
    namespace: "myorg/production"
    gateway_adapter: "my_gateways.http.HTTPAdapter"

    adapter_config:
      http_host: "0.0.0.0"
      http_port: 8080

    # OAuth client credentials (fully managed by generic gateway)
    auth_config:
      type: "oauth_client_creds"
      token_url: "https://auth.example.com/oauth/token"
      client_id: "${OAUTH_CLIENT_ID}"
      client_secret: "${OAUTH_CLIENT_SECRET}"
      scopes: ["api.read", "api.write"]

    artifact_service:
      type: "gcs"
      bucket_name: "artifacts-bucket"
```

### Example 3: Discord Gateway with Static Bearer Token

```yaml
app:
  class_name: solace_agent_mesh.gateway.generic.app.GenericGatewayApp
  app_config:
    namespace: "myorg/community"
    gateway_adapter: "my_gateways.discord.DiscordAdapter"

    adapter_config:
      discord_application_id: "${DISCORD_APP_ID}"

    # Static bearer token (fully managed by generic gateway)
    auth_config:
      type: "static_bearer"
      token: "${DISCORD_BOT_TOKEN}"

    artifact_service:
      type: "s3"
      bucket_name: "discord-artifacts"
      endpoint_url: "https://minio.example.com"
```

### Example 4: Teams Gateway with API Key

```yaml
app:
  class_name: solace_agent_mesh.gateway.generic.app.GenericGatewayApp
  app_config:
    namespace: "myorg/enterprise"
    gateway_adapter: "my_gateways.teams.TeamsAdapter"

    adapter_config:
      teams_webhook_url: "${TEAMS_WEBHOOK}"

    # API key authentication (fully managed by generic gateway)
    auth_config:
      type: "api_key"
      api_key_header: "X-Teams-API-Key"
      api_key_value: "${TEAMS_API_KEY}"

    # Identity enrichment via LDAP
    identity_service:
      type: "ldap"
      ldap_server: "ldaps://ldap.corp.example.com:636"
      base_dn: "dc=corp,dc=example,dc=com"
      bind_dn: "cn=service,dc=corp,dc=example,dc=com"
      bind_password: "${LDAP_PASSWORD}"

    artifact_service:
      type: "filesystem"
      base_path: "/var/lib/sam/artifacts"
```

### Example 5: Webhook Gateway with OAuth User Flow

```yaml
app:
  class_name: solace_agent_mesh.gateway.generic.app.GenericGatewayApp
  app_config:
    namespace: "myorg/webhooks"
    gateway_adapter: "my_gateways.webhook.WebhookAdapter"

    adapter_config:
      webhook_port: 9000
      webhook_secret: "${WEBHOOK_SECRET}"

    # OAuth user flow (adapter must implement auth redirect)
    auth_config:
      type: "oauth_user"
      auth_url: "https://oauth.example.com/authorize"
      token_url: "https://oauth.example.com/token"
      client_id: "${OAUTH_CLIENT_ID}"
      client_secret: "${OAUTH_CLIENT_SECRET}"
      scopes: ["user.read", "user.email"]
      redirect_uri: "https://webhook.example.com/oauth/callback"

    artifact_service:
      type: "memory"
```

---

### Design Note: Webhook Gateway Use Case

The multi-endpoint gateway pattern (with `endpoint_context` parameter) and SAC template processing support (`process_sac_template()`) were specifically designed to support the existing webhook gateway implementation. The webhook gateway demonstrates several advanced patterns:

- **Multi-endpoint configuration**: Single adapter instance handling multiple HTTP endpoints, each with its own authentication, target agent, and payload transformation rules
- **Fire-and-forget pattern**: Immediate HTTP 202 acknowledgment without streaming responses (outbound handlers are no-ops)
- **Template-based payload transformation**: Using SAC templates to convert structured webhook payloads (JSON, YAML, form data, binary) into text prompts for agents
- **Per-endpoint authentication**: Different endpoints can use different auth schemes (none, token, basic auth)
- **Flexible payload handling**: Support for various formats (JSON, YAML, form_data, binary) with optional artifact storage

This use case validates that the adapter framework can support complex, real-world gateway patterns beyond simple streaming scenarios like Slack or CLI.

---

## Appendix: Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create `solace_agent_mesh/gateway/adapter/` package
- [ ] Define SAM types in `types.py` using Pydantic models
- [ ] Define `GatewayAdapter` ABC in `base.py` with hybrid handler design
- [ ] Implement translation functions (SAM types ↔ A2A types)

### Phase 2: Generic Gateway
- [ ] Create `solace_agent_mesh/gateway/generic/` package
- [ ] Implement `GenericGatewayApp` in `app.py`
- [ ] Implement `GenericGatewayComponent` in `component.py`
- [ ] Implement dynamic adapter loading in `loader.py`
- [ ] Implement authentication handling (OAuth, tokens, etc.)
- [ ] Implement state management (task and session state)

### Phase 3: Examples
- [ ] Create CLI adapter example
- [ ] Create Slack v2 adapter example
- [ ] Add configuration examples
- [ ] Validate Slack v2 has feature parity

### Phase 4: Testing
- [ ] Unit tests for type translations
- [ ] Unit tests for Pydantic model validation
- [ ] Unit tests for adapter loading
- [ ] Integration test with mock adapter
- [ ] Integration test with CLI adapter
- [ ] Integration test with Slack v2 adapter (hybrid handler)
- [ ] Test state management functionality

### Phase 5: Documentation
- [ ] Gateway adapter development guide
- [ ] API reference documentation
- [ ] Tutorial: Building your first gateway in 10 minutes
- [ ] Comparison: Old vs new approach
- [ ] State management best practices guide
