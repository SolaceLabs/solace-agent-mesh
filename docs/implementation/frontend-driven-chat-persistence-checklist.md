# Implementation Checklist: Frontend-Driven Chat Persistence

**Related Documents:**
- [Implementation Plan](./frontend-driven-chat-persistence-implementation-plan.md)
- [Detailed Design](../design/frontend-driven-chat-persistence-detailed-design.md)
- [Feature Specification](../features/frontend-driven-chat-persistence.md)

---

## Backend Implementation

### Step 1: Database Migration (1-2 hours)
- [x] 1.1 Generate migration: `alembic revision -m "create_chat_tasks_table"`
- [x] 1.2 Implement `upgrade()` - create `chat_tasks` table with all columns
- [x] 1.3 Create indexes on `session_id`, `user_id`, `created_time`
- [x] 1.4 Implement `downgrade()` - drop table
- [ ] 1.5 Test: `alembic upgrade head`
- [ ] 1.6 Test: `alembic downgrade -1`
- [ ] 1.7 Test: `alembic upgrade head` again
- [ ] 1.8 Verify table structure and foreign key cascade

### Step 2: Domain Entity (1 hour)
- [x] 2.1 Create `chat_task.py` with Pydantic model
- [x] 2.2 Add all fields matching schema
- [x] 2.3 Implement `add_feedback(feedback_type, feedback_text)` method
- [x] 2.4 Implement `get_feedback()` method
- [x] 2.5 Add validation for non-empty `message_bubbles`
- [x] 2.6 Update `entities/__init__.py` to export `ChatTask`
- [ ] 2.7 Test: Entity instantiation with valid data
- [ ] 2.8 Test: Business logic methods work correctly

### Step 3: SQLAlchemy Model (1 hour)
- [x] 3.1 Create `chat_task_model.py` inheriting from `Base`
- [x] 3.2 Set `__tablename__ = "chat_tasks"`
- [x] 3.3 Define all columns matching database schema
- [x] 3.4 Configure foreign key with CASCADE delete
- [x] 3.5 Update `models/__init__.py` to export `ChatTaskModel`
- [ ] 3.6 Test: Model imports without errors
- [ ] 3.7 Test: JSON columns serialize/deserialize correctly

### Step 4: Repository (2-3 hours)
- [x] 4.1 Add `IChatTaskRepository` interface to `interfaces.py`
- [x] 4.2 Create `chat_task_repository.py` implementing interface
- [x] 4.3 Implement `save(task)` with upsert logic
- [x] 4.4 Implement `find_by_session(session_id, user_id)`
- [x] 4.5 Implement `find_by_id(task_id, user_id)`
- [x] 4.6 Implement `delete_by_session(session_id)`
- [x] 4.7 Add `_model_to_entity()` helper method
- [x] 4.8 Update `repository/__init__.py` to export repository
- [ ] 4.9 Test: Upsert creates new task
- [ ] 4.10 Test: Upsert updates existing task
- [ ] 4.11 Test: Find by session returns correct tasks
- [ ] 4.12 Test: Authorization filtering works

### Step 5: Session Service (2-3 hours)
- [x] 5.1 Add `save_task()` method to `SessionService`
- [x] 5.2 Add `get_session_tasks()` method
- [x] 5.3 Add `get_session_messages_from_tasks()` method
- [x] 5.4 Implement session validation in all methods
- [x] 5.5 Implement authorization checks
- [ ] 5.6 Test: Task saving works
- [ ] 5.7 Test: Task retrieval works
- [ ] 5.8 Test: Message flattening works correctly

### Step 6: API DTOs (1-2 hours)
- [x] 6.1 Create `task_requests.py` with `SaveTaskRequest`
- [x] 6.2 Add field aliases for camelCase conversion
- [x] 6.3 Add validators for required fields
- [x] 6.4 Create `task_responses.py` with `TaskResponse`
- [x] 6.5 Create `TaskListResponse`
- [ ] 6.6 Test: DTOs validate correctly
- [ ] 6.7 Test: Serialization/deserialization works
- [ ] 6.8 Test: Field aliases work

### Step 7: API Endpoints (3-4 hours)
- [x] 7.1 Add `POST /sessions/{session_id}/tasks` endpoint
- [x] 7.2 Implement request parsing and validation
- [x] 7.3 Call `SessionService.save_task()`
- [x] 7.4 Return appropriate status codes (201/200)
- [x] 7.5 Handle errors: 400, 403, 404, 422
- [x] 7.6 Add `GET /sessions/{session_id}/tasks` endpoint
- [x] 7.7 Call `SessionService.get_session_tasks()`
- [x] 7.8 Return `TaskListResponse`
- [x] 7.9 Modify `GET /sessions/{session_id}/messages` endpoint
- [x] 7.10 Call `get_session_messages_from_tasks()` internally
- [x] 7.11 Keep same response format
- [ ] 7.12 Test: Can save tasks via API
- [ ] 7.13 Test: Can retrieve tasks via API
- [ ] 7.14 Test: Authorization works (403 for wrong user)
- [ ] 7.15 Test: Backward compatibility maintained

### Step 8: Feedback Service (1-2 hours)
- [x] 8.1 Modify `process_feedback()` in `FeedbackService`
- [x] 8.2 After saving to feedback table, load task
- [x] 8.3 Update `task_metadata.feedback` if task exists
- [x] 8.4 Save updated task via repository
- [x] 8.5 Handle errors gracefully (log but don't fail)
- [ ] 8.6 Test: Feedback saves to feedback table
- [ ] 8.7 Test: Task metadata is updated
- [ ] 8.8 Test: Missing task doesn't break submission

---

## Frontend Implementation

### Step 9: Helper Functions (2-3 hours)
- [x] 9.1 Create `serializeMessageBubble(message: MessageFE)` in `ChatProvider.tsx`
- [x] 9.2 Extract text from parts array
- [x] 9.3 Convert File objects to {name, type}
- [x] 9.4 Include all optional fields
- [x] 9.5 Create `saveTaskToBackend(taskData)` function
- [x] 9.6 Use `authenticatedFetch` to POST
- [x] 9.7 Handle errors gracefully (log only, no notifications)
- [x] 9.8 Create `deserializeTaskToMessages(task)` function
- [x] 9.9 Convert each bubble to MessageFE
- [x] 9.10 Reconstruct parts array
- [x] 9.11 Set isComplete: true
- [x] 9.12 Create `loadSessionTasks(sessionId)` function
- [x] 9.13 Fetch tasks from API
- [x] 9.14 Deserialize to messages
- [x] 9.15 Extract feedback state
- [x] 9.16 Update state
- [ ] 9.17 Test: Serialization preserves all data
- [ ] 9.18 Test: Deserialization recreates messages correctly

### Step 10: Message Saving Logic (2-3 hours)
- [x] 10.1 Update `handleSubmit()` for user messages
- [x] 10.2 After receiving taskId, call `saveTaskToBackend()`
- [x] 10.3 Save initial task data with user message
- [x] 10.4 Don't wait for save completion
- [x] 10.5 Update `handleSseMessage()` for agent messages
- [x] 10.6 When `isFinalEvent` is true, gather all messages
- [x] 10.7 Filter out status bubbles (`isStatusBubble === true`)
- [x] 10.8 Serialize messages to MessageBubble format
- [x] 10.9 Call `saveTaskToBackend()` with complete data
- [ ] 10.10 Test: User messages saved after submission
- [ ] 10.11 Test: Agent messages saved when complete
- [ ] 10.12 Test: Status bubbles filtered out
- [ ] 10.13 Test: All data preserved

### Step 11: Session Loading Logic (1-2 hours)
- [x] 11.1 Update `handleSwitchSession()` in `ChatProvider.tsx`
- [x] 11.2 Replace `getHistory()` call with `loadSessionTasks()`
- [x] 11.3 Use new deserialization logic
- [x] 11.4 Update state with messages and feedback
- [x] 11.5 Verify `handleNewSession()` needs no changes
- [ ] 11.6 Test: Session history loads correctly
- [ ] 11.7 Test: Messages in correct order
- [ ] 11.8 Test: Feedback state restored
- [ ] 11.9 Test: Files and artifacts display

### Step 12: Feedback Verification (30 minutes)
- [x] 12.1 Verify `handleFeedbackSubmit()` still works
- [x] 12.2 Confirm backend handles task metadata update
- [ ] 12.3 Test: Feedback submission works
- [ ] 12.4 Test: Task metadata updated in database
- [ ] 12.5 Test: UI reflects feedback state

---

## Cleanup

### Step 13: Remove Old Backend Logic (1 hour)
- [ ] 13.1 Locate agent message saving code in `component.py`
- [ ] 13.2 Remove section that saves final agent response
- [ ] 13.3 Keep SSE sending logic intact
- [ ] 13.4 Add comment explaining frontend handles persistence
- [ ] 13.5 Test: Backend no longer saves agent messages
- [ ] 13.6 Test: SSE functionality still works
- [ ] 13.7 Test: No errors in logs

### Step 14: Documentation (1 hour)
- [ ] 14.1 Document new API endpoints
- [ ] 14.2 Add request/response examples
- [ ] 14.3 Note backward compatibility for /messages endpoint
- [ ] 14.4 Update README if applicable
- [ ] 14.5 Update CHANGELOG with feature addition
- [ ] 14.6 Add setup instructions if needed
- [ ] 14.7 Run linters and formatters
- [ ] 14.8 Fix any warnings

---

## Final Validation

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

## Estimated Timeline

- **Backend (Steps 1-8):** 12-16 hours
- **Frontend (Steps 9-12):** 6-8 hours
- **Cleanup (Steps 13-14):** 2 hours
- **Total:** 20-26 hours (3-4 days for single developer)

---

## Notes

- Complete backend before starting frontend
- Validate each step before proceeding
- Keep old code until new system is proven stable
- Test thoroughly at each integration point
