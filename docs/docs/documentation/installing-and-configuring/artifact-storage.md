---
title: Artifact Storage
sidebar_position: 360
---

# Configuring Artifact Storage

This guide explains how to configure storage for artifacts—files and data created by your agents—from development to production deployments.

## Understanding Artifacts

Artifacts are files and data created by agents during task execution. Examples include generated reports, analysis results, processed documents, or any files that agents produce for users. Agent Mesh provides built-in tools for agents to create, manage, and reference artifacts.

Key characteristics:
- Automatic versioning: Each time an artifact is updated, a new version is created (v0, v1, v2, etc.)
- User-scoped: Artifacts belong to specific users and sessions
- Retrievable: Users can access, download, and view artifact history
- Tool-driven: Agents use built-in tools to create and manage artifacts

### Artifact Storage vs Session Storage

Unlike session storage (which is separate for WebUI Gateway and each agent), artifact storage is shared across all agents and gateways in your deployment.

How it works:
- All agents and gateways connect to the same artifact storage backend
- Artifacts are scoped by `(user_id, session_id, app_name)` to maintain isolation
- Any agent or gateway can access artifacts within their scope
- This allows agents to share files and data within a conversation

Example:
```yaml
# WebUI Gateway and all agents share this artifact storage
artifact_service:
  type: "s3"
  bucket_name: "shared-artifacts-bucket"
  region: "us-west-2"
```

Contrast with session storage:
- Session storage: Each agent has its own separate database
- Artifact storage: All agents and gateways share the same storage backend

For session storage configuration, see [Session Storage](./session-storage.md).

### Multiple S3 Buckets for OpenAPI Connector Feature

> **Note:** The S3 bucket used for OpenAPI connector specifications is not for user or chat artifacts. For details on configuring the public S3 bucket for connector specs, see [Infrastructure Setup: S3 Buckets for OpenAPI Connector Specs](../enterprise/installation.md#infrastructure-setup-s3-buckets-for-openapi-connector-specs).

## Artifact Scoping

Artifact scoping controls how artifacts are organized and isolated within your storage backend. This determines which components can access which artifacts.

### Scope Types

Agent Mesh supports three artifact scope types:

| Scope Type | Description | Use Case |
|------------|-------------|----------|
| `namespace` | Artifacts scoped to namespace | Default; isolates artifacts by namespace |
| `app` | Artifacts scoped to application instance | Isolates artifacts per agent/gateway |
| `custom` | Custom scope identifier | Advanced use cases requiring custom isolation |

### Namespace Scope (Default)

Artifacts are organized by namespace, allowing all agents and gateways within the same namespace to share artifacts:

```yaml
artifact_service:
  type: "filesystem"
  base_path: "/tmp/artifacts"
  artifact_scope: "namespace"  # Default
```

### App Scope

Artifacts are isolated per application instance, preventing sharing between different agents or gateways:

```yaml
artifact_service:
  type: "filesystem"
  base_path: "/tmp/artifacts"
  artifact_scope: "app"
```

### Custom Scope

For advanced scenarios requiring custom isolation logic:

```yaml
artifact_service:
  type: "filesystem"
  base_path: "/tmp/artifacts"
  artifact_scope: "custom"
  artifact_scope_value: "my-custom-scope"
```

**Use Cases for Custom Scope:**
- Multi-tenant deployments with custom tenant identifiers
- Departmental isolation within an organization
- Environment-specific artifact separation (dev/staging/prod)
- Custom compliance or regulatory requirements

## Artifact Storage Backends

Agent Mesh supports multiple storage backends for artifacts. Choose based on your deployment environment and requirements.

| Backend | Best For | Production Ready | Setup Complexity |
|---------|----------|------------------|------------------|
| Filesystem | Local development | ❌ | Simple |
| S3 (AWS) | AWS deployments | ✅ | Medium |
| S3-Compatible API | On-premises, private cloud | ✅ | Medium |
| GCS | Google Cloud deployments | ✅ | Medium |

### Filesystem Storage (Default)

Filesystem storage saves artifacts to local disk directories. This is the default configuration and is suitable for development and local testing.

Characteristics:
- Artifacts stored in transparent directory structure
- Data persists across restarts
- Single instance only (not shared across pods)
- Simple backup (copy directories)

Use only for local development and single-machine deployments.

Configuration:
```yaml
artifact_service:
  type: "filesystem"
  base_path: "/tmp/sam-artifacts"
```

Storage structure:
```
/tmp/sam-artifacts/
├── app-name/
│   └── user-id/
│       ├── session-id/
│       │   ├── report.pdf/
│       │   │   ├── 0          (version 0 data)
│       │   │   ├── 0.metadata (version 0 metadata)
│       │   │   ├── 1          (version 1 data)
│       │   │   └── 1.metadata
│       │   └── data.csv/
│       │       ├── 0
│       │       └── 0.metadata
│       └── user/              (user-scoped artifacts)
│           └── config.json/
│               ├── 0
│               └── 0.metadata
```

### S3 (AWS)

S3 storage uses Amazon S3 for artifact persistence. This is the recommended production backend for AWS deployments.

Characteristics:
- Highly durable
- Scalable to any size
- Access from any location
- Automatic backups and redundancy
- IAM-based security

Configuration:
```yaml
artifact_service:
  type: "s3"
  bucket_name: "my-artifacts-bucket"
  region: "us-west-2"
```

Environment variables:
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-west-2"
```

IAM permissions required:

The credentials must have these permissions for the bucket:
- `s3:GetObject`
- `s3:PutObject`
- `s3:DeleteObject`
- `s3:ListBucket`

Example IAM policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-artifacts-bucket",
        "arn:aws:s3:::my-artifacts-bucket/*"
      ]
    }
  ]
}
```

### S3-Compatible API Endpoint

S3-compatible storage allows any storage service that implements the S3 API to work with Agent Mesh. This includes on-premises solutions and services from cloud providers other than AWS.

Characteristics:
- Works with any S3-compatible API implementation
- Custom endpoints for private or on-premises storage
- Same versioning and management as AWS S3
- Requires compatible storage service

Configuration:
```yaml
artifact_service:
  type: "s3"
  bucket_name: "my-artifacts-bucket"
  endpoint_url: "${S3_ENDPOINT_URL}"
```

Environment variables:
```bash
export S3_ENDPOINT_URL="https://storage.example.com"
export S3_ACCESS_KEY_ID="your-access-key"
export S3_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"  # Required but can be arbitrary for S3-compatible endpoints
```

Supported services:

This configuration works with any S3-compatible storage service, including self-hosted and cloud-provider solutions. Examples include storage services from various cloud providers and on-premises object storage systems.

### Google Cloud Storage (GCS)

GCS storage uses Google Cloud Storage for artifact persistence. This is the recommended backend for Google Cloud deployments.

Characteristics:
- High availability and durability
- Integration with Google Cloud ecosystem
- Scalable and managed by Google
- Fine-grained IAM controls

Configuration:
```yaml
artifact_service:
  type: "gcs"
  bucket_name: "my-artifacts-bucket"
```

Authentication:

GCS authentication uses Google Cloud Application Default Credentials. Set up via:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

Or configure via environment variables if you use workload identity in Kubernetes.

Permissions required:

The service account must have these roles on the bucket:
- `roles/storage.objectViewer`
- `roles/storage.objectCreator`
- `roles/storage.objectDeleter`

## Understanding Artifact Versioning

Agent Mesh automatically manages artifact versions, allowing users to access previous versions of files.

How versioning works:
- First artifact create: version 0
- Append or update: version 1 (automatic increment)
- Continue appending: version 2, 3, 4, etc.
- Versions persist independently

Example lifecycle:
```
Agent creates report.pdf
  → version 0 created

Agent appends more data to report.pdf
  → version 1 created (v0 still exists)

Agent appends additional data
  → version 2 created (v0 and v1 still exist)

User can access any version:
- Latest version (automatic)
- Specific version (v0, v1, v2)
- Version history (list all versions)
```

Metadata:

Each artifact version includes metadata:
```json
{
  "filename": "report.pdf",
  "mime_type": "application/pdf",
  "version": 0,
  "size_bytes": 2048,
  "timestamp": "2024-10-29T12:34:56Z"
}
```

## Configuring Artifact Storage

Choose your artifact storage backend based on your deployment environment.

### Development Setup

For local development and testing, use filesystem storage:

```yaml
artifact_service:
  type: "filesystem"
  base_path: "/tmp/sam-artifacts"
```

Create the base directory if it doesn't exist:
```bash
mkdir -p /tmp/sam-artifacts
```

### AWS Production Deployment

For production deployments on AWS:

1. **Create S3 Bucket:**
   ```bash
   aws s3 mb s3://my-artifacts-bucket --region us-west-2
   ```

2. **Configure IAM User or Role** with required permissions (see IAM Policy above)

3. **Configure Agent Mesh:**
   ```yaml
   artifact_service:
     type: "s3"
     bucket_name: "my-artifacts-bucket"
     region: "us-west-2"
   ```

4. **Set Environment Variables:**
   ```bash
   export AWS_ACCESS_KEY_ID="your-key"
   export AWS_SECRET_ACCESS_KEY="your-secret"
   export AWS_REGION="us-west-2"
   ```

### On-Premises or Private Cloud

For on-premises deployments using S3-compatible storage:

1. **Set Up S3-Compatible Storage** (ensure it's running and accessible)

2. **Create Bucket:** Use your storage system's administration tools

3. **Configure Agent Mesh:**
   ```yaml
   artifact_service:
     type: "s3"
     bucket_name: "my-bucket"
     endpoint_url: "${S3_ENDPOINT_URL}"
   ```

4. **Set Environment Variables:**
   ```bash
   export S3_ENDPOINT_URL="https://storage.example.com:9000"
   export S3_ACCESS_KEY_ID="your-access-key"
   export S3_SECRET_ACCESS_KEY="your-secret-key"
   export AWS_REGION="us-east-1"
   ```

### Google Cloud Deployment

For production deployments on Google Cloud:

1. **Create GCS Bucket:**
   ```bash
   gsutil mb gs://my-artifacts-bucket
   ```

2. **Set Up Service Account with required permissions**

3. **Configure Agent Mesh:**
   ```yaml
   artifact_service:
     type: "gcs"
     bucket_name: "my-artifacts-bucket"
   ```

4. **Set Up Authentication:**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
   ```

## Migrating Artifact Storage Backends

Moving from one artifact storage backend to another requires no special migration procedure—the system starts fresh with the new backend.

### Before Migration

Understand the implications:
- Existing artifacts stored in the old backend will not be accessible after switching
- New artifacts will be stored in the new backend
- If you need to preserve existing artifacts, export them first from the old storage

### Migration Steps

Step 1: Set up new storage backend

Create the new storage location:
- For filesystem: `mkdir -p /path/to/new/storage`
- For S3: Create bucket and set up credentials
- For GCS: Create bucket and set up service account

Step 2: Update configuration

Update your artifact service configuration:

From:
```yaml
artifact_service:
  type: "filesystem"
  base_path: "/old/path"
```

To:
```yaml
artifact_service:
  type: "s3"
  bucket_name: "my-bucket"
  region: "us-west-2"
```

Step 3: Set environment variables

Configure credentials for the new backend:
```bash
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_REGION="us-west-2"
```

Step 4: Restart application

When the application restarts, it will use the new backend for all subsequent artifact operations.

Step 5: Verify

Test artifact creation and retrieval:
1. Create a new artifact
2. Verify it appears in the new storage backend
3. Retrieve it through the API or agent tools

## Data Retention for Artifacts

Like session data, artifact storage can be configured with automatic cleanup policies.

Configuration:
```yaml
data_retention:
  enabled: true
  task_retention_days: 90
  cleanup_interval_hours: 24
```

How it works:
- Artifacts older than `task_retention_days` may be cleaned up
- Cleanup runs every `cleanup_interval_hours`
- Prevents unbounded storage growth

Check your specific artifact storage backend documentation for retention policies and best practices.

## Troubleshooting

### Backend Connectivity Issues

Error: `Failed to access storage` or `Connection refused`

Solutions:
- Verify storage backend is running and accessible
- Check network connectivity and firewall rules
- Verify endpoint URL is correct (for S3-compatible)
- Check credentials and permissions
- Review application logs for detailed errors

### Authentication Errors

Error: `Access Denied` or `Unauthorized`

Solutions:
- Verify AWS/GCS credentials are correct
- Confirm IAM/service account has required permissions
- Check that credentials are set in environment variables
- Verify bucket name is correct and matches configuration

### Artifact Not Found

Error: `404 Not Found` when retrieving artifact

Solutions:
- Verify artifact was successfully created
- Check that session ID is correct
- Confirm storage backend has the artifact
- Verify you're accessing the correct version

### Performance Issues

Slow artifact creation or retrieval:

Solutions:
- Check network latency to storage backend
- Verify storage backend performance
- Check for throttling or rate limiting
- Consider object size and any upload/download limits

## Next Steps

After configuring artifact storage, you may want to:

- Configure [Session Storage](./session-storage.md) for conversation persistence
- Explore [agent tools](../developing/create-agents.md) for working with artifacts
- Review [deployment options](../deploying/deployment-options.md) for production considerations
- Set up [monitoring and observability](../deploying/observability.md) to track artifact activity
