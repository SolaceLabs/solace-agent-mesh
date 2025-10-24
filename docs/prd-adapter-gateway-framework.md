# PRD: Adapter-based Gateway Framework

## 1. Executive Summary

### Overview
This document proposes the "Adapter-based Gateway Framework," a new system within Solace Agent Mesh (SAM) designed to dramatically simplify the development of new gateway implementations. This framework introduces a clean abstraction layer that separates platform-specific logic from the complexities of the A2A protocol and Solace AI Connector (SAC) lifecycle management. By providing a generic, reusable "Host" component and a simple "Adapter" interface for developers to implement, this feature will reduce the effort to create a new gateway from hundreds of lines of complex code to tens of lines for most use cases.

### Goals
1.  **Reduce Complexity**: Enable developers to create basic gateways (e.g., CLI, simple HTTP) in under 100 lines of code.
2.  **Maintain Power**: Fully support all features of complex gateways like Slack, including streaming, file handling, status updates, and task cancellation.
3.  **Decouple A2A Protocol**: Shield gateway developers from A2A protocol internals (`TaskStatusUpdateEvent`, `JSONRPCResponse`, etc.) by providing a stable, simplified API contract.
4.  **Plugin-like Architecture**: Make new gateways as easy to develop as agent tools—implement a `BaseGatewayAdapter` and provide it via configuration.
5.  **Future-Proof**: Protect gateway adapter implementations from A2A protocol evolution through a stable abstraction layer managed by the Host component.

### Current Pain Points
-   Gateway developers must understand and handle complex A2A protocol types and message construction.
-   Significant boilerplate is required for managing the SAC component lifecycle, asynchronous message processing, and state management.
-   The barrier to entry for creating simple gateways is prohibitively high, stifling community contributions and rapid prototyping.
-   Implementations are tightly coupled to the `BaseGatewayComponent` architecture.

### Value Proposition
**Before**: Implementing a basic CLI gateway requires:
-   Extending `BaseGatewayComponent` and understanding the SAC component model.
-   Implementing 5+ abstract methods with complex signatures and A2A types.
-   Manually managing streaming buffers, embed resolution, and error states.
-   ~500+ lines of code.

**After**: Implementing the same CLI gateway requires:
-   Implementing the `BaseGatewayAdapter` interface with clear, focused methods.
-   Working with simple, stable `Sam*` types (e.g., `SamTaskRequest`).
-   No knowledge of A2A protocol internals is needed.
-   ~80 lines of code.

---

## 2. Requirements

### Functional Requirements

#### FR-1: Gateway Adapter Interface (The Contract)
-   SHALL provide an abstract base class `BaseGatewayAdapter` that developers implement.
-   SHALL define lifecycle methods: `setup()` and `cleanup()`.
-   SHALL define inbound (platform-to-agent) callback methods: `get_authentication_context()` and `create_sam_task_request()`.
-   SHALL define outbound (agent-to-platform) handler methods: `handle_update()`, `handle_final_response()`, and `handle_error()`.

#### FR-2: Stable SAM Type System
-   SHALL define a set of stable, Pydantic-based types for the adapter framework (e.g., `SamTaskRequest`, `AuthenticationContext`, `SamUpdate`).
-   SHALL ensure these types are decoupled from the underlying A2A protocol types.
-   SHALL ensure the Host component is responsible for all translation between SAM types and A2A types.

#### FR-3: Generic Host Component (`AdapterGatewayComponent`)
-   SHALL provide a concrete `AdapterGatewayComponent` that extends `BaseGatewayComponent`.
-   SHALL dynamically load a `BaseGatewayAdapter` implementation from a Python module path specified in the configuration.
-   SHALL orchestrate the entire request lifecycle: calling the adapter for auth context, then for the task request, and finally submitting to the A2A system.
-   SHALL receive all A2A responses, translate them into stable SAM types, and route them to the appropriate adapter handler methods.

#### FR-4: Context Objects
-   SHALL provide a `GatewayContext` object to the adapter during `setup()`, giving it access to:
    -   Gateway configuration via `get_config()` and `get_adapter_config()`.
    -   A method to initiate a task: `submit_task_from_adapter()`.
    -   Abstracted services for timers, caching, and artifact handling.
    -   State management helpers (`get_session_state`, `set_session_state`).
-   SHALL provide a `ResponseContext` object with every outbound handler call (`handle_update`, etc.), containing the `task_id`, `user_id`, and the `external_request_context` originally provided by the adapter.

#### FR-5: Centralized Authentication
-   SHALL support common authentication schemes (OAuth, Bearer Token, API Key) managed by the `AdapterGatewayComponent` based on configuration.
-   SHALL use the adapter's `get_authentication_context()` method to extract the necessary credentials from the platform-specific event.
-   SHALL handle OAuth token caching and refresh automatically where applicable.
-   SHALL integrate with the existing `identity_service` for user enrichment after initial credential validation.

#### FR-6: State Management
-   SHALL provide a mechanism for adapters to store and retrieve state on a per-task and per-session basis via the `GatewayContext` and `ResponseContext`, abstracting the underlying storage mechanism.

#### FR-7: Feature Completeness
-   SHALL support all features of existing complex gateways (using Slack as a reference), including streaming text, file uploads/downloads, status signals, task cancellation, and error reporting.

#### FR-8: Configuration
-   SHALL use a new `AdapterGatewayApp` that supports YAML configuration specifying:
    -   `adapter_class`: The Python module path to the adapter implementation.
    -   `adapter_config`: A dedicated block for adapter-specific settings.
    -   All standard gateway settings (`namespace`, `artifact_service`, etc.).

### Non-Functional Requirements

#### NFR-1: Developer Experience
-   The API SHOULD be intuitive, with clear, consistent naming conventions.
-   Documentation SHOULD include working examples for both simple and complex adapters.
-   Type hints MUST be comprehensive to provide excellent IDE support and static analysis.

#### NFR-2: Backward Compatibility
-   SHALL NOT break existing gateway implementations that inherit directly from `BaseGatewayComponent`.
-   The new `AdapterGatewayApp` and the existing `WebUIBackendApp` / `SlackGatewayApp` SHALL coexist.

#### NFR-3: Maintainability
-   The adapter framework's stable types SHALL be defined in a single, well-documented module.
-   The boundary between the simple adapter and the advanced `BaseGatewayComponent` path SHALL be clearly documented. No "escape hatches" will be provided in the adapter framework to maintain its simplicity.

---

## 3. Architecture Overview

### Component Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    YAML Configuration                        │
│  - adapter_class: "my_adapter.MyAdapter"                     │
│  - adapter_config: {...}                                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   AdapterGatewayApp                          │
│  (extends BaseGatewayApp)                                    │
│  - Validates configuration                                   │
│  - Creates AdapterGatewayComponent instance                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              AdapterGatewayComponent (The "Host")            │
│  (extends BaseGatewayComponent)                              │
│  - Loads adapter dynamically                                 │
│  - Implements all BaseGatewayComponent abstract methods      │
│  - Manages A2A protocol, state, auth, timers, etc.           │
│  - Provides GatewayContext to the adapter                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 BaseGatewayAdapter (ABC)                     │
│  User implements:                                            │
│  - setup() / cleanup()                                       │
│  - get_authentication_context()                              │
│  - create_sam_task_request()                                 │
│  - handle_update(), handle_final_response(), handle_error()  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                External Platform                             │
│  (Slack, CLI, Discord, Teams, etc.)                          │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow

```
1. Platform Event Arrives
   └─→ Adapter's listener (e.g., Slack @mention) receives it.

2. Adapter Calls Host
   └─→ Calls context.submit_task_from_adapter(raw_event).

3. Host Orchestrates Submission
   ├─→ Calls adapter.get_authentication_context(raw_event) to get credentials.
   ├─→ Host validates credentials and enriches user via IdentityService.
   ├─→ On success, calls adapter.create_sam_task_request(raw_event) to get content.
   ├─→ Host translates SamTaskRequest → A2A Message.
   ├─→ Host manages artifact handling based on policy.
   └─→ Host submits to A2A, stores context, and returns task_id.

4. Response Handling (Streaming)
   ├─→ Host receives A2A events (TaskStatusUpdateEvent, etc.).
   ├─→ Host parses and translates A2A event → SamUpdate object.
   ├─→ Host retrieves ResponseContext for the task.
   └─→ Calls adapter.handle_update(update, context).

5. Task Completion
   ├─→ Host receives final A2A Task object.
   ├─→ Host translates → SamFinalResponse object.
   └─→ Calls adapter.handle_final_response(response, context).
```

### Class Prototypes

```python
# ============================================
# SAM Adapter Types (solace_agent_mesh/gateway/adapter/types.py)
# ============================================
from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Any, Optional, Union, Literal

# --- Types for Adapter -> Host communication ---

class AuthenticationContext(BaseModel):
    user_id: Optional[str] = None
    token: Optional[str] = None
    token_type: Optional[Literal["bearer", "api_key"]] = None
    raw_context: Dict[str, Any] = Field(default_factory=dict)

class SamTaskRequest(BaseModel):
    target_agent_name: str
    parts: List[Dict[str, Any]] = Field(default_factory=list)
    external_request_context: Dict[str, Any] = Field(default_factory=dict)
    is_streaming: bool = True
    a2a_session_id: Optional[str] = None

# --- Types for Host -> Adapter communication ---

class SamFile(BaseModel):
    name: str
    content: Optional[bytes] = None
    mime_type: str
    uri: Optional[str] = None

    @model_validator(mode='after')
    def check_content_or_uri(cls, self):
        if self.content is None and self.uri is None:
            raise ValueError("Either 'content' or 'uri' must be provided.")
        return self

class SamStatusSignal(BaseModel):
    type: str
    data: Dict[str, Any]

# Part types for Host -> Adapter communication
class SamTextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str

class SamFilePart(BaseModel):
    type: Literal["file"] = "file"
    file: SamFile

class SamStatusSignalPart(BaseModel):
    type: Literal["signal"] = "signal"
    signal: SamStatusSignal

SamPart = Union[SamTextPart, SamFilePart, SamStatusSignalPart]


class SamUpdate(BaseModel):
    parts: List[SamPart] = Field(default_factory=list)

class SamFinalResponse(BaseModel):
    parts: List[SamPart] = Field(default_factory=list)
    status: str
    status_message: Optional[str] = None

class SamError(BaseModel):
    message: str
    code: int
    details: Optional[Dict[str, Any]] = None

# ============================================
# Context Objects (Provided by Host)
# ============================================

class GatewayContext(Protocol):
    async def submit_task_from_adapter(self, external_event_data: Any) -> Optional[str]: ...
    async def cancel_task(self, task_id: str) -> None: ...
    def get_config(self, key: str, default: Any = None) -> Any: ...
    def get_adapter_config(self) -> Dict[str, Any]: ...
    # ... methods for timers, cache, artifacts, state ...

class ResponseContext(BaseModel):
    task_id: str
    user_id: str
    a2a_session_id: str
    external_request_context: Dict[str, Any]

# ============================================
# Base Gateway Adapter (solace_agent_mesh/gateway/adapter/base.py)
# ============================================

class BaseGatewayAdapter(ABC):
    def __init__(self, context: GatewayContext):
        self.context = context
        self.log = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def setup(self) -> None: ...

    @abstractmethod
    def cleanup(self) -> None: ...

    @abstractmethod
    def get_authentication_context(self, external_event_data: Any) -> Optional[AuthenticationContext]: ...

    @abstractmethod
    def create_sam_task_request(self, external_event_data: Any) -> SamTaskRequest: ...

    @abstractmethod
    def handle_update(self, update: SamUpdate, context: ResponseContext) -> None: ...

    @abstractmethod
    def handle_final_response(self, response: SamFinalResponse, context: ResponseContext) -> None: ...

    @abstractmethod
    def handle_error(self, error: SamError, context: ResponseContext) -> None: ...
```

---

## 4. Simple CLI Gateway Example

This example demonstrates the simplicity of creating a new gateway using the adapter framework.

### CLI Adapter Implementation

**File:** `examples/gateways/adapters/cli_adapter.py`

```python
import asyncio
import sys
from typing import Any, Optional

from solace_agent_mesh.gateway.adapter.base import BaseGatewayAdapter
from solace_agent_mesh.gateway.adapter.types import (
    GatewayContext,
    ResponseContext,
    AuthenticationContext,
    SamTaskRequest,
    SamUpdate,
    SamFinalResponse,
    SamError,
)

class CLIAdapter(BaseGatewayAdapter):
    """Minimal CLI gateway - no authentication, simple text I/O."""

    def setup(self) -> None:
        self.context: GatewayContext  # For type hinting
        self.running = True
        asyncio.create_task(self._read_input_loop())
        print("CLI Gateway ready. Type your messages:")

    def cleanup(self) -> None:
        self.running = False

    async def _read_input_loop(self):
        loop = asyncio.get_event_loop()
        while self.running:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line or not self.running: break
            line = line.strip()
            if line:
                await self.context.submit_task_from_adapter(line)

    def get_authentication_context(self, external_event_data: str) -> Optional[AuthenticationContext]:
        return AuthenticationContext(user_id="cli_user", raw_context={"source": "local"})

    def create_sam_task_request(self, external_event_data: str) -> SamTaskRequest:
        return SamTaskRequest(
            target_agent_name=self.context.get_config("default_agent_name"),
            parts=[{"type": "text", "text": external_event_data}],
            a2a_session_id="cli_session_1" # Persistent session
        )

    def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        for part in update.parts:
            if part.type == "signal":
                if part.signal.type == "agent_progress_update":
                    print(f"\r[{part.signal.data.get('status_text', '...')}]", end='', file=sys.stderr, flush=True)
            elif part.type == "text":
                print(part.text, end='', flush=True)
            elif part.type == "file":
                print(f"\n[File Received: {part.file.name}]", flush=True)

    def handle_final_response(self, response: SamFinalResponse, context: ResponseContext) -> None:
        # Process any final parts that might have come with the final response
        for part in response.parts:
            if part.type == "text":
                print(part.text, end='', flush=True)
            elif part.type == "file":
                print(f"\n[File Received: {part.file.name}]", flush=True)
        print("\n\n---\nNext query:", flush=True)

    def handle_error(self, error: SamError, context: ResponseContext) -> None:
        print(f"\nError: {error.message}\n", file=sys.stderr)
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
  class_name: solace_agent_mesh.gateway.adapter.app.AdapterGatewayApp
  app_config:
    namespace: "myorg/dev"
    gateway_id: "cli-gateway"
    adapter_class: "examples.gateways.adapters.cli_adapter.CLIAdapter"
    default_agent_name: "my_agent"
    adapter_config: {} # No specific config needed for this simple adapter
```

**Total Implementation:** ~60 lines.

---

## 5. Slack Gateway Adapter Example (Abbreviated)

This example demonstrates how the adapter framework can support a complex, real-world gateway.

**File:** `sam_slack/adapter.py`

```python
import asyncio
from slack_bolt.async_app import AsyncApp
# ... other imports

from solace_agent_mesh.gateway.adapter.base import BaseGatewayAdapter
from solace_agent_mesh.gateway.adapter.types import (
    GatewayContext, ResponseContext, AuthenticationContext, SamTaskRequest,
    SamUpdate, SamFinalResponse, SamError
)

class SlackGatewayAdapter(BaseGatewayAdapter):
    def setup(self) -> None:
        self.context: GatewayContext
        adapter_config = self.context.get_adapter_config()
        self.slack_app = AsyncApp(token=adapter_config["slack_bot_token"])
        # ... register slack_bolt handlers ...

        @self.slack_app.event("app_mention")
        async def on_mention(event, client):
            await self.context.submit_task_from_adapter(event)

        # ... start SocketModeHandler in a background task ...

    def cleanup(self) -> None:
        # ... stop SocketModeHandler ...

    def get_authentication_context(self, event: dict) -> Optional[AuthenticationContext]:
        user_id = event.get("user")
        team_id = event.get("team")
        if not user_id or not team_id: return None
        # In a real implementation, we'd fetch the email here.
        return AuthenticationContext(
            user_id=f"slack:{team_id}:{user_id}",
            raw_context={"slack_user_id": user_id, "slack_team_id": team_id}
        )

    def create_sam_task_request(self, event: dict) -> SamTaskRequest:
        # ... logic to extract text, download files, resolve mentions ...
        parts = [{"type": "text", "text": event.get("text", "")}]
        channel_id = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]

        return SamTaskRequest(
            target_agent_name=self.context.get_config("default_agent_name"),
            parts=parts,
            a2a_session_id=f"slack:{channel_id}:{thread_ts}",
            external_request_context={
                "channel_id": channel_id,
                "thread_ts": thread_ts
            }
        )

    def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        # ... logic to iterate through update.parts ...
        # ... for text parts, buffer and update a single Slack message ...
        # ... for signal parts, post to a status message ...
        # ... for file parts, upload the file to Slack ...
        pass

    def handle_final_response(self, response: SamFinalResponse, context: ResponseContext) -> None:
        # ... logic to process any final parts in response.parts ...
        # ... logic to update the status message to "Complete" ...
        # ... logic to add feedback buttons ...
        pass

    def handle_error(self, error: SamError, context: ResponseContext) -> None:
        # ... logic to post an error message to the Slack thread ...
        pass
```

### Slack Gateway Adapter Configuration

**File:** `examples/gateways/slack_gateway_v2_example.yaml`

```yaml
# Solace AI Connector Example: Slack Gateway using the Adapter Framework
# This file demonstrates how to configure the generic AdapterGatewayApp
# to host the SlackGatewayAdapter.

# Required Environment Variables:
# - NAMESPACE: The A2A topic namespace (e.g., "myorg/dev").
# - SOLACE_BROKER_URL: URL of the Solace broker.
# - SOLACE_BROKER_USERNAME: Username for the Solace broker.
# - SOLACE_BROKER_PASSWORD: Password for the Solace broker.
# - SOLACE_BROKER_VPN: VPN name for the Solace broker.
# - SLACK_BOT_TOKEN: Your Slack Bot Token (starts with 'xoxb-').
# - SLACK_APP_TOKEN: Your Slack App Token for Socket Mode (starts with 'xapp-').

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: slack_gateway_v2.log

apps:
  - name: slack_gateway_app_v2
    app_base_path: .

    broker:
      broker_url: ${SOLACE_BROKER_URL}
      broker_username: ${SOLACE_BROKER_USERNAME}
      broker_password: ${SOLACE_BROKER_PASSWORD}
      broker_vpn: ${SOLACE_BROKER_VPN}

    # Use the generic AdapterGatewayApp
    app:
      class_name: solace_agent_mesh.gateway.adapter.app.AdapterGatewayApp
      app_config:
        # --- Core Gateway Config ---
        namespace: ${NAMESPACE}
        default_agent_name: "OrchestratorAgent"

        # --- Adapter Implementation ---
        adapter_class: "sam_slack.adapter.SlackGatewayAdapter"

        # --- Adapter-Specific Config ---
        # This block is passed to the adapter via context.get_adapter_config()
        adapter_config:
          slack_bot_token: ${SLACK_BOT_TOKEN}
          slack_app_token: ${SLACK_APP_TOKEN}
          initial_status_message: ":thinking_face: Thinking..."
          correct_markdown_formatting: true
          feedback_enabled: false
          slack_email_cache_ttl_seconds: 0

        # --- Standard Gateway Services & Settings ---
        artifact_service:
          type: "filesystem"
          base_path: "/tmp/sam_artifacts"
          artifact_scope: "namespace"

        enable_embed_resolution: true
        gateway_max_artifact_resolve_size_bytes: 10000000 # 10MB
        gateway_recursive_embed_depth: 3

        # --- System-wide instructions for the agent ---
        system_purpose: >
          The system is an AI Chatbot with agentic capabilities.
          It will use the agents available to provide information,
          reasoning and general assistance for the users in this system.
          **Always return useful artifacts and files that you create to the user.**
          Provide a status update before each tool call.
          Your external name is Agent Mesh.

        response_format: >
          Responses should be clear, concise, and professionally toned.
          Format responses to the user in Markdown using appropriate formatting.
          Note that the user is not able to access the internal artifacts of the system. You
          must return them, so if you create any files or artifacts, provide them to the user
          via the artifact_return embed.
```
