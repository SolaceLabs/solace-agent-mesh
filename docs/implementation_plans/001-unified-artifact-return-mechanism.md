# Implementation Plan: Unified Artifact Return Mechanism

This document provides a step-by-step plan for implementing the "Unified Artifact Return Mechanism" feature.

## Phase 1: Foundational Changes in Embed Utilities

### Step 1: Define `ResolutionMode` Enum

-   **File:** `src/solace_agent_mesh/common/utils/embeds/types.py`
-   **Action:** Introduce a new `Enum` called `ResolutionMode` to make the embed resolution process context-aware.
-   **Details:** The enum will contain at least the following members:
    -   `A2A_MESSAGE_TO_USER`: For resolving embeds in the final message sent from a gateway to a user.
    -   `TOOL_PARAMETER`: For resolving embeds within tool arguments before execution.
    -   `RECURSIVE_ARTIFACT_CONTENT`: For resolving embeds found within the content of another artifact.

### Step 2: Update Embed Constants

-   **File:** `src/solace_agent_mesh/common/utils/embeds/constants.py`
-   **Action:** Register the new `artifact_return` embed type.
-   **Details:** Add `"artifact_return"` to the `LATE_EMBED_TYPES` set. This ensures it is processed by the gateway, not the agent.

## Phase 2: Core Resolver Logic Refactoring

### Step 3: Update Resolver Function Signatures

-   **File:** `src/solace_agent_mesh/common/utils/embeds/resolver.py`
-   **Action:** Update the signatures of the core resolver functions to accept the new `resolution_mode` parameter.
-   **Details:**
    -   Modify `evaluate_embed` to accept `resolution_mode: ResolutionMode`.
    -   Modify `resolve_embeds_in_string` to accept `resolution_mode: ResolutionMode`.
    -   Modify `resolve_embeds_recursively_in_string` to accept `resolution_mode: ResolutionMode`.

### Step 4: Implement Context-Aware Logic in `evaluate_embed`

-   **File:** `src/solace_agent_mesh/common/utils/embeds/resolver.py`
-   **Action:** Add conditional logic to `evaluate_embed` to handle the new embed types and signals based on the `resolution_mode`.
-   **Details:**
    1.  Add a new `elif` block for `embed_type == "artifact_return"`.
        -   If `resolution_mode` is `A2A_MESSAGE_TO_USER`, parse the expression and return a new signal tuple: `(None, "SIGNAL_ARTIFACT_RETURN", {"filename": ..., "version": ...})`.
        -   Otherwise, log a warning and return the original embed text, effectively ignoring it.
    2.  Modify the existing `artifact_content` logic.
        -   When the result of the modifier chain is binary data, return a new signal tuple: `(None, "SIGNAL_INLINE_BINARY_CONTENT", {"bytes": ..., "mime_type": ..., "filename": ...})`.

### Step 5: Create the `Part` List Resolver

-   **File:** `src/solace_agent_mesh/common/utils/embeds/resolver.py`
-   **Action:** Create a new primary function, `resolve_embeds_in_parts_list`, designed to be called by the gateway.
-   **Details:**
    1.  The function will accept `parts: List[ContentPart]` and the `resolution_mode`.
    2.  It will iterate through the input `parts`. Non-`TextPart` objects will be passed through to a new output list.
    3.  For each `TextPart`, it will call the existing `resolve_embeds_in_string` helper function.
    4.  It will use the signals returned from the helper to construct the final list of parts. This involves:
        -   Splitting the resolved text by placeholders for each signal.
        -   Creating new `TextPart` objects for the text segments.
        -   Creating `FilePart` objects based on the `SIGNAL_ARTIFACT_RETURN` and `SIGNAL_INLINE_BINARY_CONTENT` signals.
        -   Assembling these into the correct order in the new output list.
    5.  The function will return the newly constructed `List[ContentPart]`.

## Phase 3: Gateway and Agent Integration

### Step 6: Deprecate the `signal_artifact_for_return` Tool

-   **File:** `src/solace_agent_mesh/agent/tools/builtin_artifact_tools.py`
-   **Action:** Remove the `signal_artifact_for_return` function and its `BuiltinTool` definition (`signal_artifact_for_return_tool_def`).
-   **Details:** Also remove the tool from the `tool_registry.register()` call at the end of the file.

### Step 7: Update Gateway Component to Use the New Resolver

-   **File:** `src/solace_agent_mesh/gateway/base/component.py`
-   **Action:** Modify the gateway's event processing logic to use the new `resolve_embeds_in_parts_list` function.
-   **Details:**
    1.  The `_resolve_embeds_and_handle_signals` method will be refactored.
    2.  Instead of operating on a string, it will now extract the `parts` list from the incoming A2A event (`TaskStatusUpdateEvent` or `Task`).
    3.  It will call `resolve_embeds_in_parts_list`, passing `ResolutionMode.A2A_MESSAGE_TO_USER`.
    4.  The returned list of parts will replace the original parts list on the event object before it is sent to the user.

### Step 8: Update Agent Tool Wrapper and Recursive Resolver

-   **File:** `src/solace_agent_mesh/agent/adk/tool_wrapper.py` (Not in chat, will need to be requested)
-   **Action:** Update the `ADKToolWrapper` to pass the correct `ResolutionMode` when resolving embeds in tool parameters.
-   **Details:** The call to `resolve_embeds_recursively_in_string` will be modified to include `resolution_mode=ResolutionMode.TOOL_PARAMETER`.

-   **File:** `src/solace_agent_mesh/common/utils/embeds/modifiers.py`
-   **Action:** Update the `_apply_template` modifier to pass the correct `ResolutionMode` during its recursive call.
-   **Details:** The call to `resolve_embeds_recursively_in_string` within `_apply_template` will be modified to include `resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT`.

## Phase 4: Prompt Engineering and Documentation

### Step 9: Update Agent System Prompt

-   **File:** `src/solace_agent_mesh/agent/adk/callbacks.py`
-   **Action:** Modify the `inject_dynamic_instructions_callback` function to update the LLM's instructions.
-   **Details:**
    1.  Remove any text describing the `signal_artifact_for_return` tool.
    2.  Add a new section clearly explaining the syntax and usage of the `«artifact_return:filename:version»` embed.
    3.  Clarify that this is the only method for returning existing artifacts as attachments.
    4.  Explain that using `«artifact_content:...»` for binary files will result in them being automatically attached.

### Step 10: Update Project Documentation

-   **Files:**
    -   `docs/proposals/001-unified-artifact-return-mechanism.md`
    -   `docs/designs/001-unified-artifact-return-mechanism.md`
-   **Action:** Update the status of these documents to "Implemented" and add a reference to the final commit hash upon completion.
