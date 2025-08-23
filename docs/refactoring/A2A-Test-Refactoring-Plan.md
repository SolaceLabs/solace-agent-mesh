# Refactoring Plan: Aligning Test Infrastructure with the A2A Helper Layer

**Objective:** To completely remove the deprecated `common.types` system from our test suite and refactor all test infrastructure to use the official `a2a.types` via our new `common.a2a` helper layer. This will make our tests more robust, accurate, and maintainable.

---

## Phase 1: Refactor Core Test Components

This phase focuses on fixing the central components of our test harness to use the correct A2A types and helpers.

1.  **Refactor `TestGatewayComponent`**
    -   **File:** `tests/sam-test-infrastructure/src/sam_test_infrastructure/gateway_interface/component.py`
    -   **Goal:** This component is the bridge between our tests and the agent. It must be the first thing we fix.
    -   **Actions:**
        1.  **Update Imports:** Remove all imports from the deprecated `solace_agent_mesh.common.types`. Add imports for the official `a2a.types` and our new `ContentPart` alias from `solace_agent_mesh.common.a2a.types`.
        2.  **Update Type Hints:** Change the type hint for the `_captured_outputs` attribute to use the official `a2a.types` (e.g., `TaskStatusUpdateEvent`, `Task`, etc.).
        3.  **Update `_translate_external_input` Method:**
            -   Modify the method signature to return `Tuple[str, List[ContentPart], Dict[str, Any]]`, aligning it with the `BaseGatewayComponent` and resolving the type conflict.
            -   Rewrite the method's implementation to use the `a2a.create_text_part`, `a2a.create_data_part`, and `a2a.create_file_part_...` helpers. It will no longer create instances of the old "shadow" types.

2.  **Refactor `conftest.py` Fixtures**
    -   **File:** `tests/integration/conftest.py`
    -   **Goal:** Ensure all test data fixtures produce valid, official `a2a.types` objects using our helper layer.
    -   **Actions:**
        1.  **Remove Obsolete Fixtures:** Delete the `mock_a2a_client` and `mock_card_resolver` fixtures, as they are based on the deprecated `common.client` module.
        2.  **Rewrite Mock Data Fixtures:**
            -   `mock_task_response`: Rewrite to use `a2a.create_final_task` to return a valid `a2a.types.Task` object.
            -   `mock_task_response_cancel`: Rewrite to use `a2a.create_final_task` with a `canceled` status.
            -   `mock_sse_task_response`: Rewrite to use `a2a.create_status_update` to return a valid `a2a.types.TaskStatusUpdateEvent`.
            -   `mock_task_callback_response`: Rewrite to return a valid `a2a.types.TaskPushNotificationConfig`.
        3.  **Update `AgentCard` Fixtures:**
            -   `mock_agent_skills`: Update to return an `a2a.types.AgentSkill` object.
            -   `mock_agent_card`: Update to return an `a2a.types.AgentCard` object.

---

## Phase 2: Final Cleanup and Verification

This phase removes the now-unused code and updates our documentation to reflect the completed refactoring.

3.  **Delete Deprecated Files**
    -   **Goal:** Eradicate the old type system and client from the codebase.
    -   **Actions:**
        1.  Delete the file: `src/solace_agent_mesh/common/types.py`
        2.  Delete the file: `src/solace_agent_mesh/common/client/client.py`
        3.  Delete the empty file: `src/solace_agent_mesh/common/a2a_protocol.py`

4.  **Update Documentation**
    -   **Goal:** Ensure our planning documents are accurate and reflect the final state of the project.
    -   **Actions:**
        1.  Update `docs/refactoring/A2A-Helper-Refactoring-Checklist.md` to mark the test-related refactoring items as complete.
        2.  Review `docs/refactoring/summary.txt` and `docs/refactoring/A2A-Helper-Layer-Design.md` for any necessary updates based on the final implementation.
