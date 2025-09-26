# Agent Side Quest: Implementation Checklist

- [x] 1. **Config Flag**: Add `enable_side_quests` flag to `SamAgentAppConfig` in `src/solace_agent_mesh/agent/sac/app.py`.
- [x] 2. **Create Tool Class**: Create `SelfSideQuestTool` class in new file `src/solace_agent_mesh/agent/tools/self_side_quest_tool.py`.
- [x] 3. **Register Tool**: Conditionally register `SelfSideQuestTool` in `load_adk_tools` in `src/solace_agent_mesh/agent/adk/setup.py`.
- [x] 4. **Update Request Handler**: In `handle_a2a_request` (`event_handlers.py`), detect `is_side_quest` metadata and force `RUN_BASED` session behavior.
- [ ] 5. **Implement Artifact Pre-loading**: In `handle_a2a_request`, if `invoked_with_artifacts` is present, construct a rich initial prompt with artifact summaries.
- [ ] 6. **Update LLM Instructions**: Ensure `self_side_quest` tool has a clear, instructive description for the LLM in `_generate_tool_instructions_from_registry` (`callbacks.py`).
- [ ] 7. **Verify Result Handling**: Manually verify that `handle_a2a_response` correctly processes the side quest's final `Task` object, reusing `PeerAgentTool` logic.
- [ ] 8. **Verify Automatic Cleanup**: Manually verify that `finalize_task_with_cleanup` correctly deletes the temporary `RUN_BASED` session for the side quest.
- [ ] 9. **Update Documentation**: Add `enable_side_quests` flag usage and an example to `docs/proposals/agent_side_quests.md` and `docs/designs/agent_side_quests.md`.
