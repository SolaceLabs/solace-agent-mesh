# Implementation Plan: Frontend-Driven Chat Persistence

## Document Information

- **Feature**: Frontend-Driven Chat Persistence
- **Version**: 1.0
- **Date**: 2025-01-02
- **Status**: Implementation Ready
- **Related Documents**: 
  - [Feature Specification](../features/frontend-driven-chat-persistence.md)
  - [Detailed Design](../design/frontend-driven-chat-persistence-detailed-design.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Implementation Steps](#implementation-steps)
4. [Validation Checklist](#validation-checklist)

---

## Overview

This document provides a step-by-step implementation plan for the frontend-driven chat persistence feature. The plan is organized into numbered major steps that can be executed sequentially, with each step building on the previous ones.

**Estimated Total Effort:** 3-4 days for a single developer

**Implementation Strategy:** Backend first, then frontend, then cleanup. This allows for incremental development and validation.

---

## Prerequisites

Before starting implementation, ensure:

1. ✅ Feature specification approved
2. ✅ Detailed design reviewed and approved
3. ✅ Development environment set up with database access
4. ✅ All dependencies installed (`pip install -r requirements.txt`)
5. ✅ Database migrations can be run successfully
6. ✅ Frontend development server can connect to backend

---

## Implementation Steps

### Step 1: Create Database Migration

**Estimated Time:** 1-2 hours

**Objective:** Create the new `chat_tasks` table via Alembic migration.

**Files to Create:**
- `src/solace_agent_mesh/gateway/http_sse/alembic/versions/YYYYMMDD_create_chat_tasks_table.py`

**Implementation Details:**

1.1. Generate migration file using `alembic revision -m "create_chat_tasks_table"`

1.2. Implement `upgrade()` function to create table with columns:
   - `id` VARCHAR PRIMARY KEY
   - `session_id` VARCHAR NOT NULL with FOREIGN KEY to sessions(id) ON DELETE CASCADE
   - `user_id` VARCHAR NOT NULL
   - `user_message` TEXT NULL
   - `message_bubbles` JSON NOT NULL
   - `task_metadata` JSON NULL
   - `created_time` BIGINT NOT NULL
   - `updated_time` BIGINT NULL

1.3. Create indexes on `session_id`, `user_id`, and `created_time`

1.4. Implement `downgrade()` function to drop the table

**Validation:**
- Migration runs without errors
- Table structure matches design
- Foreign key cascade works
- Indexes are created

---

### Step 2: Create Domain Entity

**Estimated Time:** 1 hour

**Objective:** Create the `ChatTask` domain entity with business logic.

**Files to Create:**
- `src/solace_agent_mesh/gateway/http_sse/repository/entities/chat_task.py`

**Files to Modify:**
- `src/solace_agent_mesh/gateway/http_sse/repository/entities/__init__.py`

**Implementation Details:**

2.1. Create Pydantic `BaseModel` with `ConfigDict(from_attributes=True)`

2.2. Define fields: `id`, `session_id`, `user_id`, `user_message`, `message_bubbles`, `task_metadata`, `created_time`, `updated_time`

2.3. Add `add_feedback(feedback_type, feedback_text)` method

2.4. Add `get_feedback()` method

2.5. Add validation for non-empty `message_bubbles`

2.6. Update `__init__.py` to export `ChatTask`

**Validation:**
- Entity instantiates correctly
- Business logic methods work
- Validation catches invalid data

---

### Step 3: Create SQLAlchemy Model

**Estimated Time:** 1 hour

**Objective:** Create the `ChatTaskModel` SQLAlchemy model.

**Files to Create:**
- `src/solace_agent_mesh/gateway/http_sse/repository/models/chat_task_model.py`

**Files to Modify:**
- `src/solace_agent_mesh/gateway/http_sse/repository/models/__init__.py`

**Implementation Details:**

3.1. Create model class inheriting from `Base`

3.2. Set `__tablename__ = "chat_tasks"`

3.3. Define all columns matching database schema

3.4. Configure foreign key with CASCADE delete

3.5. Update `__init__.py` to export `ChatTaskModel`

**Validation:**
- Model imports without errors
- Structure matches database schema
- JSON columns work correctly

---

### Step 4: Create Repository

**Estimated Time:** 2-3 hours

**Objective:** Create `ChatTaskRepository` with CRUD operations.

**Files to Create:**
- `src/solace_agent_mesh/gateway/http_sse/repository/chat_task_repository.py`

**Files to Modify:**
- `src/solace_agent_mesh/gateway/http_sse/repository/interfaces.py`
- `src/solace_agent_mesh/gateway/http_sse/repository/__init__.py`

**Implementation Details:**

4.1. Add `IChatTaskRepository` interface to `interfaces.py`

4.2. Implement `ChatTaskRepository` class with methods:
   - `save(task)` - upsert logic
   - `find_by_session(session_id, user_id)` - query and convert
   - `find_by_id(task_id, user_id)` - single task lookup
   - `delete_by_session(session_id)` - cascade delete

4.3. Add `_model_to_entity()` helper method

4.4. Update `__init__.py` to export repository

**Validation:**
- Upsert works correctly
- Queries return correct data
- Authorization filtering works
- Cascade delete works

---

### Step 5: Add Task Methods to SessionService

**Estimated Time:** 2-3 hours

**Objective:** Add task-related methods to `SessionService`.

**Files to Modify:**
- `src/solace_agent_mesh/gateway/http_sse/services/session_service.py`

**Implementation Details:**

5.1. Add `save_task()` method:
   - Validate session ownership
   - Create ChatTask entity
   - Save via repository
   - Update session activity
   - Return saved task

5.2. Add `get_session_tasks()` method:
   - Validate session ownership
   - Query via repository
   - Return task list

5.3. Add `get_session_messages_from_tasks()` method:
   - Load tasks
   - Flatten message_bubbles to Message entities
   - Return for backward compatibility

**Validation:**
- Task saving works
- Task retrieval works
- Message flattening works
- Authorization checks work

---

### Step 6: Create API DTOs

**Estimated Time:** 1-2 hours

**Objective:** Create request/response DTOs for new endpoints.

**Files to Create:**
- `src/solace_agent_mesh/gateway/http_sse/routers/dto/requests/task_requests.py`
- `src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/task_responses.py`

**Implementation Details:**

6.1. Create `SaveTaskRequest` with fields:
   - `task_id`, `user_message`, `message_bubbles`, `task_metadata`
   - Use `Field(alias=...)` for camelCase conversion
   - Add validators for required fields

6.2. Create `TaskResponse` with all task fields

6.3. Create `TaskListResponse` with tasks array

**Validation:**
- DTOs validate correctly
- Serialization/deserialization works
- Field aliases work

---

### Step 7: Create API Endpoints

**Estimated Time:** 3-4 hours

**Objective:** Add new task endpoints to sessions router.

**Files to Modify:**
- `src/solace_agent_mesh/gateway/http_sse/routers/sessions.py`

**Implementation Details:**

7.1. Add `POST /sessions/{session_id}/tasks` endpoint:
   - Parse `SaveTaskRequest`
   - Call `SessionService.save_task()`
   - Return `TaskResponse` with 201/200
   - Handle errors: 400, 403, 404, 422

7.2. Add `GET /sessions/{session_id}/tasks` endpoint:
   - Call `SessionService.get_session_tasks()`
   - Return `TaskListResponse`
   - Handle errors: 403, 404

7.3. Modify `GET /sessions/{session_id}/messages` endpoint:
   - Call `SessionService.get_session_messages_from_tasks()`
   - Keep same response format
   - Maintain backward compatibility

**Validation:**
- Can save tasks via API
- Can retrieve tasks via API
- Authorization works
- Backward compatibility maintained

---

### Step 8: Update Feedback Service

**Estimated Time:** 1-2 hours

**Objective:** Update `FeedbackService` to also update task metadata.

**Files to Modify:**
- `src/solace_agent_mesh/gateway/http_sse/services/feedback_service.py`

**Implementation Details:**

8.1. Modify `process_feedback()` method:
   - After saving to feedback table (existing)
   - Load task from `chat_tasks` using `task_id`
   - If task exists, update `task_metadata.feedback`
   - Save updated task
   - Handle errors gracefully (log but don't fail)

**Validation:**
- Feedback saves to feedback table
- Task metadata is updated
- Missing task doesn't break submission
- Errors are logged appropriately

---

### Step 9: Frontend - Create Helper Functions

**Estimated Time:** 2-3 hours

**Objective:** Create frontend helper functions for serialization and API calls.

**Files to Modify:**
- `client/webui/frontend/src/lib/providers/ChatProvider.tsx`

**Implementation Details:**

9.1. Create `serializeMessageBubble(message: MessageFE): MessageBubble`
   - Extract text from parts
   - Convert File objects to {name, type}
   - Include all optional fields
   - Return MessageBubble object

9.2. Create `saveTaskToBackend(taskData): Promise<void>`
   - Use `authenticatedFetch` to POST
   - Handle errors gracefully (log only)
   - No user notifications (silent per NFR-1)

9.3. Create `deserializeTaskToMessages(task): MessageFE[]`
   - Convert each bubble to MessageFE
   - Reconstruct parts array
   - Set isComplete: true
   - Return message array

9.4. Create `loadSessionTasks(sessionId): Promise<void>`
   - Fetch tasks from API
   - Deserialize to messages
   - Extract feedback state
   - Update state
   - Handle errors (show notification)

**Validation:**
- Serialization preserves data
- API calls work correctly
- Deserialization recreates messages
- Error handling works

---

### Step 10: Frontend - Update Message Saving Logic

**Estimated Time:** 2-3 hours

**Objective:** Integrate task saving into chat flow.

**Files to Modify:**
- `client/webui/frontend/src/lib/providers/ChatProvider.tsx`

**Implementation Details:**

10.1. Update `handleSubmit()` for user messages:
   - After receiving taskId from A2A
   - Call `saveTaskToBackend()` with initial task data
   - Don't wait for completion
   - Continue with existing logic

10.2. Update `handleSseMessage()` for agent messages:
   - When `isFinalEvent` is true
   - Gather all messages for taskId
   - Filter out status bubbles
   - Serialize to MessageBubble format
   - Call `saveTaskToBackend()` with complete data
   - Continue with existing logic

**Validation:**
- User messages saved after submission
- Agent messages saved when complete
- Status bubbles filtered out
- All data preserved
- UI not blocked

---

### Step 11: Frontend - Update Session Loading Logic

**Estimated Time:** 1-2 hours

**Objective:** Load session history from tasks instead of messages.

**Files to Modify:**
- `client/webui/frontend/src/lib/providers/ChatProvider.tsx`

**Implementation Details:**

11.1. Update `handleSwitchSession()`:
   - Replace `getHistory()` with `loadSessionTasks()`
   - Use new deserialization logic
   - Update state with messages and feedback

11.2. Verify `handleNewSession()` needs no changes

**Validation:**
- Session history loads correctly
- Messages in correct order
- Feedback state restored
- Files and artifacts display

---

### Step 12: Frontend - Verify Feedback Submission

**Estimated Time:** 30 minutes

**Objective:** Ensure feedback updates work with new backend.

**Files to Modify:**
- None (verification only)

**Implementation Details:**

12.1. Verify `handleFeedbackSubmit()` still works
   - Backend now handles task metadata update
   - No frontend changes needed

**Validation:**
- Feedback submission works
- Task metadata updated in database
- UI reflects feedback state

---

### Step 13: Remove Old Backend Message Saving Logic

**Estimated Time:** 1 hour

**Objective:** Clean up deprecated backend code.

**Files to Modify:**
- `src/solace_agent_mesh/gateway/http_sse/component.py` (or equivalent)

**Implementation Details:**

13.1. Locate and remove agent message saving code:
   - Find section that saves final agent response to persistence
   - Remove entire block
   - Keep SSE sending logic
   - Add comment explaining frontend now handles persistence

**Validation:**
- Backend no longer saves agent messages
- SSE functionality still works
- No errors in logs

---

### Step 14: Documentation Updates

**Estimated Time:** 1 hour

**Objective:** Update relevant documentation.

**Files to Modify:**
- API documentation
- README (if applicable)
- CHANGELOG

**Implementation Details:**

14.1. Document new API endpoints

14.2. Note backward compatibility for /messages endpoint

14.3. Update CHANGELOG with feature addition

14.4. Add any necessary setup instructions

**Validation:**
- Documentation is accurate
- Examples are correct
- CHANGELOG updated

---

## Validation Checklist

### Backend Validation

- [ ] Database migration runs successfully
- [ ] ChatTask entity works correctly
- [ ] ChatTaskModel maps to database
- [ ] Repository CRUD operations work
- [ ] SessionService methods work
- [ ] API endpoints respond correctly
- [ ] Authorization checks work
- [ ] Feedback service updates tasks
- [ ] Backward compatibility maintained

### Frontend Validation

- [ ] Helper functions work correctly
- [ ] Task saving works on submit
- [ ] Task saving works on completion
- [ ] Session loading works
- [ ] Feedback submission works
- [ ] Status bubbles filtered out
- [ ] All message data preserved
- [ ] Error handling works

### Integration Validation

- [ ] Complete conversation flow works
- [ ] Session switching works
- [ ] Feedback persists
- [ ] Files display correctly
- [ ] Artifacts display correctly
- [ ] Error messages display correctly
- [ ] No console errors
- [ ] No backend errors

### Data Validation

- [ ] Tasks saved to database correctly
- [ ] Message bubbles JSON is valid
- [ ] Task metadata JSON is valid
- [ ] Feedback integrated correctly
- [ ] Timestamps are correct
- [ ] Foreign keys work
- [ ] Cascade delete works

---

## Notes

- Each step builds on previous steps
- Validate each step before proceeding
- Backend steps (1-8) can be done independently of frontend
- Frontend steps (9-12) depend on backend completion
- Step 13 (cleanup) should only be done after full validation
- Keep old code until new system is proven stable

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-02 | System | Initial implementation plan |
