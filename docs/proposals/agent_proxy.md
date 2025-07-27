# Feature Proposal: Agent Proxy Framework

## 1. Introduction & Goals

The Solace Agent Mesh (SAM) framework currently supports building native agents that communicate directly over the Solace event mesh. However, to expand the ecosystem, there is a need to integrate with external, pre-existing AI agents that use other communication protocols, such as standard A2A over HTTPS.

This proposal outlines the creation of an **Agent Proxy Framework** within SAM. The primary goal of this framework is to act as a bridge, making non-native external agents appear and behave as if they were first-class, native SAM agents on the Solace event mesh.

The key objectives are:
-   **Seamless Integration:** Enable SAM agents to discover and communicate with external agents using the standard Solace A2A protocol, without needing to know the external agent's underlying protocol (e.g., HTTPS).
-   **Interoperability:** Allow existing, standard A2A agents to participate in the SAM ecosystem without any modification to their code.
-   **Extensibility:** Create a foundational framework that can be extended to support various external agent protocols in the future (e.g., gRPC, proprietary APIs).

## 2. High-Level Requirements

### 2.1. Configuration-Driven
The Agent Proxy must be configurable via the standard SAM YAML files. The configuration should allow users to define a list of downstream agents to be proxied. For each agent, the configuration must specify:
- A unique name within the SAM namespace.
- The external endpoint URL.
- Any necessary authentication details (e.g., API keys, bearer tokens).

### 2.2. Agent Discovery
- At startup, the proxy must connect to each configured downstream agent and fetch its `AgentCard`.
- The proxy must then publish a modified version of this `AgentCard` to the Solace discovery topic.
- The `url` field in the published `AgentCard` must be rewritten to point to the proxy's own Solace topic, effectively advertising the external agent as a native SAM agent.
- This discovery process should repeat periodically to keep the agent cards fresh.

### 2.3. Request & Response Forwarding
- The proxy must subscribe to and listen on the Solace request topics corresponding to the agents it proxies.
- When a request is received from the Solace mesh, the proxy must translate and forward it to the appropriate downstream agent using its native protocol (e.g., an HTTPS POST request for an A2A agent).
- The proxy must handle both standard and streaming responses from the downstream agent.
- All status updates and the final response from the downstream agent must be translated back into the Solace A2A protocol and published to the correct `statusTopic` and `replyTo` topics specified in the original request.

### 2.4. Bidirectional Artifact Handling
-   **Outbound (Downstream to Solace):** If a downstream agent returns an artifact, the proxy must intercept it, store it in the shared SAM `ArtifactService`, and then forward it over the Solace mesh as either a reference (`artifact://...`) or as embedded data, based on configuration.
-   **Inbound (Solace to Downstream):** If an incoming request from the Solace mesh contains a `FilePart` with an `artifact://` URI, the proxy must use the `ArtifactService` to load the artifact's content. It will then create a new `FilePart` containing the raw `bytes` of the artifact to be sent to the downstream agent.

### 2.5. Extensibility
The framework must be designed with extensibility in mind. It should be straightforward for a developer to add support for a new type of external agent protocol by creating a new proxy implementation without altering the core framework.

## 3. Key Architectural Decisions

### 3.1. Directory Structure
To maintain a clear separation of concerns, the Agent Proxy framework will reside in a new top-level directory within the `agent` subsystem:
- **`src/agent/proxies/`**: This directory will house all proxy-related components.
- **`src/agent/proxies/base/`**: This will contain the protocol-agnostic base classes for all proxies.
- **`src/agent/proxies/a2a/`**: This will contain the initial, concrete implementation for proxying standard A2A-over-HTTPS agents.

This structure distinguishes outbound proxies from inbound `gateways`.

### 3.2. Base Class Abstraction
A new set of base classes (`BaseProxyApp`, `BaseProxyComponent`) will be created. These classes will encapsulate all generic logic related to Solace broker integration, configuration parsing, discovery publishing, and task state management. This ensures that concrete implementations only need to handle the logic specific to the downstream protocol they are proxying.

### 3.3. Concrete Implementations
The first implementation will be the `A2AProxyComponent`, which will inherit from `BaseProxyComponent`. It will be responsible for all A2A-over-HTTPS specific logic, primarily using the `a2a-python` client library (`A2ACardResolver`, `A2AClient`) for communication.

### 3.4. State Management
The proxy component will be responsible for managing the state of in-flight requests. It will maintain a mapping of incoming Solace `task_id`s to the corresponding requests made to downstream agents, ensuring that responses can be correctly routed back to the original requester on the Solace mesh.

### 3.5. Reuse of Existing Components
The proxy framework will leverage existing SAM and `a2a-python` components wherever possible, including:
- `AgentRegistry` for internal tracking of discovered downstream agents.
- `A2ACardResolver` and `A2AClient` for external communication.
- The shared `ArtifactService` for artifact persistence.
