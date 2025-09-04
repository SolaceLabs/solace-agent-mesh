# Implementation Checklist: Unified Artifact Return Mechanism

This checklist provides a high-level overview of the tasks required to implement the feature, aligned with the detailed implementation plan.

## Phase 1: Foundational Changes in Embed Utilities

1.  [x] **Define `ResolutionMode` Enum:** Create the `ResolutionMode` enum in `src/solace_agent_mesh/common/utils/embeds/types.py` with `A2A_MESSAGE_TO_USER`, `TOOL_PARAMETER`, and `RECURSIVE_ARTIFACT_CONTENT` members.
2.  [x] **Update Embed Constants:** Add `"artifact_return"` to the `LATE_EMBED_TYPES` set in `src/solace_agent_mesh/common/utils/embeds/constants.py`.

## Phase 2: Core Resolver Logic Refactoring

3.  [x] **Update Resolver Signatures:** Add the `resolution_mode: ResolutionMode` parameter to `evaluate_embed`, `resolve_embeds_in_string`, and `resolve_embeds_recursively_in_string` in `src/solace_agent_mesh/common/utils/embeds/resolver.py`.
4.  [x] **Implement Context-Aware Logic:** In `evaluate_embed`, add logic to:
    -   Emit `SIGNAL_ARTIFACT_RETURN` only when `resolution_mode` is `A2A_MESSAGE_TO_USER`.
    -   Emit `SIGNAL_INLINE_BINARY_CONTENT` for binary `artifact_content` results.
    -   Ignore `artifact_return` in other modes.
5.  [ ] **Create `Part` List Resolver:** Implement the new `resolve_embeds_in_parts_list` function in `src/solace_agent_mesh/common/utils/embeds/resolver.py` to handle `List[Part]` transformations.

## Phase 3: Gateway and Agent Integration

6.  [ ] **Deprecate `signal_artifact_for_return` Tool:** Delete the `signal_artifact_for_return` function and its `BuiltinTool` registration from `src/solace_agent_mesh/agent/tools/builtin_artifact_tools.py`.
7.  [ ] **Update Gateway Component:** Refactor `_resolve_embeds_and_handle_signals` in `src/solace_agent_mesh/gateway/base/component.py` to use the new `resolve_embeds_in_parts_list` function, passing `ResolutionMode.A2A_MESSAGE_TO_USER`.
8.  [ ] **Update `ADKToolWrapper`:** Modify the call to the embed resolver in `src/solace_agent_mesh/agent/adk/tool_wrapper.py` to pass `resolution_mode=ResolutionMode.TOOL_PARAMETER`.
9.  [ ] **Update `_apply_template` Modifier:** Modify the recursive call to the embed resolver in `src/solace_agent_mesh/common/utils/embeds/modifiers.py` to pass `resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT`.

## Phase 4: Prompt Engineering and Documentation

10. [ ] **Update Agent System Prompt:** Modify `inject_dynamic_instructions_callback` in `src/solace_agent_mesh/agent/adk/callbacks.py` to remove instructions for the old tool and add instructions for the new `«artifact_return:...»` embed.
11. [ ] **Update Project Documentation:** After implementation is complete, update the `proposal` and `design` documents to reflect their implemented status.
