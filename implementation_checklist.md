# Dynamic Tools Integration Test Implementation Checklist

### Step 1: Create Test Support Infrastructure

1.  [ ] Create the directory `tests/integration/test_support/dynamic_tools/`.
2.  [ ] Create the file `tests/integration/test_support/dynamic_tools/single_tool.py` with the `MySimpleDynamicTool` class.
3.  [ ] Create the file `tests/integration/test_support/dynamic_tools/provider_tool.py` with the `MyToolProvider` class.

### Step 2: Update `conftest.py` to Configure New Agents

4.  [ ] In `tests/integration/conftest.py`, locate the `shared_solace_connector` fixture.
5.  [ ] Add the configuration dictionary for `DynamicToolAgent`.
6.  [ ] Add the configuration dictionary for `DynamicProviderAgent`.
7.  [ ] Add the new agent configurations to the `app_infos` list within the fixture.

### Step 3: Create and Implement Programmatic Tests

8.  [ ] Create the new test file `tests/integration/scenarios_programmatic/test_dynamic_tools.py`.
9.  [ ] In `test_dynamic_tools.py`, add the `pytest.mark.dynamic_tools` marker to the `pytestmark` list.
10. [ ] Implement the test `test_single_dynamic_tool_execution` to verify the `DynamicToolAgent`.
11. [ ] Implement the test `test_dynamic_tool_provider_execution` to verify the `DynamicProviderAgent`.
