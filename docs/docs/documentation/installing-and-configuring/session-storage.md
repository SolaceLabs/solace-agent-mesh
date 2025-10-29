---
title: Session Storage
sidebar_position: 40
---

# Configuring Session Storage

This guide explains how to configure session persistence in Agent Mesh, allowing user conversations to survive application restarts and enabling rich conversation history.

## Understanding Sessions

Agent Mesh maintains user sessions to track conversations across multiple interactions. A session represents a continuous conversation between a user and your agents, preserving context and history across multiple turns.

Sessions consist of two complementary storage layers:

**Web Session Layer (Always Active)**: Starlette's SessionMiddleware maintains a signed session cookie that travels with each HTTP request. This layer stores the user's A2A Client ID, session identifier, and authentication tokens. This layer persists for the duration of the browser session.

**Database Layer (Optional)**: When enabled, Agent Mesh stores session metadata and chat history in a SQL database. This layer enables conversations to persist beyond cookie expiration and survive application restarts.

## Ephemeral vs Persistent Mode

Agent Mesh supports two session storage modes depending on your deployment needs.

### Ephemeral Mode (Default)

Ephemeral mode relies exclusively on signed cookies to maintain sessions. No database storage occurs.

**Characteristics:**
- Sessions stored only in HTTP cookies
- Data lost when cookies expire or browser closes
- No external database required
- Lightweight and suitable for stateless deployments
- Fastest mode (no database queries)

**Use this when:**
- Building and testing locally
- Running stateless deployments
- Starting with Agent Mesh for the first time
- You don't need conversation history to persist

**Configuration:**
```yaml
session_service:
  type: "memory"
```

Or simply omit the `session_service` configuration entirely (memory is the default).

### Persistent Mode

Persistent mode stores session metadata and conversation history in a SQL database, enabling sessions to survive application restarts and providing access to previous conversations.

**Characteristics:**
- Sessions stored in database (SQLite, PostgreSQL, or MySQL)
- Data persists indefinitely until explicitly deleted
- Survives application restarts and crashes
- Enables multi-turn conversation history
- Slightly higher latency due to database queries

**Use this when:**
- Running in production
- Need to preserve conversations after restarts
- Building multi-turn interactive experiences
- Require conversation audit trails
- Running multiple instances behind a load balancer

**Configuration:**
```yaml
session_service:
  type: "sql"
  database_url: "${WEB_UI_GATEWAY_DATABASE_URL, sqlite:///webui-gateway.db}"
```

## Enabling Persistent Sessions

To enable persistent session storage, configure two environment variables:

**SESSION_SECRET_KEY** (Required)
A secret key used to sign session cookies. This must be the same across all instances if running multiple pods or processes.

```bash
export SESSION_SECRET_KEY="your-secret-key-here"
```

**WEB_UI_GATEWAY_DATABASE_URL** (Required for persistent mode)
The database connection string specifying where to store session data.

```bash
export WEB_UI_GATEWAY_DATABASE_URL="postgresql://user:pass@localhost:5432/sam_db"
```

Then update your gateway configuration:

```yaml
session_service:
  type: "sql"
  database_url: "${WEB_UI_GATEWAY_DATABASE_URL}"
```

## Configuring Database Backends

Agent Mesh supports three SQL database backends for session storage. Choose based on your deployment environment and scale requirements.

### SQLite (Development)

SQLite stores session data in a local file, making it ideal for development and testing without requiring external infrastructure.

**Configuration:**
```yaml
session_service:
  type: "sql"
  database_url: "sqlite:///webui-gateway.db"
```

**Environment Variable:**
```bash
export WEB_UI_GATEWAY_DATABASE_URL="sqlite:///webui-gateway.db"
```

**Advantages:**
- No external dependencies
- Instant setup
- File-based, transparent storage location
- Perfect for local development

**Limitations:**
- Not suitable for production
- No built-in replication or backup
- Cannot be shared across multiple instances
- Limited concurrent connection handling

**Storage Location:**
Data is stored in `webui-gateway.db` in your working directory. You can customize the path:
```yaml
database_url: "sqlite:////absolute/path/to/webui-gateway.db"
```

### PostgreSQL (Production)

PostgreSQL provides a robust, scalable database suitable for production deployments. It offers excellent performance, reliability, and can be easily managed through cloud services or self-hosted installations.

**Configuration:**
```yaml
session_service:
  type: "sql"
  database_url: "postgresql://user:password@host:5432/sam_db"
```

**Environment Variable:**
```bash
export WEB_UI_GATEWAY_DATABASE_URL="postgresql://user:password@localhost:5432/sam_db"
```

**Advantages:**
- Production-grade reliability
- Horizontal scalability (multiple instances share same database)
- Advanced features (replication, backups, monitoring)
- Cloud-managed options available (AWS RDS, Google Cloud SQL, Azure Database)
- Connection pooling support
- ACID compliance

**Connection String Format:**
```
postgresql://[user[:password]@][netloc][:port][/dbname][?param1=value1&...]
```

**Example with all parameters:**
```bash
postgresql://sam_user:secure_password@db.example.com:5432/sam_database
```

### MySQL/MariaDB (Production)

MySQL and MariaDB are popular open-source relational databases suitable for production deployments.

**Configuration:**
```yaml
session_service:
  type: "sql"
  database_url: "mysql+pymysql://user:password@host:3306/sam_db"
```

**Environment Variable:**
```bash
export WEB_UI_GATEWAY_DATABASE_URL="mysql+pymysql://user:password@localhost:3306/sam_db"
```

**Advantages:**
- Open-source and widely available
- Strong community support
- Cloud-managed options available
- Good performance characteristics
- ACID compliance (with InnoDB)

**Connection String Format:**
```
mysql+pymysql://[user[:password]@][host][:port]/[database]
```

**Note:** Agent Mesh uses `pymysql` as the Python driver. Other drivers like `mysqlconnector` are also supported but require installation.

## Migrating from Ephemeral to Persistent

Moving from ephemeral mode to persistent mode is straightforward and can be done without losing existing sessions.

### Step 1: Set Environment Variables

First, configure your database connection and secret key:

```bash
export SESSION_SECRET_KEY="your-secret-key"
export WEB_UI_GATEWAY_DATABASE_URL="postgresql://user:pass@localhost:5432/sam_db"
```

For SQLite:
```bash
export WEB_UI_GATEWAY_DATABASE_URL="sqlite:///webui-gateway.db"
```

### Step 2: Update Configuration

Update your gateway configuration file:

```yaml
session_service:
  type: "sql"
  database_url: "${WEB_UI_GATEWAY_DATABASE_URL}"
```

### Step 3: Restart Application

When the application restarts, it automatically runs database migrations to create necessary tables:

- `sessions` table - Stores session metadata
- `chat_tasks` table - Stores conversation messages
- Supporting indexes for performance

These migrations run automatically on startup. No manual database setup is required.

### Step 4: Verify Migration

After restart, verify that persistence is working:

1. Start a conversation with an agent
2. Send a message
3. Restart the application
4. Refresh your browser
5. The session and conversation history should still be visible

### Considerations During Migration

**Existing cookies remain valid** - Sessions stored only in cookies from before the migration will continue to work as long as the cookies haven't expired.

**Database initialization** - The database migrations run once on first startup. Subsequent restarts simply connect to the existing database.

**No data loss** - Migration only adds new storage capacity; it doesn't affect existing sessions.

## Data Retention and Automatic Cleanup

When using persistent mode, you can configure automatic cleanup of old session data to manage storage and maintain privacy.

**Configuration:**
```yaml
data_retention:
  enabled: true
  task_retention_days: 90          # Keep chat tasks for 90 days
  feedback_retention_days: 90      # Keep feedback for 90 days
  cleanup_interval_hours: 24       # Run cleanup every 24 hours
```

**How It Works:**
- Every `cleanup_interval_hours`, the system runs a cleanup job
- Tasks older than `task_retention_days` are deleted
- Feedback older than `feedback_retention_days` is deleted
- Sessions themselves are retained unless explicitly deleted

**Environment Variables** (Optional override):
```bash
export DATA_RETENTION_ENABLED=true
export DATA_RETENTION_TASK_DAYS=90
export DATA_RETENTION_FEEDBACK_DAYS=90
export DATA_RETENTION_CLEANUP_HOURS=24
```

**Why This Matters:**
- **Privacy**: Automatically remove old conversations per data retention policies
- **Storage**: Prevent unlimited database growth
- **Compliance**: Meet regulatory requirements for data deletion

## Verification and Testing

After configuring session storage, verify that everything works correctly.

### For Ephemeral Mode

1. Start a conversation: Send a message to an agent
2. Check browser cookies: Developer tools → Application → Cookies
3. You should see `session` and related cookies with session data

### For Persistent Mode

1. Start a conversation and send a message
2. Verify database connection: Check application logs for any database errors
3. Confirm tables created: Query your database
   ```sql
   SELECT * FROM sessions;
   SELECT * FROM chat_tasks;
   ```
4. Test persistence:
   - Start a conversation
   - Send a message
   - Stop the application
   - Restart the application
   - Refresh browser and verify conversation history is visible

## Troubleshooting

### Database Connection Errors

**Error**: `Failed to connect to database` or `could not connect to server`

**Solutions:**
- Verify database URL format is correct
- Confirm database server is running and accessible
- Check network connectivity (firewalls, security groups)
- Verify credentials have correct permissions
- For PostgreSQL, ensure database exists (create it first if needed)

### Migration Errors

**Error**: `Alembic migration failed` or `Database schema error`

**Solutions:**
- Check that database user has permissions to create tables
- Verify no other instances are running migrations simultaneously
- For existing databases, ensure they don't have conflicting schemas
- Check application logs for detailed error messages

### Sessions Not Persisting

**Error**: Sessions lost after restart or don't appear in new browser tabs

**Solution:**
- Confirm `session_service.type` is set to `"sql"` (not `"memory"`)
- Verify `database_url` environment variable is set
- Check database connectivity
- Verify tables were created by querying the database

### Performance Issues

**Slow response times after enabling persistence:**

**Solutions:**
- Enable connection pooling (configured automatically for PostgreSQL/MySQL)
- Check database query performance using slow query logs
- Verify database indexes exist
- Consider database scaling if traffic increases

## Next Steps

After configuring session storage, you may want to:

- Configure [Artifact Storage](./artifact-storage.md) for agent-generated files
- Set up [monitoring and observability](../deploying/observability.md) to track session activity
- Review [deployment options](../deploying/deployment-options.md) for production considerations
- Implement additional [logging configuration](../deploying/logging.md) for troubleshooting
