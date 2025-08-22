# A2A Helper Layer: Implementation Checklist

This checklist provides a terse, actionable list of tasks for creating the A2A Helper Abstraction Layer, as detailed in the implementation plan.

## Phase 1: Create Package Structure

1.  [ ] Create directory `src/solace_agent_mesh/common/a2a/`.
2.  [ ] Create `src/solace_agent_mesh/common/a2a/__init__.py`.

## Phase 2: Populate Helper Modules

3.  [x] Create `src/solace_agent_mesh/common/a2a/protocol.py`.
4.  [x] Move all topic construction functions from `a2a_protocol.py` to `a2a/protocol.py`.
5.  [x] Add JSON-RPC request/response parsing helpers to `a2a/protocol.py`.
6.  [x] Create `src/solace_agent_mesh/common/a2a/message.py`.
7.  [x] Add `Message` and `Part` creation helpers to `a2a/message.py`.
8.  [x] Add `Message` and `Part` consumption helpers to `a2a/message.py`.
9.  [x] Create `src/solace_agent_mesh/common/a2a/task.py`.
10. [x] Add `Task` creation and consumption helpers to `a2a/task.py`.
11. [x] Create `src/solace_agent_mesh/common/a2a/artifact.py`.
12. [x] Add `Artifact` creation and consumption helpers to `a2a/artifact.py`.
13. [x] Create `src/solace_agent_mesh/common/a2a/events.py`.
14. [x] Add A2A event object creation and consumption helpers to `a2a/events.py`.
15. [ ] Create `src/solace_agent_mesh/common/a2a/translation.py`.
16. [ ] Move `translate_a2a_to_adk_content` and `format_adk_event_as_a2a` from `a2a_protocol.py` to `a2a/translation.py`.

## Phase 3: Finalize and Clean Up

17. [ ] Populate `src/solace_agent_mesh/common/a2a/__init__.py` to expose the public API.
18. [ ] Delete the old `src/solace_agent_mesh/common/a2a_protocol.py` file.
