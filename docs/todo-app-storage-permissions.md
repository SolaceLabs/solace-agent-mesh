# TODO: App Storage Permissions & Data Model Enhancements

## Current State

### Storage System
- **Location**: `src/solace_agent_mesh/gateway/http_sse/routers/storage.py`
- **Current Implementation**: In-memory key-value store (not persisted to DB)
- **Scoping**: Currently `{user_id} → {app_id} → {key: value}`
- **Access Control**: Simple - each user sees only their own data per app

### Existing Role System
- **AppUserModel** (`app_user_model.py`): Already has roles for app access
  - `OWNER` - full control
  - `EDITOR` - can modify
  - `VIEWER` - read-only
- This controls who can access/edit the *app itself*, not the *data within the app*

---

## Enhancement Ideas

### 1. User-Specific Storage Entries with Permissions

**Goal**: Allow apps to store data with different visibility/permission levels.

#### Proposed Permission Levels

| Permission | Write | Read | Use Case |
|------------|-------|------|----------|
| `private` | owner only | owner only | Personal settings, drafts, private notes |
| `readable` | owner only | all users | Shared configs, announcements, published data |
| `read_write` | all users | all users | Collaborative data, shared state |

#### Database Schema Option A: Add permissions to storage entries

```sql
CREATE TABLE app_storage (
    id VARCHAR PRIMARY KEY,
    app_id VARCHAR NOT NULL,
    owner_user_id VARCHAR NOT NULL,      -- who created/owns this entry
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    permission VARCHAR(20) NOT NULL DEFAULT 'private',  -- 'private', 'readable', 'read_write'
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,

    UNIQUE(app_id, owner_user_id, key)   -- unique key per user per app
);

-- Index for efficient queries
CREATE INDEX idx_app_storage_app_id ON app_storage(app_id);
CREATE INDEX idx_app_storage_owner ON app_storage(owner_user_id);
CREATE INDEX idx_app_storage_permission ON app_storage(permission);
```

#### Database Schema Option B: Separate tables for different visibility

```sql
-- User's private storage (current behavior, persisted)
CREATE TABLE app_storage_private (
    id VARCHAR PRIMARY KEY,
    app_id VARCHAR NOT NULL,
    user_id VARCHAR NOT NULL,
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,

    UNIQUE(app_id, user_id, key)
);

-- Shared storage (app-wide, readable by all)
CREATE TABLE app_storage_shared (
    id VARCHAR PRIMARY KEY,
    app_id VARCHAR NOT NULL,
    owner_user_id VARCHAR NOT NULL,      -- who created it
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    is_writable BOOLEAN DEFAULT FALSE,   -- can others write?
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,

    UNIQUE(app_id, key)                  -- only one shared entry per key per app
);
```

#### SDK API Changes

```typescript
// Current API (would remain for backward compat)
await SAM.storage.get('myKey')           // user's private data
await SAM.storage.set('myKey', value)    // user's private data

// New API additions
await SAM.storage.get('myKey', { scope: 'private' })     // explicit private
await SAM.storage.get('myKey', { scope: 'shared' })      // app-wide shared data
await SAM.storage.set('myKey', value, {
    scope: 'shared',      // save to shared space
    permission: 'readable'  // others can read, only owner can write
})

// List with scope filtering
await SAM.storage.list({ scope: 'private' })
await SAM.storage.list({ scope: 'shared' })
await SAM.storage.list({ scope: 'all' })
```

---

### 2. Role-Based Access Control for Data

**Goal**: Managers can see all data, regular users have restricted views.

#### Option A: Extend existing AppRole

Current roles (`owner`, `editor`, `viewer`) could control data visibility:
- `owner`: Can see all users' data, manage permissions
- `editor`: Can see shared data, can modify shared writable data
- `viewer`: Can only see shared readable data + own private data

#### Option B: Add new "Manager" role

```python
class AppRole(str, Enum):
    OWNER = "owner"        # Full control, app settings, can delete
    MANAGER = "manager"    # Can see all user data, manage content
    EDITOR = "editor"      # Can modify shared content
    VIEWER = "viewer"      # Read-only access
```

#### API Endpoint Changes

```
GET /api/v1/apps/{app_id}/storage
  - Regular users: returns only their private data + shared readable/writable
  - Managers/Owners: returns ALL users' data (with user_id attribution)

GET /api/v1/apps/{app_id}/storage/users/{user_id}
  - New endpoint for managers to view specific user's data
  - Returns 403 for non-managers
```

---

### 3. Database Migrations on App Promotion

**Goal**: Allow apps to run DB migrations when promoted to new environments.

#### Context
- Apps currently use simple key-value storage
- If we expand to structured data (tables), we'd need migrations
- Promotions: `draft → dev → staging → prod`

#### Questions to Consider

1. **Do we need structured storage?**
   - Key-value might be sufficient for most apps
   - Structured DB adds complexity (schema management, migrations)
   - Consider: SQLite per-app? Or just enhanced JSON storage?

2. **If yes to structured storage:**

   **Option A: Migration Scripts in Workspace**
   ```
   {app_id}/
   ├── src/
   ├── migrations/
   │   ├── 001_initial.sql
   │   ├── 002_add_users_table.sql
   │   └── 003_add_preferences.sql
   └── package.json
   ```

   - Claude Code generates migration files
   - On promotion, gateway runs pending migrations
   - Track applied migrations in `app_migrations` table

   **Option B: Schema-on-Write (NoSQL-style)**
   - Keep key-value but allow structured JSON values
   - No migrations needed - apps handle schema evolution in code
   - Simpler but less powerful

   **Option C: Per-App SQLite Database**
   ```
   {workspace_path}/data/app.db
   ```
   - Each app gets its own SQLite file
   - Apps manage their own schema via migrations
   - Gateway doesn't need to understand app schema

#### Migration Table Schema (if going with Option A)

```sql
CREATE TABLE app_migrations (
    id VARCHAR PRIMARY KEY,
    app_id VARCHAR NOT NULL,
    environment VARCHAR(20) NOT NULL,    -- 'dev', 'staging', 'prod'
    migration_name VARCHAR(255) NOT NULL,
    applied_at BIGINT NOT NULL,
    applied_by_user_id VARCHAR NOT NULL,

    UNIQUE(app_id, environment, migration_name)
);
```

---

### 4. Multi-Model LLM Support

**Goal**: Allow apps to request LLM completions with model selection.

#### Current State
- Apps can call SAM agents via `SAM.agents.call()`
- No direct LLM access from apps
- Gateway likely has a single configured LLM provider

#### Proposed Features

1. **List Available Models**: Apps can discover what LLMs are available
2. **Model Selection**: Apps can choose which model to use per request
3. **Model Metadata**: Expose capabilities, pricing tier, context limits

#### SDK API Design

```typescript
// List available models
const models = await SAM.llm.list()
// Returns: [
//   { id: 'claude-sonnet-4', name: 'Claude Sonnet 4', provider: 'anthropic', contextWindow: 200000, tier: 'standard' },
//   { id: 'claude-opus-4', name: 'Claude Opus 4', provider: 'anthropic', contextWindow: 200000, tier: 'premium' },
//   { id: 'gpt-4o', name: 'GPT-4o', provider: 'openai', contextWindow: 128000, tier: 'standard' },
// ]

// Call LLM with model selection
const response = await SAM.llm.complete({
    model: 'claude-sonnet-4',          // required: which model to use
    messages: [
        { role: 'user', content: 'Hello!' }
    ],
    temperature: 0.7,                   // optional
    maxTokens: 1000,                    // optional
    stream: true,                       // optional: stream response
    onText: (chunk) => { ... },         // callback for streaming
})

// Simple helper for common use case
const text = await SAM.llm.ask('claude-sonnet-4', 'What is 2+2?')
```

#### Backend API Endpoints

```
GET /api/v1/llm/models
  - Returns list of available models with metadata
  - May be filtered by user permissions/tier

POST /api/v1/llm/complete
  - Body: { model, messages, temperature?, maxTokens?, stream? }
  - Returns completion or streams via SSE
  - Validates user has access to requested model
```

#### Gateway Configuration

```yaml
# Example gateway config for multiple LLM providers
llm_providers:
  - id: claude-sonnet-4
    provider: anthropic
    model: claude-sonnet-4-20250514
    api_key: ${ANTHROPIC_API_KEY}
    tier: standard              # for access control
    enabled: true

  - id: claude-opus-4
    provider: anthropic
    model: claude-opus-4-20250514
    api_key: ${ANTHROPIC_API_KEY}
    tier: premium
    enabled: true

  - id: gpt-4o
    provider: openai
    model: gpt-4o
    api_key: ${OPENAI_API_KEY}
    tier: standard
    enabled: true

  - id: local-llama
    provider: ollama
    model: llama3.2
    base_url: http://localhost:11434
    tier: free
    enabled: false
```

#### Access Control Options

1. **Tier-based**: Users/apps have a tier that limits which models they can use
2. **Allowlist**: Specific models enabled per app or per user
3. **Quota-based**: Rate limiting or token budgets per model

#### Message Types (SDK ↔ Host)

```typescript
enum MessageType {
    // ... existing types ...

    // LLM operations
    LLM_LIST = 'sam:llm:list',
    LLM_LIST_RESPONSE = 'sam:llm:list:response',
    LLM_COMPLETE = 'sam:llm:complete',
    LLM_COMPLETE_RESPONSE = 'sam:llm:complete:response',
    LLM_STREAM = 'sam:llm:stream',
    LLM_ERROR = 'sam:llm:error',
}
```

#### Implementation Considerations

1. **Abstraction Layer**: Need a unified interface that works across providers (Anthropic, OpenAI, Bedrock, Ollama, etc.)

2. **Streaming**: Support SSE streaming for real-time responses

3. **Cost Tracking**: Log usage per app/user for billing or quota enforcement

4. **Safety**:
   - Rate limiting to prevent abuse
   - Content filtering if needed
   - Prompt injection protection

5. **Caching**: Optional response caching for identical prompts

---

### 5. Library Security & Vulnerability Management

**Goal**: Ensure apps don't serve users with known security vulnerabilities in dependencies.

#### The Problem

- Apps are created from a template with pinned dependencies
- Over time, vulnerabilities are discovered in npm packages
- Existing apps don't automatically get security updates
- SAM SDK updates aren't propagated to existing apps
- No visibility into which apps have vulnerable dependencies

#### Proposed Solutions

##### A. Automated Vulnerability Scanning

**On-demand scanning:**
```
POST /api/v1/apps/{app_id}/security/scan
  - Runs `npm audit` in app workspace
  - Returns vulnerability report
  - Stores results in app metadata

GET /api/v1/apps/{app_id}/security/status
  - Returns last scan date, vulnerability counts by severity
  - { lastScan: timestamp, critical: 0, high: 2, moderate: 5, low: 10 }
```

**Scheduled scanning:**
- Background job scans all apps periodically (daily/weekly)
- Notifies app owners of new vulnerabilities
- Updates security status in database

##### B. SDK & Core Library Updates

**Challenge**: Apps have local `node_modules` with potentially outdated SDK

**Option 1: CDN-hosted SDK (Recommended)**
- Serve SDK from central URL instead of bundling
- Apps always get latest SDK automatically
- `<script src="/api/v1/sdk/sam.js"></script>` or npm package pointing to CDN
- Breaking changes handled via versioned endpoints (`/api/v1/sdk/v2/sam.js`)

**Option 2: Update mechanism in AppAgent**
- New tool: `claude_code_update_dependencies`
- AppAgent can run `npm update @sam/sdk` when instructed
- Or automated: detect outdated SDK, prompt user to update

**Option 3: Workspace refresh**
- "Refresh dependencies" button in UI
- Copies latest `node_modules` from template to app
- Preserves app-specific dependencies
- Risk: may break apps that depend on specific versions

##### C. Deployment Gates

**Block deployment of vulnerable apps:**
```yaml
# Gateway config
security:
  block_deployment:
    critical: true      # Block if any critical vulnerabilities
    high: true          # Block if any high vulnerabilities
    moderate: false     # Allow moderate vulnerabilities
    low: false          # Allow low vulnerabilities
```

**Deployment flow:**
1. User triggers deploy
2. System runs `npm audit`
3. If vulnerabilities exceed threshold → deployment blocked
4. User must fix vulnerabilities before deploying

##### D. Database Schema Additions

```sql
-- Add to apps table or create separate table
ALTER TABLE apps ADD COLUMN security_last_scan BIGINT;
ALTER TABLE apps ADD COLUMN security_critical_count INTEGER DEFAULT 0;
ALTER TABLE apps ADD COLUMN security_high_count INTEGER DEFAULT 0;
ALTER TABLE apps ADD COLUMN security_moderate_count INTEGER DEFAULT 0;
ALTER TABLE apps ADD COLUMN security_low_count INTEGER DEFAULT 0;

-- Or detailed vulnerability tracking
CREATE TABLE app_vulnerabilities (
    id VARCHAR PRIMARY KEY,
    app_id VARCHAR NOT NULL,
    package_name VARCHAR(255) NOT NULL,
    vulnerability_id VARCHAR(100) NOT NULL,  -- CVE or npm advisory ID
    severity VARCHAR(20) NOT NULL,           -- critical, high, moderate, low
    title TEXT,
    fixed_in_version VARCHAR(50),
    detected_at BIGINT NOT NULL,
    resolved_at BIGINT,                      -- NULL if still present

    UNIQUE(app_id, vulnerability_id)
);
```

##### E. UI/UX Considerations

**App list view:**
- Security badge/icon showing vulnerability status
- Filter apps by security status
- Sort by "needs attention"

**App detail view:**
- Security panel showing vulnerability summary
- "Scan now" button
- List of vulnerabilities with fix suggestions
- "Update dependencies" action

**Notifications:**
- Alert app owners when new vulnerabilities found
- Weekly digest of security status across all apps

#### Open Questions

1. **Who can fix vulnerabilities?**
   - Only app owner?
   - Platform admins for critical issues?

2. **Auto-fix?**
   - Should we auto-update packages with security patches?
   - Risk of breaking apps vs security

3. **Grace period?**
   - How long before blocking deployment?
   - Allow exceptions for low-risk apps?

4. **Scanning tool choice:**
   - `npm audit` (built-in, npm-specific)
   - `snyk` (more comprehensive, requires API key)
   - `trivy` (container + dependencies)
   - GitHub Dependabot integration?

---

## Implementation Priorities

### Phase 1: Persist Storage to DB (Essential)
- [ ] Create `app_storage` table
- [ ] Migrate from in-memory to DB-backed storage
- [ ] Maintain backward compatibility with current SDK
- [ ] Add Alembic migration

### Phase 2: Permission Levels (High Value)
- [ ] Add `permission` field to storage entries
- [ ] Implement permission checking in storage router
- [ ] Update SDK with `scope` and `permission` options
- [ ] Update CLAUDE.md documentation

### Phase 3: Manager Role (Medium Value)
- [ ] Add `MANAGER` to AppRole enum (or use existing `owner` role)
- [ ] Add admin endpoint for viewing all user data
- [ ] Add UI for managers to browse user data

### Phase 4: Structured Storage (Future/TBD)
- [ ] Evaluate need based on actual app requirements
- [ ] Choose approach (SQLite per-app vs migrations vs schema-on-write)
- [ ] Implement if warranted

### Phase 5: Library Security & Vulnerability Management (High Priority)
- [ ] Design approach for detecting vulnerable dependencies in apps
- [ ] Implement automated scanning (npm audit or similar)
- [ ] Create mechanism to update SDK and core libraries in existing apps
- [ ] Add security status to app metadata (last scan, vulnerabilities found)
- [ ] Consider blocking deployment of apps with critical vulnerabilities
- [ ] Document upgrade path for app owners

### Phase 6: Multi-Model LLM Support (High Value)
- [ ] Design LLM provider abstraction layer
- [ ] Add gateway configuration for multiple providers
- [ ] Create `/api/v1/llm/models` endpoint to list available models
- [ ] Create `/api/v1/llm/complete` endpoint with model selection
- [ ] Add `SAM.llm` namespace to SDK (list, complete, ask)
- [ ] Add postMessage handlers in useSamSdkHost.ts
- [ ] Implement streaming support for LLM responses
- [ ] Add access control (tier-based or allowlist)
- [ ] Add usage tracking/logging
- [ ] Update CLAUDE.md documentation

---

## Open Questions

1. **Namespace collisions**: If user A creates shared key "config" and user B wants to create the same, what happens?
   - First writer wins?
   - Require unique prefix per user for shared keys?
   - Owners can overwrite anyone's keys?

2. **Data retention**: When a user is removed from an app, what happens to their private data?
   - Delete immediately?
   - Retain for X days?
   - Transfer to owner?

3. **Audit trail**: Should we log who accessed/modified what data?
   - Useful for compliance and debugging
   - Adds storage overhead

4. **Quotas**: Should we limit storage per user/app?
   - Prevent runaway storage usage
   - Per-user limits vs per-app limits?

5. **Encryption**: Should private data be encrypted at rest?
   - Per-user keys?
   - App-level encryption?

---

## Related Files

- `src/solace_agent_mesh/gateway/http_sse/routers/storage.py` - Storage endpoints
- `src/solace_agent_mesh/gateway/http_sse/repository/models/app_model.py` - App model
- `src/solace_agent_mesh/gateway/http_sse/repository/models/app_user_model.py` - App roles
- `packages/sam-sdk/src/client.ts` - SDK storage implementation
- `client/webui/frontend/src/lib/hooks/useSamSdkHost.ts` - SDK host (postMessage handler)
- `docker/claude-code-sam-app/template/CLAUDE.md` - SDK documentation for apps

---

*Created: 2025-12-16*
*Author: Ed (via Claude Code)*
