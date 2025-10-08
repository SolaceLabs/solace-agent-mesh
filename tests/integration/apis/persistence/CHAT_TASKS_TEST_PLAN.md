# Chat Tasks API Test Plan

## Overview
This document describes the test coverage for the new chat tasks endpoints:
- `POST /api/v1/sessions/{session_id}/chat-tasks` - Save/upsert a task
- `GET /api/v1/sessions/{session_id}/chat-tasks` - Get all tasks for a session

## Background
The chat tasks feature introduces a task-centric data model where:
- Each task represents a complete user-agent interaction
- `message_bubbles` stores all UI message bubbles as an opaque JSON string
- `task_metadata` stores task-level information (status, feedback, agent name) as an opaque JSON string
- The backend treats these JSON strings as opaque - no parsing or validation of structure
- The old `/messages` endpoint now derives messages by flattening tasks

## Test File Structure
**File:** `tests/integration/apis/persistence/test_chat_tasks_api.py`

---

## Test Suite 1: Basic CRUD Operations

### Test 1.1: Create New Task
**Purpose:** Verify that a new task can be created via POST

**Steps:**
1. Create a session via `/message:stream`
2. POST a new task to `/sessions/{session_id}/chat-tasks`
3. Verify response status is 201 (Created)
4. Verify response contains all task fields
5. Verify task_id matches request
6. Verify created_time is set
7. Verify updated_time is None (new task)

**Expected Data:**
```json
{
  "task_id": "task-123",
  "session_id": "session-456",
  "user_message": "Hello, I need help",
  "message_bubbles": "[{\"type\":\"user\",\"text\":\"Hello\"},{\"type\":\"agent\",\"text\":\"Hi there\"}]",
  "task_metadata": "{\"status\":\"completed\",\"agent_name\":\"TestAgent\"}"
}
```

### Test 1.2: Retrieve Tasks for Session
**Purpose:** Verify that tasks can be retrieved via GET

**Steps:**
1. Create a session
2. Create 3 tasks via POST
3. GET `/sessions/{session_id}/chat-tasks`
4. Verify response status is 200
5. Verify response contains array of 3 tasks
6. Verify tasks are in chronological order (by created_time)
7. Verify each task has all required fields

### Test 1.3: Update Existing Task (Upsert)
**Purpose:** Verify that POSTing with existing task_id updates the task

**Steps:**
1. Create a session
2. POST a task with task_id "task-123"
3. Verify response status is 201
4. POST again with same task_id but different message_bubbles
5. Verify response status is 200 (not 201)
6. Verify updated_time is now set
7. GET the task and verify message_bubbles was updated
8. Verify created_time remained unchanged

### Test 1.4: Empty Session Returns Empty Array
**Purpose:** Verify that a session with no tasks returns empty array

**Steps:**
1. Create a session
2. GET `/sessions/{session_id}/chat-tasks`
3. Verify response status is 200
4. Verify response is `{"tasks": []}`

---

## Test Suite 2: Data Validation

### Test 2.1: Valid JSON Strings Accepted
**Purpose:** Verify that valid JSON strings are accepted for message_bubbles and task_metadata

**Test Cases:**
- Simple array: `"[{\"type\":\"user\",\"text\":\"Hi\"}]"`
- Complex nested structure: `"[{\"type\":\"agent\",\"parts\":[{\"text\":\"Hello\"}]}]"`
- Empty metadata: `null` or `""`
- Complex metadata: `"{\"status\":\"completed\",\"feedback\":{\"type\":\"up\"}}"`

**Expected:** All should succeed with 201/200 status

### Test 2.2: Invalid JSON in message_bubbles Rejected
**Purpose:** Verify that invalid JSON in message_bubbles is rejected

**Test Cases:**
- Malformed JSON: `"[{invalid json}]"`
- Not a JSON array: `"{\"not\":\"array\"}"`
- Empty string: `""`
- Non-JSON string: `"just plain text"`

**Expected:** 422 Unprocessable Entity with validation error

### Test 2.3: Invalid JSON in task_metadata Rejected
**Purpose:** Verify that invalid JSON in task_metadata is rejected (if not null/empty)

**Test Cases:**
- Malformed JSON: `"{invalid json}"`
- Non-JSON string: `"just plain text"`

**Expected:** 422 Unprocessable Entity with validation error

### Test 2.4: Empty message_bubbles Rejected
**Purpose:** Verify that message_bubbles cannot be empty

**Test Cases:**
- Empty string: `""`
- Empty array: `"[]"`
- Null value: `null`

**Expected:** 422 Unprocessable Entity with validation error

### Test 2.5: Missing Required Fields Rejected
**Purpose:** Verify that missing required fields are rejected

**Test Cases:**
- Missing task_id
- Missing session_id (in URL)
- Missing message_bubbles

**Expected:** 422 Unprocessable Entity

### Test 2.6: Large Payload Handling
**Purpose:** Verify that large but valid payloads are handled correctly

**Steps:**
1. Create message_bubbles with 100 message objects
2. Create task_metadata with large nested structure
3. POST the task
4. Verify it succeeds
5. GET the task back
6. Verify data integrity (no truncation)

---

## Test Suite 3: Authorization & Security

### Test 3.1: User Can Only Access Own Session's Tasks
**Purpose:** Verify that users can only access tasks in their own sessions

**Steps:**
1. User A creates session A
2. User A creates task in session A
3. User B attempts to GET `/sessions/{session_A_id}/chat-tasks`
4. Verify response is 404 (not 403, to prevent information leakage)

### Test 3.2: User Cannot Create Task in Another User's Session
**Purpose:** Verify that users cannot create tasks in sessions they don't own

**Steps:**
1. User A creates session A
2. User B attempts to POST task to `/sessions/{session_A_id}/chat-tasks`
3. Verify response is 404

### Test 3.3: Invalid Session ID Returns 404
**Purpose:** Verify proper handling of invalid session IDs

**Test Cases:**
- Non-existent session ID
- Empty string: `""`
- Null-like values: `"null"`, `"undefined"`
- Malformed ID

**Expected:** 404 Not Found for all cases

### Test 3.4: Task Isolation Between Sessions
**Purpose:** Verify that tasks are properly isolated between sessions

**Steps:**
1. User A creates session A with 3 tasks
2. User A creates session B with 2 tasks
3. GET tasks for session A
4. Verify only 3 tasks returned (session A's tasks)
5. GET tasks for session B
6. Verify only 2 tasks returned (session B's tasks)

---

## Test Suite 4: Integration with Existing Features

### Test 4.1: Tasks Cascade Delete with Session
**Purpose:** Verify that deleting a session deletes all its tasks

**Steps:**
1. Create a session
2. Create 5 tasks in the session
3. Verify tasks exist via GET
4. DELETE the session
5. Attempt to GET tasks for deleted session
6. Verify response is 404
7. Verify tasks are actually deleted from database (not just hidden)

### Test 4.2: Messages Endpoint Derives from Tasks
**Purpose:** Verify that `/messages` endpoint correctly flattens tasks

**Steps:**
1. Create a session
2. Create task with message_bubbles containing 2 user messages and 2 agent messages
3. Create another task with 1 user message and 1 agent message
4. GET `/sessions/{session_id}/messages`
5. Verify response contains 6 messages total
6. Verify messages are in correct order
7. Verify message content matches what was in message_bubbles
8. Verify sender_type is correctly derived from bubble type

### Test 4.3: Task Creation via Message Stream
**Purpose:** Verify that sending messages via `/message:stream` creates tasks

**Steps:**
1. POST to `/message:stream` to create session
2. Send follow-up message to same session
3. GET `/sessions/{session_id}/chat-tasks`
4. Verify tasks were created automatically
5. Verify task structure is correct

### Test 4.4: Feedback Updates Task Metadata
**Purpose:** Verify that submitting feedback updates the task's metadata

**Steps:**
1. Create a session and task
2. Submit feedback via `/feedback` endpoint
3. GET the task via `/chat-tasks`
4. Verify task_metadata contains feedback information
5. Verify feedback structure: `{"feedback": {"type": "up", "text": "...", "submitted": true}}`

---

## Test Suite 5: Edge Cases & Boundary Conditions

### Test 5.1: Multiple Tasks Same Session
**Purpose:** Verify handling of many tasks in one session

**Steps:**
1. Create a session
2. Create 50 tasks
3. GET all tasks
4. Verify all 50 tasks returned
5. Verify correct ordering
6. Verify no data corruption

### Test 5.2: Concurrent Task Creation
**Purpose:** Verify that concurrent task creation is handled correctly

**Steps:**
1. Create a session
2. Rapidly POST 10 tasks (simulating concurrent requests)
3. GET all tasks
4. Verify all 10 tasks exist
5. Verify no duplicate task_ids
6. Verify data integrity

### Test 5.3: Task with Minimal Data
**Purpose:** Verify that tasks with minimal required data work

**Steps:**
1. Create task with only required fields:
   - task_id
   - message_bubbles (minimal valid array)
   - user_message: null
   - task_metadata: null
2. Verify task is created successfully
3. GET task and verify null fields are preserved

### Test 5.4: Task with Maximum Data
**Purpose:** Verify that tasks with all optional fields work

**Steps:**
1. Create task with all fields populated:
   - task_id
   - user_message (long text)
   - message_bubbles (large array)
   - task_metadata (complex nested structure)
2. Verify task is created successfully
3. GET task and verify all data preserved

### Test 5.5: Unicode and Special Characters
**Purpose:** Verify proper handling of Unicode and special characters

**Test Cases:**
- Emoji in user_message: "Hello 👋 World 🌍"
- Unicode in message_bubbles: Chinese, Arabic, emoji
- Special JSON characters in strings: quotes, backslashes, newlines
- HTML/XML in content

**Expected:** All should be properly escaped and preserved

### Test 5.6: Task Ordering Consistency
**Purpose:** Verify that task ordering is consistent

**Steps:**
1. Create 10 tasks with known created_time values
2. GET tasks multiple times
3. Verify ordering is always the same (chronological by created_time)
4. Update a task (changes updated_time)
5. Verify ordering still based on created_time, not updated_time

---

## Test Suite 6: Error Handling & Recovery

### Test 6.1: Database Error Handling
**Purpose:** Verify graceful handling of database errors

**Steps:**
1. Mock database to raise exception
2. Attempt to POST task
3. Verify 500 Internal Server Error
4. Verify error message is generic (no sensitive info leaked)

### Test 6.2: Malformed Request Body
**Purpose:** Verify handling of malformed request bodies

**Test Cases:**
- Invalid JSON in request body
- Missing Content-Type header
- Wrong Content-Type (e.g., text/plain)

**Expected:** 422 or 400 with appropriate error message

### Test 6.3: Session Not Found During Task Creation
**Purpose:** Verify behavior when session doesn't exist

**Steps:**
1. Attempt to POST task to non-existent session
2. Verify 404 response
3. Verify task was not created

### Test 6.4: Partial Update Failure
**Purpose:** Verify transaction rollback on partial failure

**Steps:**
1. Create a task
2. Attempt to update with invalid data
3. Verify update fails
4. GET the task
5. Verify original data is unchanged (rollback worked)

---

## Test Suite 7: Performance & Scalability

### Test 7.1: Large message_bubbles Performance
**Purpose:** Verify performance with large message_bubbles

**Steps:**
1. Create task with message_bubbles containing 1000 message objects
2. Measure POST response time
3. GET the task
4. Measure GET response time
5. Verify reasonable performance (< 1 second for both)

### Test 7.2: Many Tasks Per Session Performance
**Purpose:** Verify performance with many tasks

**Steps:**
1. Create session with 100 tasks
2. Measure GET all tasks response time
3. Verify reasonable performance (< 2 seconds)
4. Verify memory usage is reasonable

---

## Test Suite 8: Backward Compatibility

### Test 8.1: Old Messages Endpoint Still Works
**Purpose:** Verify that existing `/messages` endpoint continues to work

**Steps:**
1. Create session using old workflow
2. GET `/sessions/{session_id}/messages`
3. Verify response format matches old format
4. Verify all expected fields present

### Test 8.2: Mixed Old and New Data
**Purpose:** Verify system handles mix of old messages and new tasks

**Steps:**
1. Create session with old-style messages (if any exist)
2. Create new-style tasks
3. GET `/messages` endpoint
4. Verify both old and new data returned correctly
5. Verify correct ordering

---

## Implementation Notes

### Test Fixtures Needed
- `create_test_task()` - Helper to create valid task data
- `create_minimal_task()` - Helper for minimal valid task
- `create_maximal_task()` - Helper for task with all fields
- `create_invalid_task()` - Helper for various invalid task scenarios

### Assertions to Include
- Status code checks
- Response schema validation
- Data integrity checks (round-trip)
- Timestamp validation (created_time, updated_time)
- JSON string validation (valid JSON, correct structure)
- Authorization checks (404 for unauthorized access)

### Database Verification
For critical tests, verify database state directly:
- Check `chat_tasks` table for expected records
- Verify foreign key relationships
- Verify cascade deletes work correctly

### Test Data Patterns
Use consistent test data patterns:
- Task IDs: `"task-{test_name}-{sequence}"`
- Session IDs: `"session-{test_name}-{sequence}"`
- User IDs: `"user-{test_name}"`

---

## Success Criteria

All tests must:
1. Pass consistently (no flaky tests)
2. Run in isolation (no dependencies between tests)
3. Clean up after themselves (database cleanup)
4. Have clear failure messages
5. Cover both happy path and error cases
6. Verify both API contract and business logic

## Estimated Test Count

- Basic CRUD: 4 tests
- Data Validation: 6 tests
- Authorization: 4 tests
- Integration: 4 tests
- Edge Cases: 6 tests
- Error Handling: 4 tests
- Performance: 2 tests
- Backward Compatibility: 2 tests

**Total: ~32 tests**

---

## Future Considerations

### Tests to Add Later
1. Pagination for task lists (when implemented)
2. Filtering/searching tasks (when implemented)
3. Task versioning (if implemented)
4. Bulk operations (if implemented)
5. Rate limiting (if implemented)

### Performance Benchmarks
Consider adding performance benchmarks for:
- Task creation throughput
- Task retrieval latency
- Large payload handling
- Concurrent access patterns
