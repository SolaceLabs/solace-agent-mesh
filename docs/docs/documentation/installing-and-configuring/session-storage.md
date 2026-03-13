---
title: Session Storage
sidebar_position: 350
---

# Configuring Session Storage

This guide explains how to configure session storage in Agent Mesh, enabling user conversations to persist across restarts and providing rich conversation history for both the WebUI Gateway and individual agents.

## Understanding Session Storage Architecture

Agent Mesh uses a distributed session architecture where the WebUI Gateway and agents maintain separate but coordinated session storage systems connected via session IDs.

### How Session Storage Works

When a user starts a conversation:

1. The WebUI Gateway generates a session ID (`web-session-<UUID>`)
2. The WebUI Gateway sends the session ID to the agent with each message
3. The agent receives the session ID and uses it to look up or store its own session context
4. The WebUI Gateway and agent store different data in their own databases

This architecture allows:
- The WebUI Gateway to show conversation history in the user interface
- Agents to maintain their own conversation context and memory
- Multiple agents in a conversation to share the same session ID while maintaining isolated storage

### Where Data Is Stored

The WebUI Gateway database stores:
- Session metadata (session ID, user ID, timestamps)
- Chat history displayed in the UI
- Message bubbles and formatted responses
- Task metadata (agent names, status, feedback)

Each agent database stores:
- Agent's conversation context and memory
- Message history from the agent's perspective
- Agent internal state and tool execution history
- Session events and actions

These are separate databases. Each agent has its own independent database (with separate credentials), and the WebUI Gateway has its own database. They coordinate via the session ID.

## Session Storage Scenarios

The behavior of your deployment depends on whether the WebUI Gateway and agents have persistent storage enabled. Understanding these scenarios helps you configure correctly for your needs.

### Scenario A: Both WebUI Gateway and Agents Have Persistence (Recommended)

```yaml
# WebUI Gateway Configuration
session_service:
  type: "sql"
  database_url: "${WEB_UI_GATEWAY_DATABASE_URL}"
```

```yaml
# Agent Configuration
session_service:
  type: "sql"
  database_url: "${AGENT_DATABASE_URL, sqlite:///agent-session.db}"
  default_behavior: "PERSISTENT"
```

What happens:
- User sees full chat history in the UI after restarts
- Agents remember full conversation context across restarts
- Multi-turn conversations work perfectly
- Browser refresh preserves everything

Use this for:
- Production deployments
- Multi-turn interactive experiences
- Any deployment where users expect conversation continuity

### Scenario B: Neither Has Persistence (Ephemeral Only)

```yaml
# WebUI Gateway Configuration
session_service:
  type: "memory"
```

```yaml
# Agent Configuration
session_service:
  type: "memory"
```

What happens:
- Sessions exist only in browser cookies
- No conversation history after browser refresh
- No persistence across restarts
- Everything lost when cookies expire

Use this for:
- Local development and testing only
- Rapid prototyping
- Scenarios where no persistence is needed

Do not use for:
- Production deployments
- Multi-turn conversations
- Any scenario requiring conversation continuity

### Scenario C: Only Agents Have Persistence (Limited Experience)

```yaml
# WebUI Gateway Configuration
session_service:
  type: "memory"  # No database
```

```yaml
# Agent Configuration
session_service:
  type: "sql"
  database_url: "${AGENT_DATABASE_URL}"
  default_behavior: "PERSISTENT"
```

What happens:
- User sees no chat history in the UI after browser refresh
- Agents maintain conversation context internally
- Conversation works but UI does not show history

Use this for:
- Rare scenarios where UI history is not needed
- Headless or API-only deployments without WebUI

### Scenario D: Only WebUI Gateway Has Persistence (Broken Experience)

```yaml
# WebUI Gateway Configuration
session_service:
  type: "sql"
  database_url: "${WEB_UI_GATEWAY_DATABASE_URL}"
```

```yaml
# Agent Configuration
session_service:
  type: "memory"  # No database
```

:::warning Broken Experience
What happens:
- User sees full chat history in the UI
- Agent receives session ID but has no database to store context
- Agent processes current message but forgets previous turns
- The UI shows history, but the agent acts like every message is the first one

The UI misleads the user by showing conversation history that the agent cannot actually use. Users get frustrated when the agent does not remember what they just said.

Avoid this scenario because it creates a confusing and broken user experience.
:::

## Configuring WebUI Gateway Session Storage

The WebUI Gateway requires two configuration elements to enable persistent session storage.

### Environment Variables

`SESSION_SECRET_KEY` (Required)

A secret key used to sign session cookies. This must be the same across all instances if you run multiple pods or processes.

```bash
export SESSION_SECRET_KEY="your-secret-key-here"
```

`WEB_UI_GATEWAY_DATABASE_URL` (Required for persistent mode)

The database connection string specifying where to store session data.

```bash
export WEB_UI_GATEWAY_DATABASE_URL="postgresql://user:pass@host:5432/webui_db"
```

`PLATFORM_DATABASE_URL` (Optional, required for enterprise features)

The database connection string for platform features such as agents, connectors, and deployments. If not configured, platform endpoints return 501 (Not Implemented).

```bash
export PLATFORM_DATABASE_URL="postgresql://user:pass@host:5432/platform_db"
```

For development, you can use SQLite:

```bash
export PLATFORM_DATABASE_URL="sqlite:///platform.db"
```

### Gateway Configuration File

Update your WebUI Gateway configuration to use the database:

```yaml
session_service:
  type: "sql"
  database_url: "${WEB_UI_GATEWAY_DATABASE_URL}"

platform_service:
  database_url: "${PLATFORM_DATABASE_URL, sqlite:///platform.db}"
```

### Database Backend Options

#### SQLite (Development)

SQLite stores session data in a local file, ideal for development without external infrastructure.

```yaml
session_service:
  type: "sql"
  database_url: "sqlite:///webui-gateway.db"
```

```bash
export WEB_UI_GATEWAY_DATABASE_URL="sqlite:///webui-gateway.db"
```

Advantages:
- No external dependencies
- Instant setup
- Perfect for local development

Limitations:
- Not suitable for production
- Cannot be shared across multiple instances
- No built-in replication or backup

#### PostgreSQL (Production)

PostgreSQL provides robust, scalable database suitable for production deployments.

```yaml
session_service:
  type: "sql"
  database_url: "postgresql://user:password@host:5432/webui_db"
```

```bash
export WEB_UI_GATEWAY_DATABASE_URL="postgresql://webui_user:secure_pass@db.example.com:5432/webui_db"
```

Advantages:
- Production-grade reliability
- Horizontal scalability (multiple instances share same database)
- Cloud-managed options (AWS RDS, Google Cloud SQL, Azure Database)
- Connection pooling support
- ACID compliance

Connection string format:
```
postgresql://[user[:password]@][host][:port]/[dbname][?param1=value1&...]
```

#### MySQL/MariaDB (Production)

MySQL and MariaDB are popular open-source databases suitable for production.

```yaml
session_service:
  type: "sql"
  database_url: "mysql+pymysql://user:password@host:3306/webui_db"
```

```bash
export WEB_UI_GATEWAY_DATABASE_URL="mysql+pymysql://webui_user:secure_pass@db.example.com:3306/webui_db"
```

Advantages:
- Open-source and widely available
- Strong community support
- Cloud-managed options available
- ACID compliance (with InnoDB)

Connection string format:
```
mysql+pymysql://[user[:password]@][host][:port]/[database]
```

Agent Mesh uses `pymysql` as the Python driver.

## Configuring Agent Session Storage

Agents use the ADK (Agent Development Kit) session configuration system. Each agent can be configured independently with its own database.

### Agent Configuration File

Add the `session_service` section to your agent's YAML configuration:

```yaml
session_service:
  type: "sql"
  database_url: "${AGENT_DATABASE_URL, sqlite:///agent-session.db}"
  default_behavior: "PERSISTENT"
```

Parameters:
- `type`: `"memory"` (ephemeral) or `"sql"` (persistent)
- `database_url`: Connection string for the agent's database
- `default_behavior`: `"PERSISTENT"` (reuse sessions) or `"RUN_BASED"` (new session per run)

### Environment Variables

Each agent can have its own database credentials:

```bash
export AGENT_DATABASE_URL="postgresql://agent_user:agent_pass@host:5432/agent_db"
```

Or use a default with fallback in the YAML:

```yaml
database_url: "${AGENT_DATABASE_URL, sqlite:///agent-session.db}"
```

### Database Isolation Between Agents

Each agent should have:
- Its own separate database (not just a schema)
- Its own separate credentials (username and password)
- Complete isolation from other agents' data

Example for two agents:

```yaml
# Agent A Configuration
session_service:
  type: "sql"
  database_url: "${AGENT_A_DATABASE_URL, sqlite:///agent-a.db}"
  default_behavior: "PERSISTENT"
```

```yaml
# Agent B Configuration
session_service:
  type: "sql"
  database_url: "${AGENT_B_DATABASE_URL, sqlite:///agent-b.db}"
  default_behavior: "PERSISTENT"
```

```bash
# Environment variables for isolation
export AGENT_A_DATABASE_URL="postgresql://agent_a_user:pass@host:5432/agent_a_db"
export AGENT_B_DATABASE_URL="postgresql://agent_b_user:pass@host:5432/agent_b_db"
```

### Shared Configuration Pattern

If all agents should use the same session storage configuration, use YAML anchors:

```yaml
# Shared configuration
session_service: &default_session_service
  type: "sql"
  database_url: "${SESSION_DATABASE_URL, sqlite:///session.db}"
  default_behavior: "PERSISTENT"

# Agent references shared config
agents:
  - name: agent-a
    session_service: *default_session_service

  - name: agent-b
    session_service: *default_session_service
```

## Migrating from Ephemeral to Persistent

Moving from ephemeral mode to persistent mode can be done without losing active sessions.

### Step 1: Configure WebUI Gateway Database

Set the environment variables:

```bash
export SESSION_SECRET_KEY="your-secret-key"
export WEB_UI_GATEWAY_DATABASE_URL="postgresql://user:pass@host:5432/webui_db"
```

Update your WebUI Gateway configuration:

```yaml
session_service:
  type: "sql"
  database_url: "${WEB_UI_GATEWAY_DATABASE_URL}"
```

### Step 2: Configure Agent Databases

For each agent, set the database URL:

```bash
export AGENT_DATABASE_URL="postgresql://agent_user:pass@host:5432/agent_db"
```

Update agent configuration:

```yaml
session_service:
  type: "sql"
  database_url: "${AGENT_DATABASE_URL}"
  default_behavior: "PERSISTENT"
```

### Step 3: Restart Application

When the application restarts:
- Database migrations run automatically
- Tables are created for session storage
- No manual database setup required

Tables created:
- `sessions` - Session metadata
- `chat_tasks` - Conversation messages
- Supporting indexes for performance

### Step 4: Verify Migration

Test that persistence is working:

1. Start a conversation with an agent
2. Send a message
3. Restart the application
4. Refresh your browser
5. Verify conversation history is visible
6. Send another message to the same agent
7. Verify agent remembers previous conversation context

### Migration Considerations

Existing cookies remain valid. Sessions stored only in cookies before migration continue to work until cookies expire.

Database initialization happens once on first startup. Subsequent restarts connect to the existing database.

Migration adds new storage without affecting existing sessions.

## Next Steps

After configuring session storage, you may want to:

- Configure [Artifact Storage](./artifact-storage.md) for agent-generated files
- Review [deployment options](../deploying/deployment-options.md) for production considerations
- Set up [monitoring and observability](../deploying/observability.md) to track session activity
