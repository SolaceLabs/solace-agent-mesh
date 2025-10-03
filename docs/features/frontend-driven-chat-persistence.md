# Feature: Frontend-Driven Chat Persistence

## Overview

Refactor the chat message persistence system to make the frontend the authoritative source of truth for what users see in the chat window, rather than having the backend attempt to infer the displayed state from A2A protocol messages.

## Problem Statement

### Current Issues

1. **State Mismatch**: The backend currently saves the final A2A task response, but what users actually see in the browser can be significantly different due to:
   - Embed resolution (artifact_content and other embed types)
   - Streaming updates that accumulate over time
   - Text transformations applied during rendering
   - UI-specific state (feedback, file attachments, artifact notifications)

2. **Inaccurate History**: When users load a previous session, the displayed messages may not match what they originally saw because the backend's saved state doesn't capture the frontend's final rendered output.

3. **Backend Complexity**: The backend contains complex logic trying to determine what the user saw by parsing A2A protocol messages, which is an implementation detail that shouldn't drive the persistence layer.

4. **Loss of UI State**: Important UI state like feedback (thumbs up/down) is stored separately and not integrated with the message history.

## Goals

### Primary Goals

1. **Accurate Replay**: When a user loads a previous session, they should see exactly what was displayed during the original conversation, including all resolved embeds, file attachments, and UI state.

2. **Frontend Authority**: The frontend chat UI becomes the single source of truth for what constitutes the "chat history" that should be persisted.

3. **Simplified Backend**: The backend becomes a simple storage layer that doesn't need to understand A2A protocol details or make decisions about what to save.

4. **Integrated State**: All UI state (feedback, attachments, notifications) is saved together with the messages as a cohesive unit.

### Secondary Goals

1. **Future-Proof**: The persistence model should easily accommodate future UI features (message editing, reactions, annotations, etc.) without requiring database schema changes.

2. **Efficient Storage**: Minimize database writes while maintaining data integrity.

3. **Resilient**: Handle network failures gracefully with retry logic, but accept that some data loss is acceptable if the network is unavailable.

## High-Level Approach

### Conceptual Model Shift

**From:** "Save individual message bubbles as they appear"
**To:** "Save complete task interactions as logical units"

A "task" represents one complete interaction:
- User submits a message/question
- Agent processes and responds (potentially with multiple message bubbles, files, artifacts)
- Task completes (successfully, with error, or cancelled)

This task-based model is more efficient and semantically correct than saving individual message bubbles.

### Data Model

Instead of storing individual `chat_messages`, we store `chat_tasks` where each task contains:

1. **Task Identity**: The A2A taskId as the primary key
2. **User Input**: The original user message (for search/display)
3. **Message Bubbles**: A JSON array containing all message bubbles that were rendered during this task
4. **Task Metadata**: Status, feedback, agent name, and other task-level information
5. **Timestamps**: When the task was created and last updated

### Persistence Strategy

**User Messages:**
- Save immediately after successful A2A request submission
- If the A2A request fails, don't save (user will retry)

**Agent Messages:**
- Save when the task completes (final response, error, or cancellation)
- Capture all message bubbles that were displayed during the task
- Include all UI state (files, artifacts, notifications)

**Updates:**
- When feedback is submitted, update the existing task record
- Use upsert semantics (overwrite if exists, insert if new)
- Future updates (edits, reactions) follow the same pattern

## Requirements

### Functional Requirements

1. **FR-1**: The frontend must save all message bubbles for a completed task as a single atomic unit
2. **FR-2**: The saved data must include everything needed to recreate the exact visual state of the chat window
3. **FR-3**: User messages must be saved immediately after successful A2A request submission
4. **FR-4**: Agent messages must be saved when the task completes (success, error, or cancellation)
5. **FR-5**: Status bubbles (transient UI indicators) must NOT be saved
6. **FR-6**: Feedback state (thumbs up/down) must be saved as part of the task metadata
7. **FR-7**: When loading a session, messages must appear exactly as they did originally
8. **FR-8**: The system must support updating task records (e.g., when feedback is added later)
9. **FR-9**: Failed save attempts should be retried, but data loss is acceptable if the network is unavailable

### Non-Functional Requirements

1. **NFR-1**: Saving must be silent (no user-visible indicators or errors)
2. **NFR-2**: The system must handle one save operation per task (not per message bubble)
3. **NFR-3**: The metadata structure must be flexible (JSON) to accommodate future UI features without schema changes
4. **NFR-4**: The backend must not need to understand A2A protocol details to save/load messages

## Key Decisions

### Decision 1: Task-Based Storage Model

**Decision**: Store complete task interactions as single records, not individual message bubbles.

**Rationale**: 
- More efficient (one DB write per task instead of N writes)
- Semantically correct (a task is the natural unit of conversation)
- Atomic (either the whole task is saved or none of it)
- Easier to update (one record to modify for feedback, etc.)

### Decision 2: Frontend-Driven Persistence

**Decision**: The frontend explicitly saves messages after rendering, rather than the backend inferring what to save from A2A messages.

**Rationale**:
- Frontend knows exactly what the user saw
- Backend doesn't need to parse/interpret A2A protocol
- Separation of concerns (UI state vs. protocol state)
- More accurate history replay

### Decision 3: JSON Metadata Storage

**Decision**: Store all UI state in a flexible JSON metadata field, not as separate database columns.

**Rationale**:
- No schema changes needed for new UI features
- Can store arbitrary nested structures (files, parts, notifications)
- Modern databases handle JSON efficiently
- Easier to evolve over time

### Decision 4: Upsert Semantics

**Decision**: Use taskId as the primary key and support overwriting existing records.

**Rationale**:
- Enables updating tasks (e.g., adding feedback later)
- Idempotent (safe to retry saves)
- Supports future features (message editing, status updates)
- Simpler error handling

### Decision 5: Don't Save Failed Submissions

**Decision**: Only save user messages after successful A2A request submission. Don't save messages that fail before getting a taskId.

**Rationale**:
- Failed submissions will be retried by the user
- Avoids orphaned messages without task context
- Simpler implementation
- Acceptable data loss scenario

### Decision 6: Remove Backend Message Saving

**Decision**: Remove the existing backend logic that attempts to save agent messages from A2A protocol events.

**Rationale**:
- Eliminates duplicate/conflicting save logic
- Reduces backend complexity
- Frontend is now the authoritative source
- Backend becomes a simple storage API

## Success Criteria

1. **Accuracy**: Loaded sessions display messages exactly as they appeared originally, including all resolved embeds and UI state
2. **Completeness**: All message bubbles, files, artifacts, and feedback state are preserved
3. **Simplicity**: Backend code is simpler and doesn't contain A2A protocol parsing logic
4. **Flexibility**: New UI features can be added without database schema changes
5. **Efficiency**: One database write per task, not per message bubble

## Out of Scope

The following are explicitly out of scope for this feature:

1. Backward compatibility with existing saved messages (not yet rolled out)
2. User-visible save status indicators or error messages
3. Offline support or sophisticated retry mechanisms
4. Performance optimization for high-frequency saves
5. Database load concerns or caching strategies
6. Migration scripts for existing data
7. Feature flags or gradual rollout
8. Handling edge cases like browser crashes mid-stream
9. Message size limits or validation

## Future Considerations

This design enables future enhancements:

1. **Message Editing**: Update the task record with edited content
2. **Message Reactions**: Add reactions to task metadata
3. **Message Annotations**: Store user notes or highlights
4. **Task-Level Analytics**: Duration, token count, cost tracking
5. **Advanced Search**: Search within message content and metadata
6. **Export/Import**: Easy to serialize/deserialize complete conversations

## Dependencies

- Existing session management system
- SQLAlchemy ORM and database infrastructure
- Frontend message state management (ChatProvider)
- A2A task completion detection logic

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Network failures during save | Medium | Implement retry queue, accept some data loss |
| Large message payloads | Low | JSON storage is efficient, no immediate size concerns |
| Concurrent updates to same task | Low | Last-write-wins is acceptable for this use case |
| Frontend bugs causing bad data | Medium | Validate data structure on backend, log errors |

## Approval

This feature requires approval from:
- Product Owner (for UX implications)
- Technical Lead (for architecture changes)
- Backend Team (for API changes)
- Frontend Team (for implementation effort)
