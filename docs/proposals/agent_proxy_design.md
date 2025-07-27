# Agent Proxy Framework - Detailed Design

## 1. Overview

This document provides the detailed design for the Agent Proxy Framework as outlined in the corresponding feature proposal. The framework will enable the Solace Agent Mesh (SAM) to integrate with external, non-native AI agents by making them appear as first-class citizens on the Solace event mesh.

This design focuses on creating a reusable base framework and an initial concrete implementation for proxying standard A2A-over-HTTPS agents.

## 2. Directory & File Structure

The new framework will be housed within the `src/agent/` directory to align it with agent-centric functionality. A new `proxies` subdirectory will be created to distinguish these outbound components from inbound `gateways`.

```
src/
└── agent/
    ├── adk/
    ├── protocol/
    ├── sac/
    ├── tools/
    └── proxies/
        ├── __init__.py
        ├── base/
        │   ├── __init__.py
        │   ├── app.py
        │   └── component.py
        └── a2a/
            ├── __init__.py
            ├── app.py
            └── component.py
```

## 3. Base Proxy Framework (`src/agent/proxies/base/`)

This directory will contain the protocol-agnostic base classes that handle all common logic for connecting to Solace and managing the proxy lifecycle.

### 3.1. `base/app.py`: `BaseProxyApp`

This class will handle application-level setup and configuration.

-   **Inheritance:** Inherits from `solace_ai_connector.flow.app.App`.
-   **Responsibilities:**
    -   Define and validate the common configuration schema for all proxies. Key parameters will include `namespace`, `proxied_agents` (a list of agent configurations), and `artifact_service`.
    -   Programmatically create the corresponding `BaseProxyComponent` instance.
    -   Generate and manage the required Solace topic subscriptions for all proxied agents.

### 3.2. `base/component.py`: `BaseProxyComponent`

This abstract class will serve as the foundation for all concrete proxy implementations.

-   **Inheritance:** Inherits from `solace_ai_connector.components.component_base.ComponentBase`.
-   **Key Attributes:**
    -   `_async_loop`, `_async_thread`: For managing a dedicated asyncio event loop.
    -   `agent_registry`: An instance of `common.agent_registry.AgentRegistry` to store the fetched (original) `AgentCard`s of downstream agents.
    -   `artifact_service`: An instance of an `adk.artifacts.BaseArtifactService` for handling artifact storage.
    -   `active_tasks`: A thread-safe dictionary to manage the state of in-flight tasks, mapping a Solace `task_id` to a `ProxyTaskContext` object.
-   **Concrete Logic (Implemented in Base Class):**
    -   **Initialization:** Connects to Solace, initializes the `agent_registry` and `artifact_service`.
    -   **Discovery Loop:** A timed loop that iterates through the `proxied_agents` config. For each agent, it calls the abstract `_fetch_agent_card` method and then publishes the returned card to the Solace discovery topic after rewriting its `url`.
    -   **Event Processing (`process_event`):** Listens for incoming Solace messages. It parses the request and routes `SendTask` and `SendTaskStreaming` requests to the abstract `_forward_request` method. It will also handle `CancelTask` requests by signaling cancellation to the appropriate active task.
    -   **State Management:** Manages the `active_tasks` dictionary, creating a context when a task starts and cleaning it up upon completion.
    -   **Response Publishing:** Provides concrete helper methods (`_publish_status_update`, `_publish_final_response`) that concrete implementations can call to send data back to the original requester on Solace.
-   **Abstract Methods (To be implemented by subclasses):**
    -   `_fetch_agent_card(self, agent_config: dict) -> AgentCard`: Fetches the `AgentCard` from a single downstream agent.
    -   `_forward_request(self, task_context: ProxyTaskContext, request: A2ARequest)`: Forwards a request to the downstream agent using its specific protocol.
-   **`ProxyTaskContext` (Inner Class or separate dataclass):**
    -   A simple data structure to hold the state for a single proxied task, including the original `a2a_context`, a cancellation event, and any other necessary correlation data.

## 4. A2A-over-HTTPS Proxy Implementation (`src/agent/proxies/a2a/`)

This directory will contain the concrete implementation for proxying standard A2A agents that communicate over HTTPS.

### 4.1. `a2a/app.py`: `A2AProxyApp`

-   **Inheritance:** Inherits from `BaseProxyApp`.
-   **Responsibilities:**
    -   Extends the base schema to add validation for A2A-specific configuration parameters within the `proxied_agents` list, such as `url` and `authentication`.

### 4.2. `a2a/component.py`: `A2AProxyComponent`

-   **Inheritance:** Inherits from `BaseProxyComponent`.
-   **Responsibilities:**
    -   **Implement `_fetch_agent_card`:**
        -   Uses the `a2a.client.A2ACardResolver` to fetch the `AgentCard` from the agent's HTTP endpoint.
    -   **Implement `_forward_request`:**
        -   Maintains a dictionary of `a2a.client.A2AClient` instances, one for each configured downstream agent.
        -   **Inbound Artifact Handling:** Before forwarding, it inspects the `A2ARequest` for any `FilePart`s with `artifact://` URIs. If found, it uses the `self.artifact_service` to load the content and replaces the URI with the raw `bytes` of the artifact.
        -   Calls the appropriate `A2AClient` method (`send_message` or `send_message_streaming`).
        -   Asynchronously iterates through the response(s) from the client.
        -   **Outbound Artifact Handling:** If a response from the downstream agent contains an artifact, it uses `self.artifact_service` to save it and rewrites the `FilePart` to use an `artifact://` URI or embedded data, according to the proxy's configuration.
        -   Uses the base class's helper methods to publish all status updates and the final response back to the Solace event mesh.
    -   **Authentication:** Leverages the `a2a.client.auth.AuthInterceptor` and `CredentialService` to manage and inject authentication credentials for downstream requests.

## 5. Configuration

A new example configuration file, `examples/a2a_proxy.yaml`, will be created to demonstrate how to configure and run the proxy.

```yaml
# examples/a2a_proxy.yaml
log:
  stdout_log_level: INFO
  log_file: a2a_proxy.log

!include shared_config.yaml

apps:
  - name: a2a_proxy_app
    app_base_path: .
    app_module: src.agent.proxies.a2a.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      artifact_service:
        type: "filesystem"
        base_path: "/tmp/sam_proxy_artifacts"
        artifact_scope: namespace
      artifact_handling_mode: "reference" # 'reference' or 'embed'

      proxied_agents:
        - name: "MarkitdownAgent" # The name it will have on the Solace mesh
          url: "http://localhost:8001" # The real HTTP endpoint
          # Optional authentication for this specific agent
          authentication:
            scheme: "bearer"
            token: "${MARKITDOWN_AGENT_TOKEN}"
        - name: "WebAgent"
          url: "http://localhost:8002"
```

## 6. Changes to Existing Files

The proposed design is self-contained within the new `src/agent/proxies/` directory. No changes to existing files in `src/agent/sac/`, `src/common/`, or other directories are anticipated for the initial implementation of this feature. All required functionality can be built within the new base and concrete proxy classes.
