# Service Configuration

Configures shared services for session storage, artifact management, and data processing. Services provide essential infrastructure for agent operations.

## Overview

Service configuration includes:
- **Session Service** - Conversation history and context persistence
- **Artifact Service** - File and data storage
- **Data Tools Config** - Data analysis optimization

## Session Service

Manages conversation history and context across agent interactions.

### Configuration Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | String | Yes | - | Storage type: `"memory"` or `"sql"` |
| `database_url` | String | Yes (sql) | - | Database connection string |
| `default_behavior` | String | No | `"PERSISTENT"` | `"PERSISTENT"` or `"RUN_BASED"` |

### Memory Storage

Stores sessions in memory (lost on restart):

```yaml
session_service:
  type: "memory"
  default_behavior: "PERSISTENT"
```

**Use Cases**:
- Development and testing
- Temporary sessions
- Stateless agents

**Limitations**:
- Data lost on restart
- Not suitable for production
- No persistence across instances

### SQL Storage

Stores sessions in database (persistent):

```yaml
session_service:
  type: "sql"
  database_url: "${DATABASE_URL}"
  default_behavior: "PERSISTENT"
```

**Use Cases**:
- Production deployments
- Multi-instance setups
- Long-term conversation history

**Supported Databases**:
- SQLite
- PostgreSQL
- MySQL

### Database URL Formats

#### SQLite

```bash
# Relative path
DATABASE_URL="sqlite:///./sessions.db"

# Absolute path
DATABASE_URL="sqlite:////tmp/sessions.db"
```

#### PostgreSQL

```bash
DATABASE_URL="postgresql://user:password@localhost:5432/dbname"

# With SSL
DATABASE_URL="postgresql://user:password@host:5432/db?sslmode=require"
```

#### MySQL

```bash
DATABASE_URL="mysql://user:password@localhost:3306/dbname"

# With charset
DATABASE_URL="mysql://user:password@host:3306/db?charset=utf8mb4"
```

### Session Behaviors

| Behavior | Description | Use Case |
|----------|-------------|----------|
| `PERSISTENT` | Sessions persist across runs | Production, user conversations |
| `RUN_BASED` | New session each run | Testing, isolated executions |

### Examples

#### Development Setup

```yaml
session_service:
  type: "memory"
  default_behavior: "PERSISTENT"
```

#### Production Setup

```yaml
session_service:
  type: "sql"
  database_url: "${DATABASE_URL}"
  default_behavior: "PERSISTENT"
```

#### Shared Configuration

```yaml
shared_config:
  - services:
      session_service: &default_session_service
        type: "sql"
        database_url: "${DATABASE_URL}"
        default_behavior: "PERSISTENT"
```

Reference in agent:

```yaml
app_config:
  session_service: *default_session_service
```

## Artifact Service

Manages files and data created by agents.

### Configuration Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | String | Yes | - | Storage type: `"memory"`, `"filesystem"`, `"s3"`, `"gcs"` |
| `base_path` | String | Yes (filesystem) | - | Base directory path |
| `bucket_name` | String | Yes (s3/gcs) | - | Cloud storage bucket name |
| `region` | String | No (s3) | - | AWS region |
| `endpoint_url` | String | No (s3) | - | Custom S3-compatible endpoint |

### Memory Storage

Stores artifacts in memory (temporary):

```yaml
artifact_service:
  type: "memory"
```

**Use Cases**:
- Quick testing
- Temporary data
- Development

**Limitations**:
- Data lost on restart
- Limited by RAM
- Not for production

### Filesystem Storage

Stores artifacts on local disk:

```yaml
artifact_service:
  type: "filesystem"
  base_path: "/tmp/sam-artifacts"
```

**Use Cases**:
- Local development
- Single-instance deployments
- Simple setups

**Limitations**:
- Not shared across instances
- Requires local storage
- Manual backup needed

**Storage Structure**:
```
/tmp/sam-artifacts/
├── app-name/
│   └── user-id/
│       ├── session-id/
│       │   └── file.pdf/
│       │       ├── 0          # Version 0
│       │       ├── 0.metadata
│       │       ├── 1          # Version 1
│       │       └── 1.metadata
```

### S3 Storage (AWS)

Stores artifacts in Amazon S3:

```yaml
artifact_service:
  type: "s3"
  bucket_name: "my-artifacts-bucket"
  region: "us-west-2"
```

**Environment Variables**:
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-west-2"
```

**Use Cases**:
- Production deployments
- AWS infrastructure
- Scalable storage

**Required IAM Permissions**:
- `s3:GetObject`
- `s3:PutObject`
- `s3:DeleteObject`
- `s3:ListBucket`

### S3-Compatible Storage

Stores artifacts in S3-compatible services:

```yaml
artifact_service:
  type: "s3"
  bucket_name: "my-bucket"
  endpoint_url: "${S3_ENDPOINT_URL}"
```

**Environment Variables**:
```bash
export S3_ENDPOINT_URL="https://storage.example.com"
export S3_ACCESS_KEY_ID="your-access-key"
export S3_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
```

**Compatible Services**:
- MinIO
- Ceph
- DigitalOcean Spaces
- Wasabi
- Backblaze B2

### Google Cloud Storage

Stores artifacts in GCS:

```yaml
artifact_service:
  type: "gcs"
  bucket_name: "my-artifacts-bucket"
```

**Environment Variables**:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

**Use Cases**:
- Google Cloud deployments
- GCP infrastructure
- Managed storage

**Required Permissions**:
- `roles/storage.objectViewer`
- `roles/storage.objectCreator`
- `roles/storage.objectDeleter`

### Examples

#### Development

```yaml
artifact_service:
  type: "filesystem"
  base_path: "/tmp/sam-artifacts"
```

#### Production (AWS)

```yaml
artifact_service:
  type: "s3"
  bucket_name: "${S3_BUCKET_NAME}"
  region: "${AWS_REGION}"
```

#### Production (GCP)

```yaml
artifact_service:
  type: "gcs"
  bucket_name: "${GCS_BUCKET_NAME}"
```

#### Shared Configuration

```yaml
shared_config:
  - services:
      artifact_service: &default_artifact_service
        type: "s3"
        bucket_name: "${S3_BUCKET_NAME}"
        region: "${AWS_REGION}"
```

## Data Tools Configuration

Optimizes data analysis and processing operations.

### Configuration Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `max_rows_to_analyze` | Integer | No | `1000` | Maximum rows for analysis |
| `enable_query_caching` | Boolean | No | `true` | Cache query results |
| `query_timeout_seconds` | Integer | No | `30` | Query execution timeout |
| `max_file_size_mb` | Integer | No | `100` | Maximum file size |
| `supported_formats` | List | No | All | Supported file formats |

### Basic Configuration

```yaml
data_tools_config:
  max_rows_to_analyze: 5000
  enable_query_caching: true
  query_timeout_seconds: 60
```

### Advanced Configuration

```yaml
data_tools_config:
  max_rows_to_analyze: 10000
  enable_query_caching: true
  query_timeout_seconds: 120
  max_file_size_mb: 500
  supported_formats:
    - "csv"
    - "xlsx"
    - "json"
    - "parquet"
  cache_ttl_seconds: 3600
  enable_parallel_processing: true
```

### Shared Configuration

```yaml
shared_config:
  - services:
      data_tools_config: &default_data_tools_config
        max_rows_to_analyze: 5000
        enable_query_caching: true
        query_timeout_seconds: 60
```

## Complete Examples

### Development Configuration

```yaml
shared_config:
  - services:
      # Memory-based session storage
      session_service: &default_session_service
        type: "memory"
        default_behavior: "PERSISTENT"
      
      # Filesystem artifact storage
      artifact_service: &default_artifact_service
        type: "filesystem"
        base_path: "/tmp/sam-artifacts"
      
      # Basic data tools config
      data_tools_config: &default_data_tools_config
        max_rows_to_analyze: 1000
        enable_query_caching: true
```

### Production Configuration (AWS)

```yaml
shared_config:
  - services:
      # SQL session storage
      session_service: &default_session_service
        type: "sql"
        database_url: "${DATABASE_URL}"
        default_behavior: "PERSISTENT"
      
      # S3 artifact storage
      artifact_service: &default_artifact_service
        type: "s3"
        bucket_name: "${S3_BUCKET_NAME}"
        region: "${AWS_REGION}"
      
      # Optimized data tools
      data_tools_config: &default_data_tools_config
        max_rows_to_analyze: 10000
        enable_query_caching: true
        query_timeout_seconds: 120
```

### Production Configuration (GCP)

```yaml
shared_config:
  - services:
      # PostgreSQL session storage
      session_service: &default_session_service
        type: "sql"
        database_url: "${POSTGRES_URL}"
        default_behavior: "PERSISTENT"
      
      # GCS artifact storage
      artifact_service: &default_artifact_service
        type: "gcs"
        bucket_name: "${GCS_BUCKET_NAME}"
      
      # Data tools config
      data_tools_config: &default_data_tools_config
        max_rows_to_analyze: 5000
        enable_query_caching: true
```

### Multi-Environment Configuration

```yaml
# Development
shared_config_dev:
  - services:
      session_service: &dev_session_service
        type: "memory"
      artifact_service: &dev_artifact_service
        type: "filesystem"
        base_path: "/tmp/dev-artifacts"

# Production
shared_config_prod:
  - services:
      session_service: &prod_session_service
        type: "sql"
        database_url: "${PROD_DATABASE_URL}"
      artifact_service: &prod_artifact_service
        type: "s3"
        bucket_name: "${PROD_S3_BUCKET}"
        region: "us-west-2"
```

## Service Coordination

All agents and gateways must use the same artifact service:

```yaml
# WebUI Gateway
app_config:
  artifact_service: *default_artifact_service

# Agent 1
app_config:
  artifact_service: *default_artifact_service

# Agent 2
app_config:
  artifact_service: *default_artifact_service
```

Session services can be different per agent:

```yaml
# Agent 1 - SQL storage
app_config:
  session_service:
    type: "sql"
    database_url: "${AGENT1_DB_URL}"

# Agent 2 - Memory storage
app_config:
  session_service:
    type: "memory"
```

## Best Practices

### 1. Use SQL for Production Sessions

```yaml
# Production
session_service:
  type: "sql"
  database_url: "${DATABASE_URL}"

# Not for production
session_service:
  type: "memory"
```

### 2. Use Cloud Storage for Production Artifacts

```yaml
# Production
artifact_service:
  type: "s3"
  bucket_name: "${S3_BUCKET_NAME}"

# Development only
artifact_service:
  type: "filesystem"
```

### 3. Shared Artifact Service

All components must use the same artifact service:

```yaml
shared_config:
  - services:
      artifact_service: &default_artifact_service
        type: "s3"
        bucket_name: "${S3_BUCKET_NAME}"
```

### 4. Environment Variables for Credentials

```yaml
# Good
database_url: "${DATABASE_URL}"
bucket_name: "${S3_BUCKET_NAME}"

# Bad - never hardcode
database_url: "postgresql://user:pass@host/db"
```

### 5. Appropriate Data Limits

```yaml
data_tools_config:
  max_rows_to_analyze: 5000  # Balance performance and capability
  query_timeout_seconds: 60   # Prevent hanging queries
```

## Troubleshooting

### Session Storage Issues

**Error**: `Failed to connect to database`

**Solutions**:
1. Verify DATABASE_URL is correct
2. Check database is running
3. Verify credentials
4. Test connection independently

### Artifact Storage Issues

**Error**: `Failed to access storage`

**Solutions**:
1. Verify storage backend is accessible
2. Check credentials (AWS/GCS)
3. Verify bucket exists
4. Check permissions

### Performance Issues

**Issue**: Slow data processing

**Solutions**:
1. Increase `max_rows_to_analyze`
2. Enable query caching
3. Increase timeout values
4. Optimize database queries

## Related Documentation

- [Shared Configuration](./shared-configuration.md) - Defining services in shared config
- [Agent Configuration](./agent-configuration.md) - Using services in agents
- [Gateway Configuration](./gateway-configuration.md) - Gateway service usage
- [Environment Variables](./environment-variables.md) - Service-related variables
- [Best Practices](./best-practices.md) - Service configuration guidelines