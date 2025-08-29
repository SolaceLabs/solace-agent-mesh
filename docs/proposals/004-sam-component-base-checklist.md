# Implementation Checklist: `SamComponentBase` Refactoring

1.  [x] **Create `SamComponentBase` Class**
    -   [x] Create the file `src/solace_agent_mesh/common/sac/sam_component_base.py`.
    -   [x] Implement the `SamComponentBase` class with inheritance from `ComponentBase` and `abc.ABC`.
    -   [x] Implement `__init__` to handle shared configuration (`namespace`, `max_message_size_bytes`).
    -   [x] Implement the shared `publish_a2a_message` method with size validation.
    -   [x] Implement the async lifecycle methods: `run`, `cleanup`, `_run_async_operations`, `get_async_loop`.
    -   [x] Define the abstract methods: `_async_setup_and_run` and `_pre_async_cleanup`.

2.  [x] **Update Gateway Configuration**
    -   [x] In `src/solace_agent_mesh/gateway/base/app.py`, add `gateway_max_message_size_bytes` to `BASE_GATEWAY_APP_SCHEMA`.
    -   [x] In `src/solace_agent_mesh/gateway/base/app.py`, update `__init__` to read the new configuration value.

3.  [x] **Refactor `BaseGatewayComponent`**
    -   [x] In `src/solace_agent_mesh/gateway/base/component.py`, change inheritance to `SamComponentBase`.
    -   [x] Remove the duplicated methods: `run`, `cleanup`, `_run_async_operations`, `publish_a2a_message`.
    -   [x] Implement the abstract method `_async_setup_and_run`.
    -   [x] Implement the abstract method `_pre_async_cleanup`.

4.  [x] **Refactor `SamAgentComponent`**
    -   [x] In `src/solace_agent_mesh/agent/sac/component.py`, change inheritance to `SamComponentBase`.
    -   [x] Remove the duplicated methods: `_start_async_loop`, `_publish_a2a_message`, and async logic from `cleanup`.
    -   [x] Replace all internal calls from `_publish_a2a_message` to `publish_a2a_message`.
    -   [x] Implement the abstract method `_async_setup_and_run`.
    -   [x] Implement the abstract method `_pre_async_cleanup`.

5.  [x] **Add `update_artifact_parts` Utility**
    -   [x] In `src/solace_agent_mesh/common/a2a/artifact.py`, add the `update_artifact_parts` function.
    -   [x] In `src/solace_agent_mesh/common/a2a/__init__.py`, export the new function in `__all__`.

6.  [x] **Update Design Document**
    -   [x] In `docs/proposals/002-sam-component-base-design.md`, update the signature of `publish_a2a_message` to reflect its public status.
