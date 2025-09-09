# Dynamic Tools Integration Test Implementation Checklist

### Step 1: Enhance Declarative Test Framework

1.  [x] In `tests/sam-test-infrastructure/src/sam_test_infrastructure/llm_server/server.py`, add the `_verify_tool_declarations` helper method to `TestLLMServer`.
2.  [x] In `llm_server/server.py`, add the `_verify_tool_responses` helper method to `TestLLMServer`.
3.  [x] In `llm_server/server.py`, add the `_verify_expected_request` dispatcher method to `TestLLMServer`.
4.  [x] In `llm_server/server.py`, update the `chat_completions` endpoint to call `_verify_expected_request` when processing a stateful test case turn.

### Step 2: Update Agent Configuration for Testing

5.  [x] In `tests/integration/conftest.py`, remove the separate `DynamicToolAgent` and `DynamicProviderAgent` configurations.
6.  [x] In `tests/integration/conftest.py`, add a single `CombinedDynamicAgent` configuration that loads both dynamic tool modules.
7.  [x] In `tests/integration/conftest.py`, update the `app_infos` list to use the new `CombinedDynamicAgent_App`.

### Step 3: Implement Declarative Test Case

8.  [x] Delete the programmatic test file `tests/integration/scenarios_programmatic/test_dynamic_tools.py`.
9.  [x] Create the new declarative test file `tests/integration/scenarios_declarative/test_data/dynamic_tools/test_dynamic_tool_loading.yaml`.
10. [x] In the new YAML file, implement the test case to verify both tool loading and execution using the new `expected_tool_declarations_contain` assertion.
