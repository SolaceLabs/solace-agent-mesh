# Checklist: Refactor Artifact Delegation to Pass-by-Reference

This document outlines the files to be modified and created to implement the pass-by-reference artifact delegation feature.

## Files to Modify

- [ ] **`src/solace_agent_mesh/agent/tools/peer_agent_tool.py`**
    -   Change the `data_artifacts` parameter to `artifacts` to accept artifact identifiers (filename/version).
    -   Stop loading artifact content; instead, place the identifiers into the A2A message metadata.

- [ ] **`src/solace_agent_mesh/agent/protocol/event_handlers.py`**
    -   In `handle_a2a_request`, check for artifact identifiers in message metadata and enrich the LLM prompt with a metadata summary.
    -   In `handle_a2a_response`, replace the old summary logic with the new `generate_artifact_metadata_summary` helper.

- [ ] **`src/solace_agent_mesh/agent/utils/artifact_helpers.py`**
    -   Add the new `generate_artifact_metadata_summary` helper function.

- [ ] **`src/solace_agent_mesh/gateway/base/component.py`**
    -   Update `submit_a2a_task` to pass `invoked_with_artifacts` from the external context into the A2A message metadata.

- [ ] **`sam-test-infrastructure/src/sam_test_infrastructure/gateway_interface/component.py`**
    -   Update `_translate_external_input` to pass `invoked_with_artifacts` from the test definition into the external context.

- [ ] **`tests/integration/scenarios_declarative/test_declarative_runner.py`**
    -   Enhance `_assert_llm_interactions` to validate that artifact metadata summaries are present in LLM prompts and tool responses.

## New Test Files to Create

- [ ] `tests/integration/scenarios_declarative/test_data/multi_agent/delegation/test_peer_request_with_artifact.yaml`
- [ ] `tests/integration/scenarios_declarative/test_data/multi_agent/delegation/test_peer_response_with_artifact.yaml`
- [ ] `tests/integration/scenarios_declarative/test_data/multi_agent/delegation/test_peer_e2e_artifact_passing.yaml`
- [ ] `tests/integration/scenarios_declarative/test_data/multi_agent/delegation/test_peer_request_with_nonexistent_artifact.yaml`
