# A2A Agent Proxy: Detailed Design

## 1. Overview

The A2A Agent Proxy is a specialized gateway within the Solace Agent Mesh (SAM) designed to bridge external, standard A2A-compliant agents into the Solace event mesh. Its primary purpose is to make agents that communicate over standard protocols (like A2A-over-HTTPS) appear and behave as if they were native SAM agents.

This allows the SAM ecosystem to seamlessly integrate with a wider range of agents, including those developed independently of the SAM framework, as long as they adhere to the A2A specification.

### Key Functionality
- **Agent Discovery:** Periodically polls downstream agents for their capabilities (`AgentCard`) and broadcasts them onto the Solace event mesh.
- **Request Forwarding:** Receives modern, spec-compliant A2A requests from the Solace mesh and forwards them to the appropriate downstream agent over its native protocol (e.g., HTTPS).
- **Response Relaying:** Relays streaming and final responses from the downstream agent back to the original requester on the Solace mesh.
- **Artifact Management:** Acts as an intermediary for artifacts, resolving `artifact://` URIs into bytes for downstream agents and saving byte-based artifacts from agents into a shared artifact store.

## 2. Architecture

The proxy is implemented as a custom SAC (Solace AI Connector) application, composed of a protocol-agnostic base and a concrete implementation for A2A-over-HTTPS.

### Core Components

- **`BaseProxyApp` / `BaseProxyComponent`:**
  - This is the protocol-agnostic foundation located in `src/agent/proxies/base/`.
  - `BaseProxyApp` handles the generation of Solace topic subscriptions for each proxied agent defined in the configuration.
  - `BaseProxyComponent` contains the core, non-blocking logic for interacting with the Solace mesh. It manages a dedicated `asyncio` event loop to handle all asynchronous operations, such as polling for discovery and forwarding requests, without blocking the main SAC framework. It also manages the lifecycle of in-flight tasks via the `ProxyTaskContext`.

- **`A2AProxyApp` / `A2AProxyComponent`:**
  - This is the concrete implementation for proxying A2A-over-HTTPS agents, located in `src/agent/proxies/a2a/`.
  - `A2AProxyApp` extends the base app to add configuration validation specific to A2A agents (e.g., URL, authentication).
  - `A2AProxyComponent` uses the `a2a-sdk` library, specifically `A2ACardResolver` and `A2AClient`, to communicate with downstream agents over HTTPS. It implements the abstract methods defined in the base component to handle the specifics of the HTTP transport.

### Threading Model

The `BaseProxyComponent` runs within the synchronous SAC framework but manages its own internal `asyncio` event loop in a separate thread. This is crucial for performance, as it allows the proxy to perform non-blocking network I/O (polling for discovery, forwarding HTTP requests) without stalling the main SAC processing thread. All events received from Solace are safely dispatched to this async loop for processing.

### Configuration

The proxy is configured via a YAML file (e.g., `examples/a2a_proxy.yaml`). Key configuration sections include:
- **`namespace`**: The root Solace topic for all A2A communication.
- **`proxied_agents`**: A list of downstream agents, where each entry defines:
  - `name`: The alias the agent will have on the Solace mesh.
  - `url`: The base HTTP(S) URL of the downstream agent.
  - `authentication`: (Optional) Credentials for the downstream agent.
- **`artifact_service`**: Configuration for the artifact store shared by the proxy. This is essential for artifact management.
- **`discovery_interval_seconds`**: How often to poll agents for their `AgentCard`.
- **`artifact_handling_mode`**: Defines how the proxy handles file parts in messages (see Artifact Management section).

## 3. Key Logic and Data Flows

### Agent Discovery

1.  **Polling:** On a configurable interval, the `A2AProxyComponent` iterates through the `proxied_agents` list.
2.  **Fetch Card:** For each agent, it uses `A2ACardResolver` to make an HTTP GET request to the agent's `/well-known/agent.json` endpoint to retrieve its `AgentCard`.
3.  **Update Registry:** The fetched card is stored in the proxy's internal `AgentRegistry`. The `name` of the card is updated to the alias specified in the proxy's configuration.
4.  **Publish to Mesh:** The proxy modifies the `url` field of the `AgentCard` to point to its own Solace topic (e.g., `solace:my/namespace/a2a/v1/agent/request/MyProxiedAgent`). It then publishes this modified card to the global discovery topic on the Solace mesh. This makes the external agent visible and addressable to all other SAM components.

### Request/Response Flow

1.  **Inbound Request:** A SAM client (e.g., another agent, a gateway) publishes a modern, spec-compliant `A2ARequest` to the proxy's Solace topic.
2.  **Validation:** The `BaseProxyComponent` receives the message. It uses `pydantic.TypeAdapter` to validate the payload directly against the `a2a.types.A2ARequest` model. No translation is performed.
3.  **Context Creation:** A `ProxyTaskContext` is created to track the state of this specific task, including its ID and cancellation status.
4.  **Artifact Resolution:** The proxy inspects the message for any `FilePart`s containing `artifact://` URIs and resolves them into byte content (see Artifact Management).
5.  **Forwarding:** The `A2AProxyComponent` uses its `A2AClient` instance to forward the (potentially modified) `A2ARequest` to the downstream agent over HTTPS.
6.  **Response Relaying:** The downstream agent responds with streaming events (`TaskStatusUpdateEvent`) and/or a final `Task` object. The proxy receives these HTTP responses.
7.  **Outbound Artifacts:** The proxy inspects the responses for any byte-based artifacts, saves them, and converts them to `artifact://` URIs (see Artifact Management).
8.  **Publish to Solace:** The proxy wraps the event/task in a `JSONRPCResponse` and publishes it to the `statusTopic` or `replyToTopic` specified in the original request's user properties, completing the round trip.

### Artifact Management

The proxy plays a crucial role as an artifact intermediary, ensuring that agents that do not share an artifact store can still exchange files seamlessly. This behavior is configured by the `artifact_handling_mode` setting.

#### Inbound Flow (Client -> Agent)

When a client sends a message containing a file reference:
1.  The proxy's `_handle_a2a_request` method inspects the incoming `A2ARequest`.
2.  It identifies any `FilePart` objects that contain a `FileWithUri` with an `artifact://` scheme.
3.  Using the `a2a.resolve_file_part_uri` helper and its configured `ArtifactService`, it loads the raw byte content of the artifact from the shared store.
4.  It creates a new `FilePart` containing a `FileWithBytes` object (with the content base64-encoded) and updates the message before forwarding it.
5.  This ensures the downstream HTTPS agent receives the actual file content, as it may not have access to the SAM artifact store.

#### Outbound Flow (Agent -> Client)

When a downstream agent returns a file in its response:
1.  The proxy's `_handle_outbound_artifacts` method in `A2AProxyComponent` inspects the `Task` or `TaskArtifactUpdateEvent` from the downstream agent.
2.  It identifies any `FilePart` objects containing raw `FileWithBytes`.
3.  It uses the `artifact_helpers.save_artifact_with_metadata` function to save these bytes into its configured `ArtifactService`, creating a new artifact version.
4.  It then creates a new `FilePart` containing a `FileWithUri` that points to the newly saved artifact (e.g., `artifact://...`).
5.  It replaces the original byte-based part with this new reference-based part before relaying the response to the original client on Solace.
6.  This allows the client to receive a lightweight reference and load the artifact's content from the shared store on demand.

## 4. Testing Strategy

The proxy's functionality is validated through a robust integration testing strategy that avoids dependencies on live downstream agents.

-   **`TestA2AAgentServer`:** A key test fixture located in `tests/integration/infrastructure/a2a_agent_server/`. This is a lightweight, in-process FastAPI server that implements the A2A-over-HTTPS protocol.
-   **Declarative Control:** The test server's behavior is controlled declaratively. The test case provides a base64-encoded JSON string in the request prompt, which tells the server exactly how to respond (e.g., which events to send, what content to include). This is managed by the `DeclarativeAgentExecutor`.
-   **`conftest.py` Integration:** The `test_a2a_agent_server` fixture is managed by `pytest` and integrated into the `shared_solace_connector` fixture. This ensures the test server is running before any tests execute.
-   **Test Scenarios:** Declarative test cases (e.g., `test_a2a_proxy_simple.yaml`) define the complete end-to-end flow, specifying the client input and the expected final output from the gateway, allowing for automated validation of the entire proxy data path.
