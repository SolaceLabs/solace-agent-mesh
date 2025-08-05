# Design Document: Refactoring Artifact Delegation to Pass-by-Reference

## 1. Objective

The goal of this refactoring is to change how AI agents delegate tasks involving artifacts. Currently, when an agent delegates a task, it sends the full content of any required artifacts to the peer agent ("pass-by-value"). This is inefficient for large files.

This work will change the mechanism to "pass-by-reference." The calling agent will only send a reference (filename and version) to the peer. The framework will then enrich the peer agent's context with a metadata summary of the referenced artifact, allowing it to understand the file without receiving its full content.

## 2. Summary of Changes

This refactoring involves modifying the `PeerAgentTool`, updating the A2A protocol handlers to process artifact references, and enhancing the test infrastructure to validate the new behavior.

## 3. Modified Files and Change Descriptions

The following files will be modified to implement this feature:

#### `src/solace_agent_mesh/agent/tools/peer_agent_tool.py`

*   **Summary of Changes:** The `PeerAgentTool` will be updated to send artifact references instead of full artifact content.
*   **Details:**
    *   The tool's function signature will be changed. The `data_artifacts` parameter (which expected a list of filenames) will be replaced with a new `artifacts` parameter that accepts a list of objects, each containing a `filename` and `version`.
    *   The `_prepare_a2a_parts` method will be simplified to no longer load artifact content from the `ArtifactService`.
    *   The `run_async` method will be updated to take the list of artifact identifiers from the `artifacts` argument and place them into the `metadata` of the outgoing `A2AMessage`.

#### `src/solace_agent_mesh/agent/protocol/event_handlers.py`

*   **Summary of Changes:** The core A2A protocol handlers will be updated to process incoming artifact references and enrich the agent's context.
*   **Details:**
    *   The `handle_a2a_request` function will be modified. It will now inspect the `metadata` of incoming `A2ARequest` messages for a new `invoked_with_artifacts` key.
    *   If artifact references are found, it will call a new helper function (`generate_artifact_metadata_summary`) to fetch the metadata for each artifact.
    *   The resulting metadata summary (a human-readable YAML string) will be prepended to the LLM prompt, giving the receiving agent the necessary context about the files.
    *   The `handle_a2a_response` function will also be updated. The old `_format_artifact_summary_from_manifest` function will be removed and replaced with calls to the new `generate_artifact_metadata_summary` helper. This ensures that when a peer agent returns an artifact, the calling agent receives a consistent metadata summary in its tool response.

#### `src/solace_agent_mesh/agent/utils/artifact_helpers.py`

*   **Summary of Changes:** A new helper function will be added to generate LLM-friendly metadata summaries for artifacts.
*   **Details:**
    *   A new asynchronous function, `generate_artifact_metadata_summary`, will be created.
    *   This function will accept a list of artifact identifiers (filename and version). It will use the `ArtifactService` to load the corresponding metadata for each, format it into a clean YAML string, and handle potential errors gracefully (e.g., if an artifact is not found).

#### `src/solace_agent_mesh/gateway/base/component.py`

*   **Summary of Changes:** The base gateway will be updated to support passing artifact references from an external system into the A2A protocol.
*   **Details:**
    *   The `submit_a2a_task` method will be modified. It will now check the `external_request_context` for an `invoked_with_artifacts` list.
    *   If this list exists, its content will be added to the `metadata` of the `A2AMessage` before it is sent to the target agent. This is the crucial link that allows test inputs (and future external integrations) to trigger the pass-by-reference flow.

#### `sam-test-infrastructure/src/sam_test_infrastructure/gateway_interface/component.py`

*   **Summary of Changes:** The test gateway component will be updated to recognize and process artifact references from declarative test definitions.
*   **Details:**
    *   The `_translate_external_input` method will be modified to check for an `invoked_with_artifacts` key in the test input data.
    *   If found, this list of artifact identifiers will be added to the `constructed_external_context` dictionary, which will then be used by the modified `submit_a2a_task` method in the base class.

#### `tests/integration/scenarios_declarative/test_declarative_runner.py`

*   **Summary of Changes:** The declarative test runner will be significantly updated to validate the new pass-by-reference flow.
*   **Details:**
    *   The `_assert_llm_interactions` function will be enhanced to support two new assertion types:
        *   `prompt_contains_artifact_summary_for`: This will verify that an LLM prompt has been correctly enriched with the metadata summary of a referenced artifact.
        *   `response_contains_artifact_summary_for`: This will verify that a tool response from a peer agent correctly includes the metadata summary of an artifact created by that peer.
    *   The test runner will use the new `generate_artifact_metadata_summary` helper to construct the expected summary strings for these assertions.

## 4. New Test Files

To ensure the new functionality is robust and correct, the following new declarative test files will be created:

*   `tests/integration/scenarios_declarative/test_data/multi_agent/delegation/test_peer_request_with_artifact.yaml`: Tests that a peer agent's prompt is correctly enriched when it receives a task with an artifact reference.
*   `tests/integration/scenarios_declarative/test_data/multi_agent/delegation/test_peer_response_with_artifact.yaml`: Tests that a calling agent correctly receives the metadata summary when a peer agent creates and returns an artifact.
*   `tests/integration/scenarios_declarative/test_data/multi_agent/delegation/test_peer_e2e_artifact_passing.yaml`: An end-to-end test combining both of the above scenarios.
*   `tests/integration/scenarios_declarative/test_data/multi_agent/delegation/test_peer_request_with_nonexistent_artifact.yaml`: Tests graceful error handling when a non-existent artifact is referenced.

---

This concludes the detailed plan for the refactoring. Once you approve, I can proceed with generating the code changes.
