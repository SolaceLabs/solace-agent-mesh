# Implementation Checklist: Workflow Invocation via A2A (v2)

- [x] **1. Core Types & Constants**
    - [x] Update `src/solace_agent_mesh/common/a2a/types.py`: Add `SchemasExtensionParams` model.
    - [x] Update `src/solace_agent_mesh/common/constants.py`: Add extension URIs (`schemas`, `agent-type`).

- [x] **2. Tool Implementation**
    - [x] Create `src/solace_agent_mesh/agent/tools/workflow_tool.py`:
        - [x] Implement `WorkflowAgentTool` class.
        - [x] Implement `_get_declaration` (Dual-mode schema generation).
        - [x] Implement `run_async` (Artifact creation vs. pass-through logic).

- [ ] **3. Agent Discovery & Tool Factory**
    - [ ] Update `src/solace_agent_mesh/agent/sac/component.py`:
        - [ ] Modify `_inject_peer_tools_callback` to detect `agent_type: workflow`.
        - [ ] Instantiate `WorkflowAgentTool` instead of `PeerAgentTool` for workflows.
        - [ ] Handle default schema fallback.

- [ ] **4. Prompt Engineering**
    - [ ] Update `src/solace_agent_mesh/agent/adk/callbacks.py`:
        - [ ] Modify `inject_dynamic_instructions_callback`.
        - [ ] Inject "Workflow Execution" instructions if workflow tools are present.

- [ ] **5. Workflow Agent Configuration**
    - [ ] Update `src/solace_agent_mesh/agent/sac/app.py`:
        - [ ] Add `agent_type` to `SamAgentAppConfig`.
    - [ ] Update `src/solace_agent_mesh/agent/protocol/event_handlers.py`:
        - [ ] Update `publish_agent_card` to include `agent_type` extension.
        - [ ] Update `publish_agent_card` to include `schemas` extension.
    - [ ] Update `src/solace_agent_mesh/workflow/component.py`:
        - [ ] Update `_create_workflow_agent_card` to use shared `EXTENSION_URI_SCHEMAS`.
        - [ ] Update `_create_workflow_agent_card` to add `agent_type` extension.

- [ ] **6. Workflow Input Handling**
    - [ ] Update `src/solace_agent_mesh/workflow/protocol/event_handlers.py`:
        - [ ] Modify `handle_task_request` to extract input payload (artifact/data/text).
        - [ ] Store input in `workflow_state.node_outputs["workflow_input"]`.

- [ ] **7. Testing**
    - [ ] Create `tests/agent/tools/test_workflow_tool.py`.
    - [ ] Create `tests/agent/sac/test_workflow_discovery.py`.
