# Implementation Checklist: Generic Gateway Adapter Framework

This checklist tracks the implementation of the Generic Gateway Adapter Framework.

### **Phase 1: Core Framework and Type Definition**

- [ ] 1. **Create Directory Structure**:
    - [ ] `src/solace_agent_mesh/gateway/adapter/`
    - [ ] `src/solace_agent_mesh/gateway/generic/`

- [ ] 2. **Define SAM Types** (`src/solace_agent_mesh/gateway/adapter/types.py`):
    - [ ] `SamTextPart`, `SamFilePart`, `SamDataPart`, `SamContentPart`
    - [ ] `SamTask`
    - [ ] `AuthClaims`
    - [ ] `SamUpdate`
    - [ ] `SamError`
    - [ ] `ResponseContext`
    - [ ] `GatewayContext` (class definition)

- [ ] 3. **Define GatewayAdapter Interface** (`src/solace_agent_mesh/gateway/adapter/base.py`):
    - [ ] Create `GatewayAdapter` ABC with `Generic` type hints.
    - [ ] Define abstract methods: `prepare_task`, `handle_text_chunk`.
    - [ ] Define concrete methods with default implementations.

---

### **Phase 2: Generic Gateway Component Implementation**

- [ ] 4. **Implement GenericGatewayApp** (`src/solace_agent_mesh/gateway/generic/app.py`):
    - [ ] Extend `BaseGatewayApp`.
    - [ ] Add `gateway_adapter` and `adapter_config` to schema.
    - [ ] Implement `_get_gateway_component_class`.

- [ ] 5. **Implement GenericGatewayComponent** (`src/solace_agent_mesh/gateway/generic/component.py`):
    - [ ] Extend `BaseGatewayComponent` and implement `GatewayContext`.
    - [ ] Dynamically load adapter in `__init__`.
    - [ ] Implement `_start_listener` and `_stop_listener` to call adapter.
    - [ ] Implement `_send_*_to_external` methods to translate A2A events to SAM types and call adapter handlers.
    - [ ] Implement `handle_external_input` to orchestrate the inbound flow.
    - [ ] Implement state management methods using `self.cache_service`.

---

### **Phase 3: Refactor an Existing Gateway (Slack)**

- [ ] 6. **Create SlackAdapter** (`../solace-agent-mesh-core-plugins-1/sam-slack/src/sam_slack/adapter.py`):
    - [ ] Create new `adapter.py` file.
    - [ ] Implement `SlackAdapter` by migrating logic from `SlackGatewayComponent`.

- [ ] 7. **Update SlackGatewayApp and Handlers**:
    - [ ] Modify `SlackGatewayApp` to inherit from `GenericGatewayApp`.
    - [ ] Simplify `_process_slack_event` in `handlers.py` to call `handle_external_input`.
    - [ ] Delete `../solace-agent-mesh-core-plugins-1/sam-slack/src/sam_slack/component.py`.

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
