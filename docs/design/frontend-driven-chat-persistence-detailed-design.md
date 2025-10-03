# Detailed Design: Frontend-Driven Chat Persistence

## Document Information

- **Feature**: Frontend-Driven Chat Persistence
- **Version**: 1.0
- **Date**: 2025-01-02
- **Status**: Design Review
- **Related Documents**: 
  - [Feature Specification](../features/frontend-driven-chat-persistence.md)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Model Design](#data-model-design)
3. [API Design](#api-design)
4. [Frontend Design](#frontend-design)
5. [Backend Design](#backend-design)
6. [Data Flow](#data-flow)
7. [Error Handling](#error-handling)
8. [Security Considerations](#security-considerations)
9. [Performance Considerations](#performance-considerations)

---

## 1. Architecture Overview

### 1.1 Current Architecture Problems

The current system has the backend attempting to infer what the user saw by parsing A2A protocol messages and saving them to the `chat_messages` table. This creates several issues:

- **State Mismatch**: Backend saves raw A2A responses, but frontend displays resolved embeds, accumulated streaming text, and UI-specific state
- **Lost Context**: Feedback is stored separately from messages, making it difficult to reconstruct the exact user experience
- **Complex Backend Logic**: Backend contains complex A2A protocol parsing logic that shouldn't be in the persistence layer
- **Inaccurate Replay**: Loading a session doesn't show exactly what the user originally saw

### 1.2 New Architecture

The new architecture makes the frontend the authoritative source of truth:

- **Frontend Authority**: Frontend knows exactly what was displayed and saves that state
- **Backend Simplicity**: Backend becomes a simple storage layer with no A2A protocol knowledge
- **Task-Based Model**: Store complete task interactions (user input + agent response) as atomic units
- **Integrated State**: All UI state (feedback, files, notifications) stored together

**Key Principle**: The chat UI is the source of truth for chat history, not the A2A protocol messages.

---

## 2. Data Model Design

### 2.1 Database Schema Changes

#### 2.1.1 New Table: `chat_tasks`

Replace the existing `chat_messages` table with a new `chat_tasks` table that stores complete task interactions.

**Columns:**
- `id` (VARCHAR, PRIMARY KEY): The A2A taskId (e.g., "gdk-task-abc123")
- `session_id` (VARCHAR, FOREIGN KEY → sessions.id, ON DELETE CASCADE): Links to session
- `user_id` (VARCHAR, NOT NULL): User who owns this task
- `user_message` (TEXT, NULLABLE): Original user input text (for search/display)
- `message_bubbles` (JSON, NOT NULL): Array of all message bubbles displayed during this task
- `task_metadata` (JSON, NULLABLE): Task-level information (status, feedback, agent name, etc.)
- `created_time` (BIGINT, NOT NULL): When task was created
- `updated_time` (BIGINT, NULLABLE): When task was last updated

**Indexes:**
- Primary key on `id`
- Index on `session_id` (for loading session history)
- Index on `user_id` (for user-specific queries)
- Index on `created_time` (for chronological ordering)

**Foreign Key Constraints:**
- `session_id` references `sessions(id)` with CASCADE delete (when session is deleted, all its tasks are deleted)

#### 2.1.2 JSON Structure: `message_bubbles`

This field stores an array of message bubble objects. Each bubble represents one visual element in the chat window.

**Bubble Structure:**
```
{
  "id": string,              // Frontend-generated messageId
  "type": "user" | "agent" | "artifact_notification",
  "text": string,            // Combined text from all text parts (optional)
  "parts": Part[],           // Full A2A Part objects for reconstruction (optional)
  "files": FileAttachment[], // Agent-returned files (optional)
  "uploadedFiles": [{        // User-uploaded files (optional)
    "name": string,
    "type": string
  }],
  "artifactNotification": {  // Artifact creation notice (optional)
    "name": string,
    "version": number
  },
  "isError": boolean         // Error styling flag (optional)
}
```

**Design Rationale:**
- Store both `text` (for quick display) and `parts` (for full reconstruction)
- Include all file attachments inline (base64 content or URIs)
- Capture artifact notifications as they appeared
- Flag error messages for proper styling

#### 2.1.3 JSON Structure: `task_metadata`

This field stores task-level information that applies to the entire interaction.

**Metadata Structure:**
```
{
  "status": "completed" | "error" | "cancelled",
  "feedback": {              // Optional
    "type": "up" | "down",
    "text": string,
    "submitted": boolean
  },
  "agent_name": string,      // Optional
  "duration_ms": number,     // Optional, for future analytics
  "token_count": number      // Optional, for future analytics
}
```

**Design Rationale:**
- Store task outcome (completed, error, cancelled)
- Integrate feedback directly with the task
- Include agent name for filtering/display
- Reserve space for future analytics data

### 2.2 Domain Entity

Create a new `ChatTask` domain entity in `src/solace_agent_mesh/gateway/http_sse/repository/entities/chat_task.py`.

**Responsibilities:**
- Represent a complete task interaction in the domain layer
- Provide business logic methods (e.g., `add_feedback()`, `get_feedback()`)
- Validate task data structure
- Convert to/from SQLAlchemy models

**Key Methods:**
- `add_feedback(type, text)`: Add or update feedback for this task
- `get_feedback()`: Retrieve feedback if present
- `validate()`: Ensure message_bubbles is valid JSON array

### 2.3 SQLAlchemy Model

Create a new `ChatTaskModel` in `src/solace_agent_mesh/gateway/http_sse/repository/models/chat_task_model.py`.

**Responsibilities:**
- Map to the `chat_tasks` database table
- Handle JSON serialization/deserialization for `message_bubbles` and `task_metadata`
- Define foreign key relationships

### 2.4 Migration Strategy

Create an Alembic migration to:
1. Create the new `chat_tasks` table with all columns and indexes
2. Keep the old `chat_messages` table temporarily (don't drop it yet)
3. Add a comment noting that `chat_messages` is deprecated

**Migration File Location:** `src/solace_agent_mesh/gateway/http_sse/alembic/versions/YYYYMMDD_create_chat_tasks_table.py`

**Note:** We are NOT migrating existing data since this feature hasn't been rolled out yet (per requirement #13).

---

## 3. API Design

### 3.1 New Endpoint: Save Task

**Purpose:** Save a complete task interaction with upsert semantics (create if new, update if exists).

**Endpoint:** `POST /api/v1/sessions/{session_id}/tasks`

**Authentication:** Required (user must own the session)

**Request Body:**
```typescript
{
  "task_id": string,              // Required: A2A taskId
  "user_message": string,         // Optional: Original user input
  "message_bubbles": Array<{      // Required: All bubbles shown
    "id": string,
    "type": "user" | "agent" | "artifact_notification",
    "text": string,
    "parts": Part[],
    "files": FileAttachment[],
    "uploadedFiles": Array<{name: string, type: string}>,
    "artifactNotification": {name: string, version: number},
    "isError": boolean
  }>,
  "task_metadata": {              // Optional: Task-level info
    "status": "completed" | "error" | "cancelled",
    "feedback": {
      "type": "up" | "down",
      "text": string,
      "submitted": boolean
    },
    "agent_name": string
  }
}
```

**Response (200 OK or 201 Created):**
```typescript
{
  "task_id": string,
  "session_id": string,
  "created_time": number,
  "updated_time": number
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request data (malformed JSON, missing required fields)
- `403 Forbidden`: User doesn't own this session
- `404 Not Found`: Session doesn't exist
- `422 Unprocessable Entity`: Validation error (e.g., empty message_bubbles array)

**Validation Rules:**
- `task_id` must be a non-empty string
- `message_bubbles` must be a non-empty array
- Each bubble must have an `id` and `type`
- `session_id` in URL must match an existing session owned by the authenticated user

**Idempotency:** This endpoint is idempotent. Calling it multiple times with the same `task_id` will update the existing task rather than creating duplicates.

### 3.2 New Endpoint: Get Session Tasks

**Purpose:** Load all tasks for a session to reconstruct the chat history.

**Endpoint:** `GET /api/v1/sessions/{session_id}/tasks`

**Authentication:** Required (user must own the session)

**Query Parameters:** None (returns all tasks for the session)

**Response (200 OK):**
```typescript
{
  "tasks": Array<{
    "task_id": string,
    "user_message": string,
    "message_bubbles": Array<MessageBubble>,
    "task_metadata": TaskMetadata,
    "created_time": number,
    "updated_time": number
  }>
}
```

**Error Responses:**
- `403 Forbidden`: User doesn't own this session
- `404 Not Found`: Session doesn't exist

**Ordering:** Tasks are returned in chronological order (oldest first) based on `created_time`.

### 3.3 Modified Endpoint: Get Session Messages (Backward Compatibility)

**Purpose:** Maintain backward compatibility by keeping the existing endpoint but populating it from tasks.

**Endpoint:** `GET /api/v1/sessions/{session_id}/messages`

**Behavior Change:**
- Previously: Loaded from `chat_messages` table
- Now: Loads from `chat_tasks` table and flattens `message_bubbles` into individual `MessageResponse` objects

**Response Format:** Unchanged (still returns `MessageResponse[]`)

**Implementation Strategy:**
1. Load all tasks for the session
2. Iterate through each task's `message_bubbles`
3. Convert each bubble to a `MessageResponse` object
4. Return flattened list in chronological order

**Note:** This endpoint is maintained for backward compatibility but the new `/tasks` endpoint is preferred.

### 3.4 Modified Behavior: Submit Feedback

**Endpoint:** `POST /api/v1/feedback` (unchanged)

**New Behavior:** In addition to saving to the `feedback` table, also update the corresponding task's `task_metadata`.

**Implementation:**
1. Save feedback to `feedback` table (existing behavior)
2. Load the task from `chat_tasks` using `task_id`
3. Update `task_metadata.feedback` with the new feedback
4. Save the updated task back to `chat_tasks`

**Error Handling:** If updating the task fails, log a warning but don't fail the feedback submission (feedback table is still updated).

---

## 4. Frontend Design

### 4.1 Save Timing Strategy

#### 4.1.1 User Messages

**When to Save:** Immediately after successful A2A request submission

**Location:** `ChatProvider.tsx` in the `handleSubmit()` function

**What to Save:**
- The user's input text
- Any uploaded files (names and types, not full content)
- Initial task metadata with status "pending"

**Rationale:** Save as soon as we have a taskId to ensure we capture the user's intent even if the agent response fails.

#### 4.1.2 Agent Messages

**When to Save:** When the task completes (final event, error, or cancellation)

**Location:** `ChatProvider.tsx` in the `handleSseMessage()` function when `isFinalEvent` is true

**What to Save:**
- All message bubbles for this task (user + agent)
- All file attachments
- All artifact notifications
- Final task metadata with status "completed", "error", or "cancelled"
- Overwrite the initial user message save with the complete task data

**Rationale:** Wait until the task is complete to capture the full interaction in one atomic save.

#### 4.1.3 Feedback Updates

**When to Save:** When user submits feedback

**Location:** `ChatProvider.tsx` in the `handleFeedbackSubmit()` function

**What to Save:**
- Call the existing feedback API (which will update both tables)
- Update local state to reflect the feedback

**Rationale:** Feedback can be added after the task is complete, so we need to support updates.

### 4.2 Helper Functions Needed

#### 4.2.1 `serializeMessageBubble(message: MessageFE): MessageBubble`

**Purpose:** Convert a frontend `MessageFE` object to the backend `MessageBubble` format.

**Key Transformations:**
- Extract text from `parts` array
- Include full `parts` array for reconstruction
- Convert `File` objects to `{name, type}` objects
- Include all optional fields (files, artifactNotification, isError)

#### 4.2.2 `saveTaskToBackend(taskData: SaveTaskRequest): Promise<void>`

**Purpose:** Send task data to the backend API.

**Behavior:**
- Use `authenticatedFetch` to POST to `/api/v1/sessions/{sessionId}/tasks`
- Handle errors gracefully (log but don't throw)
- Return silently on success

**Error Handling:** If save fails, log the error but don't show UI notification (silent background operation per NFR-1).

#### 4.2.3 `deserializeTaskToMessages(task: TaskData): MessageFE[]`

**Purpose:** Convert backend task data back to frontend `MessageFE` objects.

**Key Transformations:**
- Create one `MessageFE` per bubble in `message_bubbles`
- Reconstruct `parts` array from stored data
- Set `isComplete: true` for all messages
- Populate `metadata` with `messageId` from bubble `id`

#### 4.2.4 `loadSessionTasks(sessionId: string): Promise<void>`

**Purpose:** Load all tasks for a session and reconstruct the message list.

**Behavior:**
1. Fetch tasks from `/api/v1/sessions/{sessionId}/tasks`
2. Deserialize each task to messages
3. Flatten into a single message array
4. Extract feedback state from task metadata
5. Update `messages` and `submittedFeedback` state

### 4.3 State Management Changes

#### 4.3.1 No New State Variables Needed

The existing state variables in `ChatProvider` are sufficient:
- `messages: MessageFE[]` - continues to hold all messages
- `submittedFeedback: Record<string, FeedbackState>` - continues to hold feedback state
- `sessionId: string` - continues to identify the current session

#### 4.3.2 Modified State Update Logic

**In `handleSubmit()`:**
- After getting taskId, call `saveTaskToBackend()` with initial user message
- Continue with existing logic

**In `handleSseMessage()`:**
- When `isFinalEvent` is true, gather all messages for the task
- Call `saveTaskToBackend()` with complete task data
- Continue with existing logic

**In `handleSwitchSession()`:**
- Replace `getHistory()` call with `loadSessionTasks()`
- Use new deserialization logic

**In `handleFeedbackSubmit()`:**
- Keep existing logic (backend will handle task update)

### 4.4 Filtering Logic

**Status Bubbles:** Must NOT be saved to the backend.

**Implementation:** When gathering messages for a task, filter out any message where `isStatusBubble === true`.

**Location:** In the `handleSseMessage()` function before calling `saveTaskToBackend()`.

---

## 5. Backend Design

### 5.1 Repository Layer

#### 5.1.1 New Repository: `ChatTaskRepository`

**File:** `src/solace_agent_mesh/gateway/http_sse/repository/chat_task_repository.py`

**Responsibilities:**
- CRUD operations for `chat_tasks` table
- Convert between SQLAlchemy models and domain entities
- Handle JSON serialization/deserialization

**Key Methods:**
- `save(task: ChatTask) -> ChatTask`: Upsert a task (create or update)
- `find_by_session(session_id: str, user_id: str) -> List[ChatTask]`: Get all tasks for a session
- `find_by_id(task_id: str, user_id: str) -> Optional[ChatTask]`: Get a specific task
- `delete_by_session(session_id: str) -> bool`: Delete all tasks for a session (for cascade delete)

**Upsert Logic:**
- Check if task with given `id` exists
- If exists: Update `message_bubbles`, `task_metadata`, and `updated_time`
- If not exists: Insert new record with all fields
- Always commit and return the saved entity

#### 5.1.2 Update to `SessionRepository`

**No changes needed.** The existing `SessionRepository` handles session CRUD operations. The CASCADE delete on the foreign key will automatically delete tasks when a session is deleted.

### 5.2 Service Layer

#### 5.2.1 Update `SessionService`

**File:** `src/solace_agent_mesh/gateway/http_sse/services/session_service.py`

**New Methods:**

**`save_task()`:**
- Validate session exists and belongs to user
- Create `ChatTask` entity from parameters
- Call `ChatTaskRepository.save()`
- Update session's `updated_time` (mark activity)
- Return saved task

**`get_session_tasks()`:**
- Validate session exists and belongs to user
- Call `ChatTaskRepository.find_by_session()`
- Return list of tasks in chronological order

**`get_session_messages_from_tasks()`:**
- Load tasks using `get_session_tasks()`
- Flatten `message_bubbles` from all tasks
- Convert to `Message` entities for backward compatibility
- Return list of messages

**Validation Logic:**
- Ensure `message_bubbles` is a non-empty array
- Ensure each bubble has required fields (`id`, `type`)
- Ensure `session_id` matches an existing session
- Ensure user owns the session

#### 5.2.2 Update `FeedbackService`

**File:** `src/solace_agent_mesh/gateway/http_sse/services/feedback_service.py`

**Modified Method: `process_feedback()`**

**New Behavior:**
1. Save feedback to `feedback` table (existing logic)
2. Load the task from `chat_tasks` using `task_id`
3. If task exists:
   - Update `task_metadata.feedback` with new feedback data
   - Call `ChatTaskRepository.save()` to persist
4. If task doesn't exist:
   - Log a warning (this shouldn't happen in normal flow)
   - Continue (feedback table is still updated)

**Error Handling:** If task update fails, log error but don't fail the feedback submission.

### 5.3 Router Layer

#### 5.3.1 New Router Endpoints

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/sessions.py`

**New Endpoint: `POST /sessions/{session_id}/tasks`**

**Handler Function:** `save_task()`

**Implementation:**
1. Extract `session_id` from path
2. Get authenticated `user_id` from dependencies
3. Parse request body into a Pydantic model
4. Validate request data
5. Call `SessionService.save_task()`
6. Return success response with task details
7. Handle errors (403, 404, 422)

**New Endpoint: `GET /sessions/{session_id}/tasks`**

**Handler Function:** `get_session_tasks()`

**Implementation:**
1. Extract `session_id` from path
2. Get authenticated `user_id` from dependencies
3. Call `SessionService.get_session_tasks()`
4. Convert tasks to response DTOs
5. Return list of tasks
6. Handle errors (403, 404)

#### 5.3.2 Modified Router Endpoint

**Endpoint: `GET /sessions/{session_id}/messages`**

**Handler Function:** `get_session_history()`

**Modified Implementation:**
1. Keep the same signature and response format
2. Change internal logic to call `SessionService.get_session_messages_from_tasks()`
3. Convert task-based messages to `MessageResponse` DTOs
4. Return in the same format as before (backward compatibility)

### 5.4 DTO Layer

#### 5.4.1 New Request DTO

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/dto/requests/task_requests.py`

**`SaveTaskRequest`:**
- Pydantic model for the save task request body
- Validates required fields
- Handles JSON deserialization for `message_bubbles` and `task_metadata`

#### 5.4.2 New Response DTOs

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/task_responses.py`

**`TaskResponse`:**
- Pydantic model for a single task
- Includes all task fields
- Handles JSON serialization

**`TaskListResponse`:**
- Pydantic model for list of tasks
- Contains array of `TaskResponse` objects

---

## 6. Data Flow

### 6.1 User Sends Message Flow

```
1. User types message and clicks send
   ↓
2. Frontend: handleSubmit() called
   ↓
3. Frontend: Submit A2A request to backend
   ↓
4. Backend: Returns taskId
   ↓
5. Frontend: Save initial task with user message
   POST /api/v1/sessions/{sessionId}/tasks
   {
     task_id: "gdk-task-123",
     user_message: "Hello",
     message_bubbles: [{id: "msg-1", type: "user", text: "Hello"}],
     task_metadata: {status: "pending", agent_name: "assistant"}
   }
   ↓
6. Backend: SessionService.save_task()
   ↓
7. Backend: ChatTaskRepository.save() (creates new task)
   ↓
8. Backend: Returns 201 Created
   ↓
9. Frontend: Continues with SSE connection
```

### 6.2 Agent Response Complete Flow

```
1. Frontend: Receives final SSE event (isFinalEvent = true)
   ↓
2. Frontend: Gathers all messages for this taskId
   - Filters out status bubbles
   - Includes user message, agent messages, files, notifications
   ↓
3. Frontend: Serializes messages to MessageBubble format
   ↓
4. Frontend: Save complete task
   POST /api/v1/sessions/{sessionId}/tasks
   {
     task_id: "gdk-task-123",
     user_message: "Hello",
     message_bubbles: [
       {id: "msg-1", type: "user", text: "Hello"},
       {id: "msg-2", type: "agent", text: "Hi there!", parts: [...]}
     ],
     task_metadata: {status: "completed", agent_name: "assistant"}
   }
   ↓
5. Backend: SessionService.save_task()
   ↓
6. Backend: ChatTaskRepository.save() (updates existing task)
   ↓
7. Backend: Returns 200 OK
   ↓
8. Frontend: Task saved successfully (silent)
```

### 6.3 Load Session History Flow

```
1. User switches to a different session
   ↓
2. Frontend: handleSwitchSession() called
   ↓
3. Frontend: Load tasks for session
   GET /api/v1/sessions/{sessionId}/tasks
   ↓
4. Backend: SessionService.get_session_tasks()
   ↓
5. Backend: ChatTaskRepository.find_by_session()
   ↓
6. Backend: Returns list of tasks with all message_bubbles
   ↓
7. Frontend: Deserialize tasks to MessageFE objects
   - For each task, for each bubble, create a MessageFE
   - Extract feedback from task_metadata
   ↓
8. Frontend: Update state
   - setMessages(allMessages)
   - setSubmittedFeedback(feedbackMap)
   ↓
9. Frontend: Chat window displays exact history
```

### 6.4 Submit Feedback Flow

```
1. User clicks thumbs up/down
   ↓
2. Frontend: handleFeedbackSubmit() called
   ↓
3. Frontend: Submit feedback
   POST /api/v1/feedback
   {taskId: "gdk-task-123", feedbackType: "up", feedbackText: "Great!"}
   ↓
4. Backend: FeedbackService.process_feedback()
   ↓
5. Backend: Save to feedback table (existing logic)
   ↓
6. Backend: Load task from chat_tasks
   ↓
7. Backend: Update task_metadata.feedback
   ↓
8. Backend: ChatTaskRepository.save() (updates task)
   ↓
9. Backend: Returns 202 Accepted
   ↓
10. Frontend: Update local feedback state
    setSubmittedFeedback({...prev, [taskId]: {type: "up", text: "Great!"}})
```

---

## 7. Error Handling

### 7.1 Frontend Error Handling

#### 7.1.1 Save Failures

**Scenario:** Network error or backend unavailable when saving task

**Handling:**
- Log error to console
- Do NOT show user notification (silent background operation per NFR-1)
- Do NOT retry automatically (accept data loss per FR-9)
- Continue normal operation

**Rationale:** Saving is best-effort. The user's immediate experience (seeing messages) is more important than persistence.

#### 7.1.2 Load Failures

**Scenario:** Error loading session history

**Handling:**
- Show user notification: "Error loading session history"
- Log error to console
- Leave messages array empty or show welcome message
- Allow user to retry by switching sessions again

**Rationale:** Loading failures are user-visible and should be communicated.

#### 7.1.3 Validation Errors

**Scenario:** Backend returns 422 validation error

**Handling:**
- Log error with full details
- Do NOT show user notification
- Continue normal operation

**Rationale:** Validation errors indicate a bug in the frontend serialization logic, not a user error.

### 7.2 Backend Error Handling

#### 7.2.1 Invalid Request Data

**Scenario:** Request body is malformed or missing required fields

**Response:** 400 Bad Request with error details

**Example:**
```json
{
  "detail": "Invalid request: message_bubbles is required"
}
```

#### 7.2.2 Authorization Failures

**Scenario:** User tries to access/modify a session they don't own

**Response:** 403 Forbidden

**Example:**
```json
{
  "detail": "You do not have permission to access this session"
}
```

#### 7.2.3 Resource Not Found

**Scenario:** Session doesn't exist

**Response:** 404 Not Found

**Example:**
```json
{
  "detail": "Session not found"
}
```

#### 7.2.4 Validation Errors

**Scenario:** Data passes schema validation but fails business rules

**Response:** 422 Unprocessable Entity

**Example:**
```json
{
  "detail": "message_bubbles cannot be empty"
}
```

#### 7.2.5 Database Errors

**Scenario:** Database connection fails or query errors

**Response:** 500 Internal Server Error

**Logging:** Log full error with stack trace

**User Message:** Generic error message (don't expose internal details)

### 7.3 Partial Failure Handling

#### 7.3.1 Feedback Update Fails

**Scenario:** Feedback saves to `feedback` table but task update fails

**Handling:**
- Log warning
- Return success to user (feedback table is updated)
- Task metadata will be inconsistent but not critical

**Rationale:** Feedback table is the source of truth for feedback; task metadata is supplementary.

---

## 8. Security Considerations

### 8.1 Authorization

**Requirement:** Users can only save/load tasks for sessions they own.

**Implementation:**
- All endpoints require authentication (via `get_user_id` dependency)
- All endpoints validate session ownership before operations
- Use `user_id` from authenticated session, not from request body

**Validation Points:**
1. `save_task()`: Verify session belongs to authenticated user
2. `get_session_tasks()`: Verify session belongs to authenticated user
3. Database queries: Always include `user_id` in WHERE clause

### 8.2 Data Validation

**Input Validation:**
- Validate all request bodies with Pydantic models
- Sanitize user input (though stored as-is for accurate replay)
- Limit JSON field sizes to prevent DoS

**Size Limits:**
- `message_bubbles`: Max 100 bubbles per task (reasonable limit)
- `user_message`: Max 10,000 characters
- Individual bubble `text`: Max 100,000 characters
- Total JSON size: Max 10MB per task

**Validation Rules:**
- `task_id` must be non-empty string
- `message_bubbles` must be non-empty array
- Each bubble must have `id` and `type`
- `type` must be one of: "user", "agent", "artifact_notification"

### 8.3 SQL Injection Prevention

**Protection:** Use SQLAlchemy ORM for all database operations (parameterized queries).

**Never:** Concatenate user input into SQL strings.

### 8.4 XSS Prevention

**Frontend:** Use React's built-in XSS protection (JSX escaping).

**Backend:** Store data as-is; don't sanitize (we want exact replay).

**Rendering:** Frontend's `MarkdownHTMLConverter` should sanitize HTML output.

---

## 9. Performance Considerations

### 9.1 Database Performance

#### 9.1.1 Query Optimization

**Indexes:**
- `session_id`: For loading all tasks in a session (most common query)
- `user_id`: For user-specific queries
- `created_time`: For chronological ordering

**Query Patterns:**
- Load session tasks: `SELECT * FROM chat_tasks WHERE session_id = ? AND user_id = ? ORDER BY created_time ASC`
- Upsert task: `SELECT * FROM chat_tasks WHERE id = ?` then INSERT or UPDATE

#### 9.1.2 JSON Field Performance

**Consideration:** JSON fields are less efficient than normalized tables.

**Mitigation:**
- Modern databases (PostgreSQL, SQLite 3.38+) have good JSON support
- We're not querying inside JSON fields (only loading/storing)
- The flexibility benefit outweighs the performance cost

**Monitoring:** Track query performance and JSON field sizes.

#### 9.1.3 Cascade Deletes

**Behavior:** When a session is deleted, all its tasks are automatically deleted (CASCADE).

**Performance:** For sessions with many tasks, this could be slow.

**Mitigation:** 
- Acceptable for now (sessions typically have < 100 tasks)
- If needed later, implement batch deletion

### 9.2 Network Performance

#### 9.2.1 Payload Sizes

**Concern:** `message_bubbles` JSON can be large (especially with base64 files).

**Mitigation:**
- Frontend already handles large payloads (streaming responses)
- HTTP compression (gzip) reduces transfer size
- Consider size limits (10MB per task)

**Monitoring:** Log payload sizes for large tasks.

#### 9.2.2 Request Frequency

**Pattern:** One save per task (not per message bubble).

**Impact:** Minimal - typical session has 10-50 tasks.

**Optimization:** No batching needed at this scale.

### 9.3 Frontend Performance

#### 9.3.1 State Updates

**Concern:** Deserializing many tasks could be slow.

**Mitigation:**
- Typical session has < 100 tasks
- Deserialization is simple (no complex transformations)
- React handles re-renders efficiently

**Optimization:** If needed, implement pagination for very long sessions.

#### 9.3.2 Memory Usage

**Concern:** Storing full message history in memory.

**Mitigation:**
- Already done in current implementation
- Typical session uses < 10MB of memory
- Browser memory limits are much higher

### 9.4 Scalability Considerations

**Current Scale:** Single-user sessions, < 100 tasks per session.

**Future Scale:** If sessions grow to 1000+ tasks:
- Implement pagination for loading history
- Consider archiving old tasks
- Add indexes on additional fields

**Database Growth:** With 1000 users, 100 sessions each, 50 tasks per session:
- 5 million task records
- ~50GB storage (assuming 10KB average per task)
- Well within database capabilities

---

## 10. Testing Strategy

### 10.1 Unit Tests

#### 10.1.1 Frontend Unit Tests

**Test `serializeMessageBubble()`:**
- Converts MessageFE to MessageBubble correctly
- Handles all optional fields
- Filters out undefined values

**Test `deserializeTaskToMessages()`:**
- Converts task data to MessageFE array
- Reconstructs parts correctly
- Handles missing optional fields

**Test `saveTaskToBackend()`:**
- Calls correct API endpoint
- Sends correct payload
- Handles errors gracefully

#### 10.1.2 Backend Unit Tests

**Test `ChatTaskRepository`:**
- `save()` creates new task
- `save()` updates existing task
- `find_by_session()` returns tasks in order
- `find_by_id()` returns correct task
- Authorization checks work

**Test `SessionService`:**
- `save_task()` validates session ownership
- `get_session_tasks()` returns correct tasks
- `get_session_messages_from_tasks()` flattens correctly

**Test `FeedbackService`:**
- `process_feedback()` updates task metadata
- Handles missing task gracefully

### 10.2 Integration Tests

#### 10.2.1 API Integration Tests

**Test Save Task Flow:**
1. Create session
2. Save task with user message
3. Verify task is created
4. Update task with agent response
5. Verify task is updated

**Test Load Tasks Flow:**
1. Create session with multiple tasks
2. Load tasks via API
3. Verify all tasks returned
4. Verify correct order

**Test Feedback Flow:**
1. Create session with task
2. Submit feedback
3. Verify feedback table updated
4. Verify task metadata updated

#### 10.2.2 End-to-End Tests

**Test Complete Conversation:**
1. User sends message
2. Agent responds
3. Verify task saved
4. User submits feedback
5. Verify feedback saved
6. Load session
7. Verify exact history displayed

**Test Session Switch:**
1. Create two sessions with tasks
2. Switch between sessions
3. Verify correct history loaded each time

**Test Error Scenarios:**
1. Network failure during save
2. Invalid session ID
3. Unauthorized access
4. Malformed request data

### 10.3 Manual Testing

**Test Scenarios:**
1. Send message with file attachments
2. Receive response with multiple bubbles
3. Receive artifact notification
4. Submit feedback
5. Switch sessions
6. Verify exact replay

**Visual Verification:**
- Messages appear in correct order
- Files display correctly
- Artifact notifications show
- Feedback state persists
- Error messages styled correctly

---

## 11. Open Questions

### 11.1 Resolved Questions

1. **Should we migrate existing data?** No - feature hasn't been rolled out yet.
2. **Should we keep backward compatibility?** Yes - keep `/messages` endpoint but populate from tasks.
3. **Should we save status bubbles?** No - they are transient UI state.
4. **Should we save failed submissions?** No - user will retry.

### 11.2 Questions for Discussion

1. **Size Limits:** What's the maximum reasonable size for a task? (Proposed: 10MB)
2. **Pagination:** Should we implement pagination for loading tasks? (Proposed: Not initially)
3. **Archiving:** Should old tasks be archived after N days? (Proposed: Not initially)
4. **Analytics:** Should we track task-level metrics (duration, tokens)? (Proposed: Add fields but don't populate yet)

---

## 12. Success Metrics

### 12.1 Functional Success

- [ ] Users can send messages and see them saved
- [ ] Users can switch sessions and see exact history
- [ ] Feedback persists across sessions
- [ ] File attachments display correctly
- [ ] Artifact notifications appear
- [ ] Error messages styled correctly

### 12.2 Technical Success

- [ ] One database write per task (not per bubble)
- [ ] Backend has no A2A protocol parsing logic
- [ ] Frontend is source of truth for displayed content
- [ ] Session replay is pixel-perfect match

### 12.3 Performance Success

- [ ] Save operations complete in < 500ms
- [ ] Load operations complete in < 1s for 50-task sessions
- [ ] No user-visible delays or errors
- [ ] Database queries use indexes efficiently

---

## Appendix A: Example Data Structures

### A.1 Example Task Record

```json
{
  "id": "gdk-task-abc123",
  "session_id": "web-session-xyz789",
  "user_id": "user@example.com",
  "user_message": "Can you analyze this sales data?",
  "message_bubbles": [
    {
      "id": "msg-user-001",
      "type": "user",
      "text": "Can you analyze this sales data?",
      "uploadedFiles": [
        {"name": "sales_q4.csv", "type": "text/csv"}
      ]
    },
    {
      "id": "msg-agent-001",
      "type": "agent",
      "text": "I'll analyze the sales data for you. Let me process the CSV file...",
      "parts": [
        {"kind": "text", "text": "I'll analyze the sales data for you. Let me process the CSV file..."}
      ]
    },
    {
      "id": "msg-agent-002",
      "type": "agent",
      "text": "Here's my analysis:\n\n- Total revenue: $1.2M\n- Top product: Widget A\n- Growth: +15% YoY",
      "parts": [
        {"kind": "text", "text": "Here's my analysis:\n\n- Total revenue: $1.2M\n- Top product: Widget A\n- Growth: +15% YoY"}
      ],
      "files": [
        {
          "name": "analysis_report.pdf",
          "mime_type": "application/pdf",
          "content": "JVBERi0xLjQKJeLjz9MK..."
        }
      ]
    },
    {
      "id": "msg-artifact-001",
      "type": "artifact_notification",
      "artifactNotification": {
        "name": "sales_analysis_q4.pdf",
        "version": 1
      }
    }
  ],
  "task_metadata": {
    "status": "completed",
    "feedback": {
      "type": "up",
      "text": "Very helpful analysis!",
      "submitted": true
    },
    "agent_name": "data_analyst",
    "duration_ms": 8420
  },
  "created_time": 1704153600000,
  "updated_time": 1704153650000
}
```

### A.2 Example API Request

```http
POST /api/v1/sessions/web-session-xyz789/tasks HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJhbGc...
Content-Type: application/json

{
  "task_id": "gdk-task-abc123",
  "user_message": "Can you analyze this sales data?",
  "message_bubbles": [
    {
      "id": "msg-user-001",
      "type": "user",
      "text": "Can you analyze this sales data?",
      "uploadedFiles": [
        {"name": "sales_q4.csv", "type": "text/csv"}
      ]
    },
    {
      "id": "msg-agent-001",
      "type": "agent",
      "text": "I'll analyze the sales data for you...",
      "parts": [
        {"kind": "text", "text": "I'll analyze the sales data for you..."}
      ]
    }
  ],
  "task_metadata": {
    "status": "completed",
    "agent_name": "data_analyst"
  }
}
```

### A.3 Example API Response

```http
HTTP/1.1 201 Created
Content-Type: application/json

{
  "task_id": "gdk-task-abc123",
  "session_id": "web-session-xyz789",
  "created_time": 1704153600000,
  "updated_time": 1704153600000
}
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-02 | System | Initial detailed design |

---

## Approval

This design requires review and approval from:

- [ ] Frontend Team Lead
- [ ] Backend Team Lead
- [ ] Technical Architect
- [ ] Product Owner
