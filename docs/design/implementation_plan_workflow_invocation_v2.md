# Implementation Plan: Workflow Invocation via A2A (v2)

## 1. Overview
This plan details the steps to implement typed workflow invocation in Solace Agent Mesh. The goal is to allow agents to call workflows as structured functions rather than generic chat agents, using a dual-mode tool (parameters or artifact) and implicit artifact creation.

This v2 plan incorporates the existing workflow implementation details found in `src/solace_agent_mesh/workflow/`.

## 2. Implementation Steps

### Phase 1: Core Types & Constants

1.  **Update `src/solace_agent_mesh/common/a2a/types.py`**
    *   Define `SchemasExtensionParams` Pydantic model to represent the `schemas` extension in Agent Cards.
    *   This model will hold `input_schema` and `output_schema`.

2.  **Update `src/solace_agent_mesh/common/constants.py`**
    *   Define constants for the extension URIs:
        *   `EXTENSION_URI_SCHEMAS = "https://solace.com/a2a/extensions/sam/schemas"`
        *   `EXTENSION_URI_AGENT_TYPE = "https://solace.com/a2a/extensions/agent-type"`

### Phase 2: Tool Implementation (`WorkflowAgentTool`)

3.  **Create `src/solace_agent_mesh/agent/tools/workflow_tool.py`**
    *   Implement `WorkflowAgentTool` class inheriting from `BaseTool`.
    *   **Constructor:** Accept `target_agent_name`, `input_schema`, `host_component`.
    *   **`_get_declaration`:**
        *   Dynamically build `FunctionDeclaration`.
        *   Start with `input_schema`.
        *   Add `input_artifact` (string, optional) to properties.
        *   Mark ALL properties as optional in the schema sent to LLM (to allow dual mode).
    *   **`run_async`:**
        *   Implement the dual-mode logic.
        *   **Artifact Mode:** If `input_artifact` is present, resolve it to a URI/reference.
        *   **Parameter Mode:**
            *   Validate `kwargs` against the *strict* `input_schema` (required fields must be present).
            *   Serialize `kwargs` to JSON.
            *   Call `host_component.artifact_service.save_artifact` to create the input artifact.
            *   Use naming convention: `workflow_input_{sanitized_workflow_name}_{uuid}.json`.
        *   **Transport:**
            *   Construct `A2AMessage` with `sessionBehavior="RUN_BASED"`.
            *   Add artifact reference to `metadata.invoked_with_artifacts`.
            *   Call `host_component.submit_a2a_task`.

### Phase 3: Agent Discovery & Tool Factory

4.  **Update `src/solace_agent_mesh/agent/sac/component.py`**
    *   Modify `_inject_peer_tools_callback`.
    *   Iterate through `self.peer_agents`.
    *   Check for `agent_type` extension in the Agent Card.
    *   **If Workflow:**
        *   Extract `input_schema` from the Agent Card (using `EXTENSION_URI_SCHEMAS`).
        *   If no schema, use default `{text: string}` schema.
        *   Instantiate `WorkflowAgentTool`.
        *   Add to `llm_request`.
    *   **If Standard Agent:**
        *   Keep existing logic (instantiate `PeerAgentTool`).
        *   (Future enhancement: Standard agents could also use `WorkflowAgentTool` if they publish a schema, but for now we stick to `agent_type` check).

### Phase 4: Prompt Engineering

5.  **Update `src/solace_agent_mesh/agent/adk/callbacks.py`**
    *   Modify `inject_dynamic_instructions_callback`.
    *   Check if any `WorkflowAgentTool` instances were added to the request.
    *   If yes, inject the specific "Workflow Execution" system prompt section explaining the dual-mode input (Parameters vs. Artifact).

### Phase 5: Workflow Agent Configuration (Server-Side)

6.  **Update `src/solace_agent_mesh/agent/sac/app.py`**
    *   Update `SamAgentAppConfig` to support `agent_type` configuration.
    *   (Note: `input_schema` and `output_schema` are already present in `SamAgentAppConfig`).

7.  **Update `src/solace_agent_mesh/agent/protocol/event_handlers.py`**
    *   Update `publish_agent_card` to include the `agent_type` extension if configured.
    *   Update `publish_agent_card` to include the `schemas` extension (using `EXTENSION_URI_SCHEMAS`) if `input_schema` or `output_schema` are configured.

8.  **Update `src/solace_agent_mesh/workflow/component.py`**
    *   Update `_create_workflow_agent_card` to include the `agent_type` extension (set to "workflow").
    *   Update `_create_workflow_agent_card` to use the shared `EXTENSION_URI_SCHEMAS` constant for publishing schemas.

### Phase 6: Workflow Input Handling (Server-Side)

9.  **Update `src/solace_agent_mesh/workflow/protocol/event_handlers.py`**
    *   Modify `handle_task_request` (or `_initialize_workflow_state`).
    *   Extract the input payload from the A2A message.
        *   If `invoked_with_artifacts` metadata is present, load the artifact content.
        *   If `DataPart` is present, use it.
        *   If `TextPart` is present, wrap in `{"text": ...}`.
    *   Store this input in `workflow_state.node_outputs["workflow_input"]` (or similar) so the first node can reference it.
    *   (Note: `DAGExecutor._resolve_template` already has a placeholder for `workflow.input`).

## 3. Verification Plan

*   **Unit Tests:**
    *   Test `WorkflowAgentTool` schema generation and dual-mode logic.
    *   Test `SamAgentComponent` tool factory logic (mocking registry).
*   **Integration Test:**
    *   Deploy a Workflow Agent.
    *   Deploy an Orchestrator Agent.
    *   Verify Orchestrator sees `workflow_` tool.
    *   Verify Orchestrator can call workflow with parameters (implicit artifact).
    *   Verify Orchestrator can call workflow with artifact reference.
