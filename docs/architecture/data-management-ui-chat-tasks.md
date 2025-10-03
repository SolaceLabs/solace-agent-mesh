# Data Management for UI Chat Tasks

## Document Information

- **Title**: Data Management for UI Chat Tasks
- **Version**: 1.0
- **Date**: 2025-01-03
- **Status**: Active
- **Related Documents**: 
  - [Feature Specification](../features/frontend-driven-chat-persistence.md)
  - [Detailed Design](../design/frontend-driven-chat-persistence-detailed-design.md)

---

## Table of Contents

1. [Introduction](#introduction)
2. [High-Level Architecture](#high-level-architecture)
3. [Data Schemas](#data-schemas)
4. [Schema Migration Strategy](#schema-migration-strategy)
5. [Future Considerations](#future-considerations)

---

## 1. Introduction

### Purpose

This document describes how the Web UI chat system persists and manages UI state to enable accurate session replay across browser sessions and devices.

### Problem Statement

When users interact with AI agents through the chat interface, they see a rich visual experience that includes:
- Streaming text responses
- File attachments and artifacts
- Embedded content (images, code, data visualizations)
- UI-specific state (feedback, notifications, error styling)

To provide a seamless experience, we need to:
1. **Persist** the exact visual state the user saw
2. **Restore** that state accurately when they return
3. **Support** UI evolution without breaking old data

### Solution Overview

We store complete task interactions (user input + agent response) as **opaque JSON blobs** in the database. The frontend owns the schema and is responsible for:
- Serializing UI state before saving
- Deserializing and migrating data when loading
- Evolving the schema over time

The backend is a **dumb storage layer** that:
- Stores JSON strings in TEXT columns
- Validates only size limits and non-empty constraints
- Has no knowledge of the JSON structure

**Key Principle**: The frontend is the authoritative source of truth for what the user saw.

---

## 2. High-Level Architecture

### 2.1 Storage Model

We use a **task-based storage model** where each task represents one complete interaction:

```
User Input → Agent Processing → Agent Response(s) → Task Complete
└─────────────────── One Task Record ──────────────────┘
```

**Why tasks instead of individual messages?**
- More efficient (one DB write per task vs. N writes per message)
- Semantically correct (a task is the natural unit of conversation)
- Atomic (either the whole task is saved or none of it)
- Easier to update (one record to modify for feedback, etc.)

### 2.2 Save Timing

#### 2.2.1 User Messages (Initial Save)

**When**: Immediately after successful A2A request submission

**What**: Initial task record with user input

**Why**: Capture user intent even if agent response fails

```
User clicks send
    ↓
Frontend submits A2A request
    ↓
Backend returns taskId
    ↓
Frontend saves initial task:
  - taskId
  - user_message
  - message_bubbles: [user bubble]
  - task_metadata: {status: "pending"}
```

#### 2.2.2 Agent Messages (Final Save)

**When**: When task completes (success, error, or cancellation)

**What**: Complete task with all message bubbles

**Why**: Capture the full interaction atomically

```
Agent sends final event
    ↓
Frontend gathers all bubbles for this task
    ↓
Frontend filters out status bubbles
    ↓
Frontend saves complete task:
  - taskId (same as initial)
  - user_message
  - message_bubbles: [user bubble, agent bubbles...]
  - task_metadata: {status: "completed", feedback: null}
    ↓
Backend upserts (overwrites initial save)
```

#### 2.2.3 Feedback Updates

**When**: User submits feedback (thumbs up/down)

**What**: Update task_metadata with feedback

**Why**: Feedback can be added after task completion

```
User clicks thumbs up
    ↓
Frontend submits feedback
    ↓
Backend updates both:
  - feedback table (for analytics)
  - chat_tasks.task_metadata (for UI state)
```

### 2.3 Load Timing

**When**: User switches to a different session

**What**: Load all tasks for that session

**How**:
```
User clicks session in sidebar
    ↓
Frontend requests: GET /sessions/{id}/tasks
    ↓
Backend returns all tasks (ordered by created_time)
    ↓
Frontend deserializes each task:
  - Check schema_version
  - Apply migrations if needed
  - Convert to MessageFE objects
    ↓
Frontend updates state:
  - setMessages(allMessages)
  - setSubmittedFeedback(feedbackMap)
    ↓
Chat window displays exact history
```

### 2.4 Data Flow Diagram

```
┌─────────────┐
│   Browser   │
│  (Frontend) │
└──────┬──────┘
       │
       │ POST /sessions/{id}/tasks
       │ {taskId, userMessage, messageBubbles, taskMetadata}
       │
       ↓
┌─────────────┐
│   FastAPI   │
│  (Backend)  │
└──────┬──────┘
       │
       │ INSERT/UPDATE chat_tasks
       │ (id, session_id, user_id, user_message,
       │  message_bubbles TEXT, task_metadata TEXT,
       │  created_time, updated_time)
       │
       ↓
┌─────────────┐
│  Database   │
│  (Storage)  │
└─────────────┘
```

---

## 3. Data Schemas

### 3.1 Database Row Schema

**Table**: `chat_tasks`

**Columns**:

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | VARCHAR | NOT NULL | A2A taskId (e.g., "gdk-task-abc123") |
| `session_id` | VARCHAR | NOT NULL | Foreign key to sessions.id (CASCADE delete) |
| `user_id` | VARCHAR | NOT NULL | User who owns this task |
| `user_message` | TEXT | NULL | Original user input text (for search/display) |
| `message_bubbles` | TEXT | NOT NULL | JSON string: Array of message bubble objects |
| `task_metadata` | TEXT | NULL | JSON string: Task-level information |
| `created_time` | BIGINT | NOT NULL | Epoch milliseconds when task was created |
| `updated_time` | BIGINT | NULL | Epoch milliseconds when task was last updated |

**Indexes**:
- Primary key on `id`
- Index on `session_id` (for loading session history)
- Index on `user_id` (for user-specific queries)
- Index on `created_time` (for chronological ordering)

**Foreign Keys**:
- `session_id` → `sessions.id` ON DELETE CASCADE

**Storage Format**:
- `message_bubbles` and `task_metadata` are stored as **TEXT columns** (not JSON columns)
- This makes it clear they are opaque blobs to the database
- Backend serializes/deserializes but does not validate structure

### 3.2 Message Bubbles Schema

**Field**: `message_bubbles`

**Type**: JSON string containing an array of bubble objects

**JSON Schema** (Version 1):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "array",
  "minItems": 1,
  "items": {
    "type": "object",
    "required": ["id", "type"],
    "properties": {
      "id": {
        "type": "string",
        "description": "Frontend-generated unique identifier for this bubble"
      },
      "type": {
        "type": "string",
        "enum": ["user", "agent", "artifact_notification"],
        "description": "Type of message bubble"
      },
      "text": {
        "type": "string",
        "description": "Combined text from all text parts (optional, for quick display)"
      },
      "parts": {
        "type": "array",
        "description": "Full A2A Part objects for reconstruction (optional)",
        "items": {
          "type": "object",
          "properties": {
            "kind": {
              "type": "string",
              "enum": ["text", "file", "data"]
            }
          }
        }
      },
      "files": {
        "type": "array",
        "description": "Agent-returned file attachments (optional)",
        "items": {
          "type": "object",
          "properties": {
            "name": {"type": "string"},
            "mime_type": {"type": "string"},
            "content": {"type": "string", "description": "Base64 encoded"},
            "uri": {"type": "string"}
          }
        }
      },
      "uploadedFiles": {
        "type": "array",
        "description": "User-uploaded files (optional)",
        "items": {
          "type": "object",
          "required": ["name", "type"],
          "properties": {
            "name": {"type": "string"},
            "type": {"type": "string", "description": "MIME type"}
          }
        }
      },
      "artifactNotification": {
        "type": "object",
        "description": "Artifact creation notice (optional)",
        "properties": {
          "name": {"type": "string"},
          "version": {"type": "number"}
        }
      },
      "isError": {
        "type": "boolean",
        "description": "Whether this bubble represents an error (optional)"
      }
    }
  }
}
```

**Example**:

```json
[
  {
    "id": "msg-user-001",
    "type": "user",
    "text": "Can you analyze this sales data?",
    "parts": [
      {"kind": "text", "text": "Can you analyze this sales data?"}
    ],
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
  },
  {
    "id": "msg-agent-002",
    "type": "agent",
    "text": "Here's my analysis:\n\n- Total revenue: $1.2M",
    "parts": [
      {"kind": "text", "text": "Here's my analysis:\n\n- Total revenue: $1.2M"}
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
]
```

**Design Notes**:
- Store both `text` (for quick display) and `parts` (for full reconstruction)
- Include all file attachments inline (base64 content or URIs)
- Capture artifact notifications as they appeared
- Flag error messages for proper styling
- **Status bubbles are NOT saved** (they are transient UI indicators)

### 3.3 Task Metadata Schema

**Field**: `task_metadata`

**Type**: JSON string containing a metadata object

**JSON Schema** (Version 1):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["schema_version"],
  "properties": {
    "schema_version": {
      "type": "integer",
      "description": "Schema version for migration purposes",
      "minimum": 1
    },
    "status": {
      "type": "string",
      "enum": ["pending", "completed", "error", "cancelled"],
      "description": "Task completion status"
    },
    "feedback": {
      "type": "object",
      "description": "User feedback (optional)",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["up", "down"]
        },
        "submitted": {
          "type": "boolean",
          "description": "Whether feedback was submitted"
        }
      }
    },
    "agent_name": {
      "type": "string",
      "description": "Name of the agent that handled this task (optional)"
    },
    "duration_ms": {
      "type": "number",
      "description": "Task duration in milliseconds (optional, for future analytics)"
    },
    "token_count": {
      "type": "number",
      "description": "Total tokens used (optional, for future analytics)"
    }
  }
}
```

**Example**:

```json
{
  "schema_version": 1,
  "status": "completed",
  "feedback": {
    "type": "up",
    "submitted": true
  },
  "agent_name": "data_analyst",
  "duration_ms": 8420
}
```

**Design Notes**:
- `schema_version` is **required** for all new saves
- `status` tracks task outcome
- `feedback` is integrated directly with the task
- `agent_name` enables filtering/display
- Future fields (`duration_ms`, `token_count`) reserved for analytics

---

## 4. Schema Migration Strategy

### 4.1 Migration Philosophy

**Approach**: **Lazy Migration** (migrate on load, not in database)

**Why**:
- No database downtime required
- Fast deployment
- Easy to iterate on migrations
- Old data stays in original format
- Frontend owns the migration logic

**How**:
1. Frontend checks `schema_version` when loading tasks
2. Applies migrations sequentially to bring data to current version
3. Renders using current schema
4. When saving, always uses current schema version

### 4.2 Version Detection

```typescript
// In ChatProvider.tsx - loadSessionTasks()
const loadSessionTasks = useCallback(async (sessionId: string) => {
    const response = await authenticatedFetch(
        `${apiPrefix}/sessions/${sessionId}/chat-tasks`
    );
    const data = await response.json();
    const tasks = data.tasks || [];
    
    // Migrate each task to current schema
    const migratedTasks = tasks.map(task => {
        const version = task.taskMetadata?.schema_version || 0;
        let migratedTask = task;
        
        // Apply migrations sequentially
        if (version < 1) migratedTask = migrateV0ToV1(migratedTask);
        if (version < 2) migratedTask = migrateV1ToV2(migratedTask);
        // ... more migrations as needed
        
        return migratedTask;
    });
    
    // Deserialize to messages
    const allMessages = migratedTasks.flatMap(deserializeTaskToMessages);
    setMessages(allMessages);
}, [apiPrefix, deserializeTaskToMessages]);
```

### 4.3 Migration Examples

#### Example 1: Adding Schema Version (V0 → V1)

**Scenario**: Initial deployment had no `schema_version` field.

**Migration**:

```typescript
function migrateV0ToV1(task: any): any {
    return {
        ...task,
        taskMetadata: {
            ...task.taskMetadata,
            schema_version: 1  // Add version field
        }
    };
}
```

**Result**: All old tasks now have `schema_version: 1`.

#### Example 2: Adding Timestamp to Bubbles (V1 → V2)

**Scenario**: We want to add a `timestamp` fiel to each bubble for better chronological display.

**Migration**:

```typescript
function migrateV1ToV2(task: any): any {
    const migratedBubbles = task.messageBubbles.map((bubble: any) => ({
        ...bubble,
        timestamp: bubble.timestamp || task.createdTime  // Default to task creation time
    }));
    
    return {
        ...task,
        messageBubbles: migratedBubbles,
        taskMetadata: {
            ...task.taskMetadata,
            schema_version: 2
        }
    };
}
```

**Result**: All bubbles now have a `timestamp` field.

#### Example 3: Renaming a Field (V2 → V3)

**Scenario**: Rename `uploadedFiles` to `userFiles` for clarity.

**Migration**:

```typescript
function migrateV2ToV3(task: any): any {
    const migratedBubbles = task.messageBubbles.map((bubble: any) => {
        const { uploadedFiles, ...rest } = bubble;
        return {
            ...rest,
            userFiles: uploadedFiles || []  // Rename field
        };
    });
    
    return {
        ...task,
        messageBubbles: migratedBubbles,
        taskMetadata: {
            ...task.taskMetadata,
            schema_version: 3
        }
    };
}
```

**Result**: Old `uploadedFiles` field is now `userFiles`.

#### Example 4: Restructuring Metadata (V3 → V4)

**Scenario**: Move `feedback` from `task_metadata` to a separate top-level field.

**Migration**:

```typescript
function migrateV3ToV4(task: any): any {
    const { taskMetadata, ...rest } = task;
    const { feedback, ...otherMetadata } = taskMetadata || {};
    
    return {
        ...rest,
        feedback: feedback || null,  // NEW TOP-LEVEL FIELD
        taskMetadata: {
            ...otherMetadata,
            schema_version: 4
        }
    };
}
```

**Result**: Feedback is now a top-level field instead of nested in metadata.

#### Example 5: Adding Default Values (V4 → V5)

**Scenario**: Add `isCollapsed` flag to bubbles for future UI feature.

**Migration**:

```typescript
function migrateV4ToV5(task: any): any {
    const migratedBubbles = task.messageBubbles.map((bubble: any) => ({
        ...bubble,
        isCollapsed: false  // Default to expanded
    }));
    
    return {
        ...task,
        messageBubbles: migratedBubbles,
        taskMetadata: {
            ...task.taskMetadata,
            schema_version: 5
        }
    };
}
```

**Result**: All bubbles have `isCollapsed: false` by default.

### 4.4 Migration Best Practices

#### 1. Always Support N-1 Versions

Keep migration code for at least the previous version:

```typescript
const SUPPORTED_VERSIONS = [0, 1, 2, 3, 4, 5];  // Current is 5
const CURRENT_VERSION = 5;

function migrateTask(task: any): any {
    const version = task.taskMetadata?.schema_version || 0;
    
    if (!SUPPORTED_VERSIONS.includes(version)) {
        console.warn(`Unsupported schema version: ${version}`);
        // Fallback to best-effort rendering
    }
    
    // Apply migrations sequentially
    let migratedTask = task;
    for (let v = version; v < CURRENT_VERSION; v++) {
        const migrationFunc = MIGRATIONS[v];
        if (migrationFunc) {
            migratedTask = migrationFunc(migratedTask);
        }
    }
    
    return migratedTask;
}

const MIGRATIONS: Record<number, (task: any) => any> = {
    0: migrateV0ToV1,
    1: migrateV1ToV2,
    2: migrateV2ToV3,
    3: migrateV3ToV4,
    4: migrateV4ToV5,
};
```

#### 2. Graceful Degradation

If a field is missing, use sensible defaults:

```typescript
const bubble = {
    id: data.id || `msg-${v4()}`,
    type: data.type || "agent",
    text: data.text || "",
    parts: data.parts || [{ kind: "text", text: data.text || "" }],
    timestamp: data.timestamp || Date.now(),
    // ... with defaults for all optional fields
};
```

#### 3. Validation on Save

Ensure new data always has required fields:

```typescript
function validateMessageBubble(bubble: any): boolean {
    if (!bubble.id) {
        console.error("Bubble missing id:", bubble);
        return false;
    }
    if (!bubble.type) {
        console.error("Bubble missing type:", bubble);
        return false;
    }
    return true;
}

// Before saving
const validBubbles = messageBubbles.filter(validateMessageBubble);
if (validBubbles.length !== messageBubbles.length) {
    console.error("Some bubbles failed validation");
}
```

#### 4. Log Migration Activity

```typescript
function migrateTask(task: any): any {
    const version = task.taskMetadata?.schema_version || 0;
    
    if (version < CURRENT_VERSION) {
        console.log(`Migrating task ${task.taskId} from v${version} to v${CURRENT_VERSION}`);
        const startTime = performance.now();
        
        // Apply migrations...
        const migratedTask = applyMigrations(task, version);
        
        const duration = performance.now() - startTime;
        if (duration > 100) {
            console.warn(`Slow migration for task ${task.taskId}: ${duration}ms`);
        }
        
        return migratedTask;
    }
    
    return task;
}
```

#### 5. Document Schema Changes

Maintain a schema changelog:

```markdown
# Message Bubble Schema Changelog

## Version 5 (2025-02-15)
- Added `isCollapsed` boolean field to bubbles
- Default value: `false`

## Version 4 (2025-02-01)
- Moved `feedback` from `task_metadata` to top-level field
- Migration: Extract feedback from metadata

## Version 3 (2025-01-20)
- Renamed `uploadedFiles` to `userFiles`
- Migration: Rename field in all bubbles

## Version 2 (2025-01-10)
- Added `timestamp` field to bubbles
- Default value: task `createdTime`

## Version 1 (2025-01-03)
- Initial schema with explicit versioning
- Added `schema_version` to `task_metadata`
```

### 4.5 When to Use Eager Migration

**Lazy migration is recommended**, but consider eager (database) migration if:

1. **Performance**: Millions of records and lazy migration is too slow
2. **Cleanup**: Removing deprecated fields to save storage
3. **Breaking Changes**: Schema change is so fundamental that lazy migration is impractical

**Process for eager migration**:
1. Write Alembic migration script
2. Test on copy of production database
3. Schedule maintenance window
4. Run migration with progress monitoring
5. Verify data integrity
6. Deploy new frontend code

---

## 5. Future Considerations

### 5.1 Partial Rendering (Virtual Scrolling)

**Problem**: Long chat sessions (100+ tasks) consume significant browser memory.

**Solution**: Implement virtual scrolling to render only visible tasks.

**Implementation**:

```typescript
// Load task metadata only (without message_bubbles)
GET /sessions/{id}/tasks?fields=id,userMessage,taskMetadata,createdTime

// Returns lightweight list:
[
  {taskId: "...", userMessage: "...", taskMetadata: {...}, createdTime: 123},
  // ... 100 more
]

// When user scrolls near a task, load full data:
GET /sessions/{id}/tasks/{taskId}

// Returns complete task with message_bubbles
```

**Benefits**:
- Faster initial load
- Lower memory usage
- Smoother scrolling for long sessions

**API Changes Needed**:
- Add `fields` query parameter to filter response
- Add single-task endpoint: `GET /sessions/{id}/tasks/{taskId}`

### 5.2 Workflow Visualization from Historical Data

**Problem**: Workflow button currently only works for active tasks.

**Solution**: Load historical task data from `tasks` and `task_events` tables.

**Implementation**:

```typescript
// When user clicks workflow button on old message
const taskId = message.taskId;

// Load task events from analytics tables
GET /tasks/{taskId}  // Returns .stim file with full event history

// Parse and render workflow visualization
const workflow = parseStimFile(stimData);
renderWorkflow(workflow);
```

**Benefits**:
- Workflow visualization works for all historical tasks
- No need to store workflow data separately
- Reuses existing task logging infrastructure

**Requirements**:
- Task logging must be enabled
- `tasks` and `task_events` tables must exist
- Frontend can parse .stim format


