# Agent Proxy Framework - Implementation Checklist

This checklist breaks down the implementation of the Agent Proxy Framework into actionable steps, mirroring the structure of the implementation plan.

## Phase 1: Foundational Base Framework (`src/agent/proxies/base/`)

-   [x] **1. Create Directory Structure:**
    -   [x] 1.1. Create the new directory `src/agent/proxies/`.
    -   [x] 1.2. Inside `proxies`, create `base/` and `a2a/` subdirectories.
    -   [x] 1.3. Add `__init__.py` files to `proxies/`, `proxies/base/`, and `proxies/a2a/`.

-   [x] **2. Define `ProxyTaskContext`:**
    -   [x] 2.1. Create the file `src/agent/proxies/base/proxy_task_context.py`.
    -   [x] 2.2. Define the `ProxyTaskContext` dataclass with `task_id`, `a2a_context`, and `cancellation_event`.

-   [x] **3. Implement `BaseProxyComponent`:**
    -   [x] 3.1. Create the file `src/agent/proxies/base/component.py`.
    -   [x] 3.2. Define the abstract class `BaseProxyComponent`, inheriting from `ComponentBase`.
    -   [x] 3.3. **Initialization (`__init__`):**
        -   [x] 3.3.1. Implement logic to start a dedicated `asyncio` event loop in a separate thread.
        -   [x] 3.3.2. Initialize the `AgentRegistry` for storing downstream agent cards.
        -   [x] 3.3.3. Initialize the shared `ArtifactService` based on configuration.
        -   [x] 3.3.4. Initialize a thread-safe `active_tasks` dictionary to store `ProxyTaskContext` objects.
    -   [x] 3.4. **Discovery Loop (`handle_timer_event`):**
        -   [x] 3.4.1. Implement the timer-based discovery loop.
        -   [x] 3.4.2. This loop will iterate through the `proxied_agents` configuration.
        -   [x] 3.4.3. For each agent, it will call the abstract method `_fetch_agent_card`.
        -   [x] 3.4.4. It will then rewrite the `url` of the returned `AgentCard` to the appropriate Solace topic and publish it.
    -   [x] 3.5. **Event Processing (`process_event`):**
        -   [x] 3.5.1. Implement the main event router.
        -   [x] 3.5.2. It will listen for messages on the proxy's subscription topics.
        -   [x] 3.5.3. It will parse incoming requests (`SendTaskRequest`, `SendTaskStreamingRequest`, `CancelTaskRequest`).
        -   [x] 3.5.4. For `SendTask*` requests, it will create a `ProxyTaskContext`, store it, and call the abstract `_forward_request` method.
        -   [x] 3.5.5. For `CancelTaskRequest`, it will find the corresponding `ProxyTaskContext` and set its `cancellation_event`.
    -   [x] 3.6. **Response Publishing:**
        -   [x] 3.6.1. Create concrete helper methods (`_publish_status_update`, `_publish_final_response`, `_publish_error_response`).
    -   [x] 3.7. **Abstract Methods:**
        -   [x] 3.7.1. Define the abstract methods `_fetch_agent_card` and `_forward_request`.
    -   [x] 3.8. **Cleanup (`cleanup`):**
        -   [x] 3.8.1. Implement cleanup logic to stop the async loop and cancel any active tasks.

-   [x] **4. Implement `BaseProxyApp`:**
    -   [x] 4.1. Create the file `src/agent/proxies/base/app.py`.
    -   [x] 4.2. Define the `BaseProxyApp` class, inheriting from `App`.
    -   [x] 4.3. Define the base `app_schema` with common configuration parameters.
    -   [x] 4.4. Implement the logic to generate Solace topic subscriptions for all proxied agents.
    -   [x] 4.5. Implement the abstract `_get_component_class` method.

## Phase 2: A2A-over-HTTPS Proxy Implementation (`src/agent/proxies/a2a/`)

-   [x] **5. Implement `A2AProxyComponent`:**
    -   [x] 5.1. Create the file `src/agent/proxies/a2a/component.py`.
    -   [x] 5.2. Define the `A2AProxyComponent` class, inheriting from `BaseProxyComponent`.
    -   [x] 5.3. **Implement `_fetch_agent_card`:**
        -   [x] 5.3.1. Use `a2a.client.A2ACardResolver` to fetch the `AgentCard` via HTTPS.
        -   [x] 5.3.2. Handle potential `A2AClientHTTPError` and other exceptions gracefully.
    -   [x] 5.4. **Implement `_forward_request`:**
        -   [x] 5.4.1. Implement the core logic of the component.
        -   [x] 5.4.2. Instantiate and manage a dictionary of `a2a.client.A2AClient` instances.
        -   [x] 5.4.3. **Inbound Artifact Handling:** Check for `artifact://` URIs and load content.
        -   [x] 5.4.4. Call the appropriate `A2AClient` method (`send_message` or `send_message_streaming`).
        -   [x] 5.4.5. Use `async for` to iterate over the responses from the client.
        -   [x] 5.4.6. **Outbound Artifact Handling:** Save artifacts and rewrite the `FilePart`.
        -   [x] 5.4.7. Call the base class's helper methods to send all events back to the Solace mesh.
    -   [x] 5.5. **Authentication:**
        -   [x] 5.5.1. Implement logic to create and use an `AuthInterceptor` with the `A2AClient`.

-   [x] **6. Implement `A2AProxyApp`:**
    -   [x] 6.1. Create the file `src/agent/proxies/a2a/app.py`.
    -   [x] 6.2. Define the `A2AProxyApp` class, inheriting from `BaseProxyApp`.
    -   [x] 6.3. Extend the `app_schema` to include validation for A2A-specific parameters (`url`, `authentication`).
    -   [x] 6.4. Override `_get_component_class` to return `A2AProxyComponent`.

## Phase 3: Configuration and Documentation

-   [x] **7. Create Example Configuration:**
    -   [x] 7.1. Create a new file `examples/a2a_proxy.yaml`.
    -   [x] 7.2. Add a complete, well-commented configuration example.

-   [ ] **8. Update Documentation:**
    -   [ ] 8.1. Update the main `llm.txt` files in `src` and `agent`.
    -   [ ] 8.2. Create a new `proxies_llm.txt` file inside `src/agent/proxies/`.

## Phase 4: Testing

-   [ ] **9. Unit Tests:**
    -   [ ] 9.1. Add unit tests for the `BaseProxyComponent`'s concrete methods.
    -   [ ] 9.2. Add unit tests for the `A2AProxyComponent`'s specific logic, mocking `A2AClient` and `ArtifactService`.

-   [ ] **10. Integration Tests:**
    -   [ ] 10.1. Create an integration test that runs the `A2AProxyApp` with mock downstream agents.
    -   [ ] 10.2. Verify the end-to-end flow: discovery, task submission, streaming, artifacts, and final response.
