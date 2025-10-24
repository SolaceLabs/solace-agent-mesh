# Implementation Checklist: Generic Gateway Adapter Framework

This checklist tracks the implementation of the Generic Gateway Adapter Framework.

### **Phase 1: Core Framework and Type Definition**

- [x] 1. **Create Directory Structure**:
    - [x] `src/solace_agent_mesh/gateway/adapter/`
    - [x] `src/solace_agent_mesh/gateway/generic/`

- [x] 2. **Define SAM Types** (`src/solace_agent_mesh/gateway/adapter/types.py`):
    - [x] `SamTextPart`, `SamFilePart`, `SamDataPart`, `SamContentPart`
    - [x] `SamTask`
    - [x] `AuthClaims`
    - [x] `SamUpdate`
    - [x] `SamError`
    - [x] `ResponseContext`
    - [x] `GatewayContext` (class definition)

- [x] 3. **Define GatewayAdapter Interface** (`src/solace_agent_mesh/gateway/adapter/base.py`):
    - [x] Create `GatewayAdapter` ABC with `Generic` type hints.
    - [x] Define abstract methods: `prepare_task`, `handle_text_chunk`.
    - [x] Define concrete methods with default implementations.

---

### **Phase 2: Generic Gateway Component Implementation**

- [x] 4. **Implement GenericGatewayApp** (`src/solace_agent_mesh/gateway/generic/app.py`):
    - [x] Extend `BaseGatewayApp`.
    - [x] Add `gateway_adapter` and `adapter_config` to schema.
    - [x] Implement `_get_gateway_component_class`.

- [x] 5. **Implement GenericGatewayComponent** (`src/solace_agent_mesh/gateway/generic/component.py`):
    - [x] Extend `BaseGatewayComponent` and implement `GatewayContext`.
    - [x] Dynamically load adapter in `__init__` and validate config against adapter's `ConfigModel`.
    - [x] Implement `_start_listener` and `_stop_listener` to call adapter.
    - [x] Implement `_send_*_to_external` methods to translate A2A events to SAM types and call adapter handlers.
    - [x] Implement `handle_external_input` to orchestrate the inbound flow.
    - [x] Implement state management methods using `self.cache_service`.

---

### **Phase 3: Refactor an Existing Gateway (Slack)**

- [x] 6. **Create SlackAdapter** (`src/solace_agent_mesh/gateway/slack/adapter.py`):
    - [x] Create new `adapter.py` file.
    - [x] Define `SlackAdapterConfig` Pydantic model.
    - [x] Implement `SlackAdapter` with `ConfigModel` and migrate logic.

- [x] 7. **Create Slack Handlers and App**:
    - [x] Create `src/solace_agent_mesh/gateway/slack/handlers.py` to call `handle_external_input`.
    - [x] Delete `src/solace_agent_mesh/gateway/slack/app.py` as it is no longer needed.

- [ ] 8. **Update Slack Example Configuration**:
    - [ ] Modify `slack_gateway_example.yaml` to use `GenericGatewayApp` and the new `gateway_adapter` and `adapter_config` structure.

---

### **Phase 4: Testing and Validation**

- [ ] 9. **Unit Test the Framework**:
    - [ ] Create unit tests for SAM types.
    - [ ] Create unit tests for `GenericGatewayComponent` with a mock adapter.

- [ ] 10. **Update Slack Tests**:
    - [ ] Refactor `test_slack_gateway.py` to test the new `SlackAdapter` and mock `GatewayContext`.

---

### **Phase 5: Documentation**

- [ ] 11. **Create Developer Guide**:
    - [ ] Create `docs/development/creating-gateways.md`.
    - [ ] Add tutorial, examples, and API documentation.

- [ ] 12. **Update Existing Code and Documentation**:
    - [ ] Add docstrings to all new public classes and methods.
    - [ ] Update existing docs to reference the new adapter pattern.
