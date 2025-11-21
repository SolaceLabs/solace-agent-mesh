# Implementation Plan: Workflow Invocation via A2A

## 1. Overview
This plan details the steps to implement typed workflow invocation in Solace Agent Mesh. The goal is to allow agents to call workflows as structured functions rather than generic chat agents, using a dual-mode tool (parameters or artifact) and implicit artifact creation.

## 2. Implementation Steps

### Phase 1: Core Types & Constants

1.  **Update `src/solace_agent_mesh/common/a2a/types.py`**
    *   Define `WorkflowConfigExtension` Pydantic model to represent the `workflow_config` extension in Agent Cards.
    *   This model will hold `input_schema` and `output_schema`.

2.  **Update `src/solace_agent_mesh/common/constants.py`** (or create if missing, otherwise add to `src/solace_agent_mesh/common/a2a/protocol.py`)
    *   Define constants for the workflow extension URI (e.g., `https://solace.com/a2a/extensions/workflow-config`).
    *   Define constants for the agent type extension URI (e.g., `https://solace.com/a2a/extensions/agent-type`).

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
        *   Extract `input_schema` from the Agent Card (standard location).
        *   If no schema, use default `{text: string}` schema.
        *   Instantiate `WorkflowAgentTool`.
        *   Add to `llm_request`.
    *   **If Standard Agent:**
        *   Keep existing logic (instantiate `PeerAgentTool`).

### Phase 4: Prompt Engineering

5.  **Update `src/solace_agent_mesh/agent/adk/callbacks.py`**
    *   Modify `inject_dynamic_instructions_callback`.
    *   Check if any `WorkflowAgentTool` instances were added to the request.
    *   If yes, inject the specific "Workflow Execution" system prompt section explaining the dual-mode input (Parameters vs. Artifact).

### Phase 5: Workflow Agent Configuration (Server-Side)

6.  **Update `src/solace_agent_mesh/agent/sac/app.py`**
    *   Update `SamAgentAppConfig` or `AgentCardConfig` to support `agent_type` and `input_schema`/`output_schema` configuration.
    *   Ensure these fields are correctly propagated to the published Agent Card.

7.  **Update `src/solace_agent_mesh/agent/protocol/event_handlers.py`**
    *   Update `publish_agent_card` to include the `agent_type` extension if configured.
    *   Update `publish_agent_card` to include the `input_schema` and `output_schema` in the standard Agent Card fields if configured.

### Phase 6: Testing

8.  **Create `tests/agent/tools/test_workflow_tool.py`**
    *   Test `_get_declaration` schema generation (optionality).
    *   Test `run_async` in Parameter Mode (validation, artifact creation, message sending).
    *   Test `run_async` in Artifact Mode (pass-through).
    *   Test validation failures (missing required params in Parameter Mode).

9.  **Create `tests/agent/sac/test_workflow_discovery.py`**
    *   Mock `AgentRegistry` with a workflow agent card.
    *   Verify `SamAgentComponent` generates the correct tool type.

## 3. Verification Plan

*   **Unit Tests:** Run the new test files.
*   **Integration Test:**
    *   Deploy a "Workflow Agent" (configured with `agent_type: workflow` and a schema).
    *   Deploy an "Orchestrator Agent".
    *   Ask Orchestrator to "Run the workflow with [parameters]".
    *   Verify Orchestrator creates an artifact and sends a RUN_BASED A2A message.
    *   Ask Orchestrator to "Run the workflow with this file [file]".
    *   Verify Orchestrator passes the file reference.
