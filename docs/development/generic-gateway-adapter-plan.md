# Implementation Plan: Generic Gateway Adapter Framework

This document outlines the steps to implement the Generic Gateway Adapter Framework as detailed in `prd-generic-gateway-adapter.md`.

---

### **Phase 1: Core Framework and Type Definition**
*Goal: Establish the foundational data structures and interfaces for the adapter pattern.*

1.  **Create Directory Structure:**
    *   Create the directory `src/solace_agent_mesh/gateway/adapter/` for the abstract framework definitions.
    *   Create the directory `src/solace_agent_mesh/gateway/generic/` for the concrete component implementation.
    *   Add `__init__.py` files to both new directories to mark them as Python packages.

2.  **Define SAM Types (`src/solace_agent_mesh/gateway/adapter/types.py`):**
    *   In a new file, `types.py`, define the following Pydantic models to create a stable abstraction layer over the A2A protocol:
        *   `SamTextPart`, `SamFilePart`, `SamDataPart`, and a `SamContentPart` `Union` type.
        *   `SamTask`: Represents an inbound request from a platform.
        *   `AuthClaims`: Represents identity information extracted from a platform event.
        *   `SamUpdate`: Represents a streaming update from an agent.
        *   `SamError`: A structured error model with `message`, `code`, and `category: Literal["FAILED", "CANCELED", "TIMED_OUT", "PROTOCOL_ERROR"]`.
        *   `ResponseContext`: Contains routing information for outbound messages (`task_id`, `conversation_id`, `user_id`, `platform_context`).
        *   `GatewayContext`: Define this as a class to establish its API, including methods like `handle_external_input`, `cancel_task`, and state management helpers. The concrete implementation will be in the `GenericGatewayComponent`.

3.  **Define GatewayAdapter Interface (`src/solace_agent_mesh/gateway/adapter/base.py`):**
    *   In a new file, `base.py`, define `GatewayAdapter` as an Abstract Base Class (`ABC`).
    *   Use `typing.Generic` to allow for optional, adapter-specific type hinting: `GatewayAdapter[T_ExternalInput, T_PlatformContext]`, defaulting to `Any`.
    *   Define the following methods as specified in the PRD, with `handle_error` updated to use the new `SamError` type:
        *   **Abstract Methods:** `prepare_task`, `handle_text_chunk`.
        *   **Concrete Methods (with default `pass` or dispatch logic):** `init`, `cleanup`, `extract_auth_claims`, `handle_update`, `handle_file`, `handle_data_part`, `handle_status_update`, `handle_task_complete`, `handle_error`.

---

### **Phase 2: Generic Gateway Component Implementation**
*Goal: Create the engine that hosts and orchestrates the adapters.*

4.  **Implement GenericGatewayApp (`src/solace_agent_mesh/gateway/generic/app.py`):**
    *   In a new file, `app.py`, define `GenericGatewayApp` that extends `BaseGatewayApp`.
    *   Add schema definitions for `gateway_adapter` (the Python module path) and `adapter_config` (a dictionary for adapter-specific settings) to its `SPECIFIC_APP_SCHEMA_PARAMS`. This allows any adapter to be loaded without a custom App class.
    *   Implement the `_get_gateway_component_class` method to return `GenericGatewayComponent`.

5.  **Implement GenericGatewayComponent (`src/solace_agent_mesh/gateway/generic/component.py`):**
    *   In a new file, `component.py`, define `GenericGatewayComponent` that extends `BaseGatewayComponent` and also serves as the concrete implementation of the `GatewayContext`.
    *   **In `__init__`**:
        *   Dynamically import and instantiate the adapter class specified in the `gateway_adapter` configuration.
        *   Check if the adapter has a `ConfigModel` (Pydantic model) defined.
        *   If so, validate the `adapter_config` dictionary against the model and store the resulting Pydantic object. Otherwise, store the raw dictionary.
    *   **Implement `BaseGatewayComponent` abstract methods**:
        *   `_start_listener`: Will call `self.adapter.init(self)`.
        *   `_stop_listener`: Will call `self.adapter.cleanup()`.
        *   `_send_update_to_external`, `_send_final_response_to_external`, `_send_error_to_external`: These methods will form the core translation layer. They will parse incoming A2A events, translate them to `SamUpdate` or `SamError` objects, retrieve the `platform_context` from the `TaskContextManager`, and call the appropriate adapter handlers (`handle_update`, `handle_error`).
    *   **Implement `GatewayContext` public API**:
        *   `handle_external_input`: This will be the main entry point for adapters. It will orchestrate the sequence of authenticating the user (via the adapter's `extract_auth_claims`), preparing the task (via `prepare_task`), and submitting it to the A2A mesh.
        *   State management methods (`get_task_state`, `set_task_state`, etc.) will be implemented to use `self.cache_service` for storage, as discussed.

---

### **Phase 3: Refactor an Existing Gateway (Slack)**
*Goal: Prove the framework's design and power by migrating the `sam-slack` plugin to the new adapter pattern.*

6.  **Create SlackAdapter (`src/solace_agent_mesh/gateway/slack/adapter.py`):**
    *   Create a new file, `adapter.py`, within the `src/solace_agent_mesh/gateway/slack/` directory.
    *   Define a `SlackAdapterConfig` Pydantic model within the file to hold all Slack-specific settings.
    *   Define a `SlackAdapter` class that implements the `GatewayAdapter` interface and sets `ConfigModel = SlackAdapterConfig`.
    *   Migrate the core platform-specific logic from the original `SlackGatewayComponent` into the corresponding methods of `SlackAdapter`.

7.  **Create Slack Handlers (`src/solace_agent_mesh/gateway/slack/handlers.py`):**
    *   Create a new `handlers.py` file.
    *   Implement `handle_slack_message` and `handle_slack_mention` which delegate to a `_process_slack_event` helper.
    *   The `_process_slack_event` function will simply call `adapter.context.handle_external_input(event)`, delegating all orchestration to the `GenericGatewayComponent`.

8.  **Update Slack Example Configuration:**
    *   Modify `examples/gateways/slack_gateway_example.yaml`:
        *   Change the `app_module` to point to `solace_agent_mesh.gateway.generic.app.GenericGatewayApp`.
        *   Add the `gateway_adapter` key, pointing to `sam_slack.adapter.SlackAdapter`.
        *   Move Slack-specific settings (like tokens) into a new `adapter_config` block.

---

### **Phase 4: Testing and Validation**
*Goal: Ensure the new framework is robust and the refactoring was successful.*

9.  **Unit Test the Framework:**
    *   Create unit tests for the new SAM types defined in `types.py`.
    *   Create unit tests for the `GenericGatewayComponent`, using a mock adapter to verify that it correctly calls adapter methods and performs the A2A-to-SAM translation logic.

10. **Update Slack Tests:**
    *   Refactor `../solace-agent-mesh-core-plugins-1/sam-slack/tests/unit/test_slack_gateway.py` to test the new `SlackAdapter` class directly. These tests will now mock the `GatewayContext` interface instead of the `BaseGatewayComponent` methods.

---

### **Phase 5: Documentation**
*Goal: Document the new framework to enable other developers to build gateways easily.*

11. **Create Developer Guide:**
    *   Create a new markdown file, `docs/development/creating-gateways.md`, that explains the new adapter pattern.
    *   Include a tutorial for building a simple gateway (like the CLI example from the PRD).
    *   Provide a high-level overview of the `SlackAdapter` as an advanced example.
    *   Document the public API for `GatewayAdapter`, `GatewayContext`, and all the new SAM types.

12. **Update Existing Code and Documentation:**
    *   Add comprehensive docstrings to all new public classes and methods created in the framework.
    *   Update existing documentation to reference the new adapter pattern as the preferred method for creating gateways.
