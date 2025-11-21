# Product Requirements Document: Workflow Invocation via A2A

## 1. Overview
This feature enables Solace Agent Mesh (SAM) agents to invoke business workflows as distinct, typed entities rather than generic chat agents. By formalizing the contract between a calling agent and a workflow, we improve reliability, type safety, and the ability for LLMs to correctly utilize complex business processes.

## 2. Goals
*   **Type Safety:** Ensure workflows receive structured data (JSON) that matches their expected input schema, rather than unstructured chat text.
*   **Reliability:** Reduce LLM hallucinations by providing clear, function-like interfaces for workflows.
*   **Efficiency:** Optimize data transport by using artifacts for structured payloads, keeping the context window clean.
*   **Ease of Use:** Automatically generate appropriate tools for discovered workflows without manual configuration in the calling agent.

## 3. Requirements

### 3.1. Discovery & Advertisement
*   **Workflow Identification:** Agents acting as workflows must be identifiable via a specific Agent Card extension (e.g., `agent_type` or `component_type`) set to `workflow`.
*   **Schema Advertisement:** The Agent Card must utilize the standard/existing mechanism for advertising `input_schema` and `output_schema`. We will not create a new, workflow-specific configuration block for schemas.
*   **Schema Inference (Default):**
    *   The system should attempt to infer the `input_schema` from the **first node** (A2A Trigger) of the workflow, **only if** the schema is explicitly defined within the workflow definition for that node.
    *   The system should attempt to infer the `output_schema` from the **last node** of the workflow, **only if** the schema is explicitly defined within the workflow definition for that node.
    *   **Constraint:** The system will **not** attempt to resolve or infer schemas by looking up the Agent Cards of the agents used in the start/end nodes. Inference is strictly local to the workflow definition.
*   **Schema Configuration (Override):** Users must be able to explicitly configure `input_schema` and `output_schema` in the agent's YAML configuration to override inference.
*   **Default Fallback:** If no schema is defined or inferred, the system must default to a simple schema: `{"properties": {"text": {"type": "string"}}, "required": ["text"]}`.

### 3.2. Tool Generation (`WorkflowAgentTool`)
*   **Distinct Tooling:** When a workflow agent is discovered, the system must generate a specialized tool named `workflow_<agent_name>` (instead of `peer_<agent_name>`).
*   **Dual-Mode Signature:** The generated tool must support two mutually exclusive input methods:
    1.  **Parameter Mode:** Explicit arguments matching the fields in the `input_schema`.
    2.  **Artifact Mode:** A single `input_artifact` argument (string) accepting a filename.
*   **Optionality Handling:** To support Dual-Mode, all schema parameters must be marked as "Optional" in the tool definition sent to the LLM, with logic to enforce their presence if `input_artifact` is not used.
*   **Description Generation:** The tool description must be auto-generated to explain the dual-mode capability and the workflow's purpose.

### 3.3. Invocation Logic
*   **Implicit Artifact Creation:** If the LLM calls the tool using **Parameter Mode**, the tool implementation must:
    1.  Validate the inputs against the strict schema.
    2.  Serialize the inputs into a JSON object.
    3.  Save this object as an artifact with a standardized name (e.g., `workflow_input_{sanitized_workflow_name}_{uuid}.json`) and a descriptive metadata description (e.g., "Auto-generated input payload for workflow '{workflow_name}' invocation.").
    4.  Send the A2A message referencing this artifact.
*   **Artifact Pass-through:** If the LLM calls the tool using **Artifact Mode**, the tool implementation must pass the reference through to the workflow.
*   **Transport:** The invocation must use the standard A2A protocol.
    *   The payload should be wrapped in a `DataPart` (if supported) or referenced via metadata.
    *   Metadata must include `sessionBehavior: "RUN_BASED"` to indicate a stateless execution.

### 3.4. Execution Model
*   **Blocking Call:** The calling agent must wait for the workflow to complete (similar to `PeerAgentTool`).
*   **Output Handling:** The workflow's final response (text and/or artifacts) must be returned to the calling agent's context.

## 4. Key Decisions

### 4.1. "Always-Typed" Workflows
We will treat all workflows as functions. Even simple "chat" workflows will be wrapped in a default `{text: ...}` schema. This eliminates ambiguity for the calling LLM—it is always calling a function, never just "chatting."
*   **Identification:** The calling agent distinguishes a workflow from a standard agent solely by the presence of the `agent_type: workflow` extension.
*   **Contract:** The calling agent determines *how* to call the workflow by reading the standard `input_schema`.

### 4.2. Implicit Artifact Pattern
We chose to hide the complexity of artifact creation from the LLM when it provides raw parameters. The tool handles the serialization and saving of the input JSON. This ensures the workflow always receives a file/artifact, which is the most robust way to handle structured data in A2A.
*   **Naming Convention:** To ensure observability, these auto-created artifacts will follow a strict naming convention: `workflow_input_{sanitized_workflow_name}_{uuid}.json`.
*   **Description:** They will be tagged with a clear description explaining their origin and purpose.

### 4.3. Dual-Mode Tooling
We support both direct parameters and artifact references in the same tool to handle different LLM contexts:
*   **Parameters:** Best for new data or simple inputs.
*   **Artifacts:** Best for passing large datasets or outputs from previous steps without re-tokenizing.

### 4.4. Single Start Node (MVP)
For the initial release, we will assume a workflow has a single A2A Trigger node. Support for multiple start nodes (polymorphic inputs) is deferred.

## 5. Out of Scope
*   **Multiple Start Nodes:** Handling workflows with multiple A2A entry points (requiring `oneOf` schema logic).
*   **Workflow-to-Workflow Validation:** The calling agent does not validate the workflow's output against the `output_schema`. Validation is the responsibility of the workflow itself or the consuming logic.
*   **Streaming Intermediate Results:** The caller waits for the final result; intermediate streaming from the workflow is not required for the MVP.
