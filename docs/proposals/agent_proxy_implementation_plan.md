# Agent Proxy Framework - Implementation Plan

This document outlines the step-by-step plan to implement the Agent Proxy Framework. The work is divided into logical phases, starting with the foundational base classes and moving to the concrete implementation, configuration, and testing.

## Phase 1: Foundational Base Framework (`src/agent/proxies/base/`)

This phase focuses on creating the reusable, protocol-agnostic base classes for all future proxies.

1.  **Create Directory Structure:**
    1.1. Create the new directory `src/agent/proxies/`.
    1.2. Inside `proxies`, create `base/` and `a2a/` subdirectories.
    1.3. Add `__init__.py` files to `proxies/`, `proxies/base/`, and `proxies/a2a/` to make them Python packages.

2.  **Define `ProxyTaskContext`:**
    2.1. In a new file `src/agent/proxies/base/proxy_task_context.py`, define a `ProxyTaskContext` dataclass.
    2.2. This class will be similar to `TaskExecutionContext` but simplified for the proxy's needs. It should contain:
        -   `task_id: str`
        -   `a2a_context: Dict[str, Any]` (the original context from the Solace request)
        -   `cancellation_event: asyncio.Event` (to signal cancellation to the downstream task)

3.  **Implement `BaseProxyComponent`:**
    3.1. Create the file `src/agent/proxies/base/component.py`.
    3.2. Define the abstract class `BaseProxyComponent`, inheriting from `ComponentBase`.
    3.3. **Initialization (`__init__`):**
        3.3.1. Implement logic to start a dedicated `asyncio` event loop in a separate thread.
        3.3.2. Initialize the `AgentRegistry` for storing downstream agent cards.
        3.3.3. Initialize the shared `ArtifactService` based on configuration.
        3.3.4. Initialize a thread-safe `active_tasks` dictionary to store `ProxyTaskContext` objects.
    3.4. **Discovery Loop (`handle_timer_event`):**
        3.4.1. Implement the timer-based discovery loop.
        3.4.2. This loop will iterate through the `proxied_agents` configuration.
        3.4.3. For each agent, it will call the abstract method `_fetch_agent_card`.
        3.4.4. It will then rewrite the `url` of the returned `AgentCard` to the appropriate Solace topic and publish it using a helper method.
    3.5. **Event Processing (`process_event`):**
        3.5.1. Implement the main event router.
        3.5.2. It will listen for messages on the proxy's subscription topics.
        3.5.3. It will parse incoming requests (`SendTaskRequest`, `SendTaskStreamingRequest`, `CancelTaskRequest`).
        3.5.4. For `SendTask*` requests, it will create a `ProxyTaskContext`, store it in `active_tasks`, and call the abstract `_forward_request` method.
        3.5.5. For `CancelTaskRequest`, it will find the corresponding `ProxyTaskContext` and set its `cancellation_event`.
    3.6. **Response Publishing:**
        3.6.1. Create concrete helper methods (`_publish_status_update`, `_publish_final_response`, `_publish_error_response`) that subclasses can call. These methods will construct the appropriate `JSONRPCResponse` and publish it to the correct Solace topic from the original `a2a_context`.
    3.7. **Abstract Methods:**
        3.7.1. Define the abstract methods `_fetch_agent_card(self, agent_config: dict)` and `_forward_request(self, task_context: ProxyTaskContext, request: A2ARequest)`.
    3.8. **Cleanup (`cleanup`):**
        3.8.1. Implement cleanup logic to stop the async loop and cancel any active tasks.

4.  **Implement `BaseProxyApp`:**
    4.1. Create the file `src/agent/proxies/base/app.py`.
    4.2. Define the `BaseProxyApp` class, inheriting from `App`.
    4.3. Define the base `app_schema` with common configuration parameters like `namespace`, `proxied_agents`, and `artifact_service`.
    4.4. Implement the logic to generate Solace topic subscriptions for all agents listed in `proxied_agents`.
    4.5. Implement the abstract `_get_component_class` method, which will be overridden by concrete app implementations.

## Phase 2: A2A-over-HTTPS Proxy Implementation (`src/agent/proxies/a2a/`)

This phase focuses on building the concrete proxy for standard A2A agents.

5.  **Implement `A2AProxyComponent`:**
    -   Create the file `src/agent/proxies/a2a/component.py`.
    -   Define the `A2AProxyComponent` class, inheriting from `BaseProxyComponent`.
    -   **Implement `_fetch_agent_card`:**
        -   Use `a2a.client.A2ACardResolver` to fetch the `AgentCard` via HTTPS.
        -   Handle potential `A2AClientHTTPError` and other exceptions gracefully.
    -   **Implement `_forward_request`:**
        -   This is the core logic of the component.
        -   Instantiate and manage a dictionary of `a2a.client.A2AClient` instances, one for each downstream agent.
        -   **Inbound Artifact Handling:** Before sending the request, check for `FilePart`s with `artifact://` URIs. Use the `self.artifact_service` to load the content and replace the URI with the raw bytes.
        -   Call the appropriate `A2AClient` method (`send_message` or `send_message_streaming`).
        -   Use `async for` to iterate over the responses from the client.
        -   **Outbound Artifact Handling:** When a response contains an artifact, use the `self.artifact_service` to save it and rewrite the `FilePart` to an `artifact://` URI or embedded data.
        -   Call the base class's helper methods (`_publish_status_update`, etc.) to send all events back to the Solace mesh.
    -   **Authentication:**
        -   Implement logic to create and use an `AuthInterceptor` with the `A2AClient` if authentication details are provided in the configuration for a downstream agent.

6.  **Implement `A2AProxyApp`:**
    -   Create the file `src/agent/proxies/a2a/app.py`.
    -   Define the `A2AProxyApp` class, inheriting from `BaseProxyApp`.
    -   Extend the `app_schema` to include validation for A2A-specific parameters like `url` and `authentication` within the `proxied_agents` list.
    -   Override `_get_component_class` to return `A2AProxyComponent`.

## Phase 3: Configuration and Documentation

7.  **Create Example Configuration:**
    7.1. Create a new file `examples/a2a_proxy.yaml`.
    7.2. Add a complete, well-commented configuration example demonstrating how to set up the A2A proxy with one or two sample downstream agents. Include examples of authentication configuration.

8.  **Update Documentation:**
    8.1. Update the main `llm.txt` files in `src` and `agent` to include summaries of the new `proxies` subsystem.
    8.2. Create a new `proxies_llm.txt` file inside `src/agent/proxies/` to provide a detailed developer guide for the new framework.

## Phase 4: Testing

9.  **Unit Tests:**
    9.1. Add unit tests for the `BaseProxyComponent`'s concrete methods (e.g., response publishing, state management).
    9.2. Add unit tests for the `A2AProxyComponent`'s specific logic, mocking the `A2AClient` and `ArtifactService` to test artifact handling and request forwarding logic.

10. **Integration Tests:**
    10.1. Create an integration test that runs the `A2AProxyApp` alongside one or two mock downstream A2A agents (which can be simple FastAPI/Starlette apps).
    10.2. The test should verify the end-to-end flow: discovery, task submission, streaming status updates, artifact handling, and final response.
