# A2A Test Infrastructure Refactoring Checklist

This checklist tracks the refactoring of the test suite to align with the new `common.a2a` helper layer.

## Phase 1: Refactor Core Test Components

1.  **Refactor `TestGatewayComponent`** (`tests/sam-test-infrastructure/src/sam_test_infrastructure/gateway_interface/component.py`)
    - [x] Update imports to use `a2a.types` and `ContentPart`, removing imports from `common.types`.
    - [x] Update `_captured_outputs` type hint to use official `a2a.types`.
    - [x] Update `_translate_external_input` method signature to return `List[ContentPart]`.
    - [x] Update `_translate_external_input` implementation to use `a2a.create_*_part` helpers.

2.  **Refactor `conftest.py`** (`tests/integration/conftest.py`)
    - [ ] Remove `mock_a2a_client` fixture.
    - [ ] Remove `mock_card_resolver` fixture.
    - [ ] Rewrite `mock_task_response` to use `a2a.create_final_task`.
    - [ ] Rewrite `mock_task_response_cancel` to use `a2a.create_final_task`.
    - [ ] Rewrite `mock_sse_task_response` to use `a2a.create_status_update`.
    - [ ] Rewrite `mock_task_callback_response` to return a valid `a2a.types.TaskPushNotificationConfig`.
    - [ ] Update `mock_agent_skills` to return an `a2a.types.AgentSkill` object.
    - [ ] Update `mock_agent_card` to return an `a2a.types.AgentCard` object.

## Phase 2: Final Cleanup and Verification

3.  **Delete Deprecated Files**
    - [ ] Delete `src/solace_agent_mesh/common/types.py`.
    - [ ] Delete `src/solace_agent_mesh/common/client/client.py`.
    - [ ] Delete `src/solace_agent_mesh/common/a2a_protocol.py`.

4.  **Update Documentation**
    - [ ] Update `docs/refactoring/A2A-Helper-Refactoring-Checklist.md` to mark all items as complete.
    - [ ] Review `docs/refactoring/summary.txt` and `docs/refactoring/A2A-Helper-Layer-Design.md` for any necessary updates.
