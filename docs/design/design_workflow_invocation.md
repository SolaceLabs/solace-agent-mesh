# Design Document: Workflow Invocation via A2A

## 1. Introduction
This document outlines the technical design for enabling Solace Agent Mesh (SAM) agents to invoke business workflows as typed, function-like entities. This feature shifts the interaction model for workflows from "chat-based" to "transaction-based," ensuring type safety and reliability.

## 2. Architecture Overview

The solution leverages the existing A2A (Agent-to-Agent) protocol but introduces a specialized client-side handling layer within the `SamAgentComponent`.

### Key Components
1.  **Agent Registry & Discovery**: Enhanced to recognize "Workflow" agents via Agent Card extensions.
2.  **Tool Factory**: Logic within `SamAgentComponent` to dynamically generate the appropriate tool class (`PeerAgentTool` vs. `WorkflowAgentTool`) based on the discovered agent type.
3.  **`WorkflowAgentTool`**: A new tool implementation that handles the dual-mode input (parameters vs. artifact) and manages the implicit creation of input artifacts.
4.  **Prompt Manager**: Conditional logic to inject system instructions specific to workflow execution only when workflow tools are present.

## 3. Component Design

### 3.1. Workflow Identification (Discovery Phase)
*   **Mechanism**: We utilize the standard `AgentCard` structure.
*   **Differentiation**: A workflow agent is identified by the presence of a specific extension in its Agent Card (`https://solace.com/a2a/extensions/agent-type` with param `type="workflow"`).
*   **Schema Source**: The input contract is read from the `https://solace.com/a2a/extensions/sam/schemas` extension in the Agent Card. This URI is shared between standard agents and workflows.
*   **Fallback**: If a workflow agent does not publish an `input_schema`, the system defaults to a generic schema: `{"text": "string"}`.

### 3.2. Tool Factory Logic
The `SamAgentComponent`'s peer tool injection logic (`_inject_peer_tools_callback`) will be updated to branch based on the agent type:

*   **Standard Agent**: Instantiates `PeerAgentTool`.
*   **Workflow Agent**: Instantiates `WorkflowAgentTool`.

This decision happens at runtime during the `before_model_callback` phase, ensuring the toolset is always up-to-date with the registry. The logic will inspect the `agent_type` extension to make this determination.

### 3.3. `WorkflowAgentTool` Design
This class is responsible for presenting the workflow to the LLM and handling the invocation mechanics.

#### 3.3.1. Dynamic Signature Generation
The tool's `FunctionDeclaration` (schema sent to the LLM) is constructed dynamically:
1.  **Base**: Start with the peer's `input_schema`.
2.  **Augmentation**: Add a special argument `input_artifact` (type: string, description: "Filename of an existing JSON artifact...").
3.  **Relaxation**: Mark **all** parameters (both original and new) as *Optional* in the LLM-facing schema. This allows the LLM to choose between providing explicit parameters OR the artifact, without validation errors from the LLM provider.

#### 3.3.2. Runtime Execution Logic (`run_async`)
The `run_async` method implements the "Dual-Mode" logic:
1.  **Check for Artifact**: If `input_artifact` is provided:
    *   Verify the file exists in the artifact service.
    *   Use this filename as the payload reference.
    *   Ignore any other parameters provided.
2.  **Check for Parameters**: If `input_artifact` is NOT provided:
    *   **Validate**: strictly validate the provided `kwargs` against the *original* `input_schema` (which requires specific fields). Raise a clear error if required fields are missing.
    *   **Serialize**: Convert the `kwargs` dictionary to a JSON byte string.
    *   **Save**: Persist this JSON as a new artifact (e.g., `workflow_input_{uuid}.json`) using the `ArtifactService`.
    *   Use this new filename as the payload reference.
3.  **Transport**: Construct the A2A message.
    *   Set `sessionBehavior` metadata to `RUN_BASED`.
    *   Add the artifact reference to `invoked_with_artifacts` metadata.
    *   Send via `submit_a2a_task`.

### 3.4. Conditional Prompt Injection
To avoid confusing the LLM with instructions for tools it doesn't have, the system prompt injection must be context-aware.

*   **Trigger**: During the `_inject_peer_tools_callback`, we track if *any* `WorkflowAgentTool` was added to the request.
*   **Action**: If count > 0, we append a specific instruction block to the system prompt explaining the "Dual-Mode" nature of workflow tools (i.e., "You can provide parameters directly OR pass an input_artifact...").
*   **Safety**: If no workflows are available, this instruction block is omitted.

## 4. Data Flow

### Scenario: Parameter Mode
1.  **User**: "Onboard user John Doe."
2.  **LLM**: Calls `workflow_onboarding(name="John Doe")`.
3.  **`WorkflowAgentTool`**:
    *   Validates `name` is present.
    *   Creates JSON: `{"name": "John Doe"}`.
    *   Saves to Artifact Service -> `input.json`.
    *   Sends A2A Request to Workflow Agent with ref to `input.json`.
4.  **Workflow Agent**: Reads `input.json`, executes logic.

### Scenario: Artifact Mode
1.  **User**: "Process this CSV file using the onboarding workflow."
2.  **LLM**: Calls `workflow_onboarding(input_artifact="data.csv")`.
3.  **`WorkflowAgentTool`**:
    *   Sees `input_artifact`.
    *   Sends A2A Request to Workflow Agent with ref to `data.csv`.
4.  **Workflow Agent**: Reads `data.csv`, executes logic.

## 5. Security & Validation
*   **Schema Validation**: The `WorkflowAgentTool` performs strict validation of parameters against the defined schema before sending any message, preventing malformed data from reaching the workflow.
*   **Artifact Access**: Standard RBAC and artifact scoping rules apply. The workflow agent must have permission to read the artifact referenced.
