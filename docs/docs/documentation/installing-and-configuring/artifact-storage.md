---
title: Artifact Storage
sidebar_position: 360
---

# Configuring Artifact Storage

This guide explains how to configure storage for artifacts—files and data created by your agents—from development to production deployments.

## Understanding Artifacts

Artifacts are files and data created by agents during task execution. Examples include generated reports, analysis results, processed documents, or any files that agents produce for users. Agent Mesh provides built-in tools for agents to create, manage, and reference artifacts.

Artifacts are automatically versioned so that each update creates a new version (v0, v1, v2, and so on). They are scoped to specific users and sessions, making them retrievable for download or history review. Agents interact with artifacts through built-in tools that handle creation and management.

### Artifact Storage vs Session Storage

Unlike session storage (which is separate for WebUI Gateway and each agent), artifact storage is shared across all agents and gateways in your deployment.

All agents and gateways connect to the same artifact storage backend, with artifacts scoped by `(user_id, session_id, app_name)` to maintain isolation. Any agent or gateway can access artifacts within their scope, which allows agents to share files and data within a conversation.

For example, you might configure a shared S3 bucket that every component uses:

```yaml
# WebUI Gateway and all agents share this artifact storage
artifact_service:
  type: "s3"
  bucket_name: "shared-artifacts-bucket"
  region: "us-west-2"
```

This differs from session storage, where each agent has its own separate database. With artifact storage, all agents and gateways share the same storage backend.

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

Custom scoping is useful for multi-tenant deployments with custom tenant identifiers, departmental isolation within an organization, environment-specific artifact separation (dev/staging/prod), or custom compliance and regulatory requirements.

## Artifact Storage Backends

Agent Mesh supports multiple storage backends for artifacts. Choose based on your deployment environment and requirements.

| Backend | Best For | Production Ready | Setup Complexity |
|---------|----------|------------------|------------------|
| Filesystem | Local development | ❌ | Simple |
| S3 (AWS) | AWS deployments | ✅ | Medium |
| S3-Compatible API | On-premises, private cloud | ✅ | Medium |
| GCS | Google Cloud deployments | ✅ | Medium |
| Azure Blob | Azure deployments | ✅ | Medium |

### Filesystem Storage (Default)

Filesystem storage saves artifacts to local disk directories. This is the default configuration and is suitable for development and local testing.

Artifacts are stored in a transparent directory structure that persists across restarts. Because the storage is local, it works only for a single instance and cannot be shared across pods. Backing up is as simple as copying directories. You should use filesystem storage only for local development and single-machine deployments.

To configure filesystem storage, add the following to your artifact service block:

```yaml
artifact_service:
  type: "filesystem"
  base_path: "/tmp/sam-artifacts"
```

On disk, artifacts are organized into the following directory structure:

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

S3 provides high durability, scales to any size, and is accessible from any location. It includes automatic backups and redundancy, with IAM-based security controlling access.

To configure S3 storage, specify your bucket and region:

```yaml
artifact_service:
  type: "s3"
  bucket_name: "my-artifacts-bucket"
  region: "us-west-2"
```

Set the following environment variables to provide credentials:

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-west-2"
```

The credentials must have the following IAM permissions on the bucket:

- `s3:GetObject`
- `s3:PutObject`
- `s3:DeleteObject`
- `s3:ListBucket`

Here is an example IAM policy granting these permissions:

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

This backend works with any S3-compatible API implementation, supports custom endpoints for private or on-premises storage, and provides the same versioning and management as AWS S3. It requires a compatible storage service to be running and accessible.

To configure S3-compatible storage, include the `endpoint_url` parameter:

```yaml
artifact_service:
  type: "s3"
  bucket_name: "my-artifacts-bucket"
  endpoint_url: "${S3_ENDPOINT_URL}"
```

Set the following environment variables to point to your storage service:

```bash
export S3_ENDPOINT_URL="https://storage.example.com"
export S3_ACCESS_KEY_ID="your-access-key"
export S3_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"  # Required but can be arbitrary for S3-compatible endpoints
```

This configuration works with any S3-compatible storage service, including self-hosted and cloud-provider solutions. Examples include storage services from various cloud providers and on-premises object storage systems.

### Google Cloud Storage (GCS)

GCS storage uses Google Cloud Storage for artifact persistence. This is the recommended backend for Google Cloud deployments.

GCS offers high availability and durability with deep integration into the Google Cloud ecosystem. It is fully managed by Google, scales automatically, and provides fine-grained IAM controls for access management.

To configure GCS storage, specify your bucket and optionally your project:

```yaml
artifact_service:
  type: "gcs"
  bucket_name: "my-artifacts-bucket"
  project: "my-gcp-project"  # Optional if credentials include project info
```

GCS supports three authentication methods.

#### Service Account JSON File

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

#### Inline Credentials JSON

```bash
export GCS_CREDENTIALS_JSON='{"type":"service_account","project_id":"my-project",...}'
```

This is useful when you cannot mount a file (e.g., in containerized environments). The inline JSON takes priority over the file path if both are set.

#### Application Default Credentials (Workload Identity)

If neither `GOOGLE_APPLICATION_CREDENTIALS` nor `GCS_CREDENTIALS_JSON` is set, the client uses [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials). This is the recommended approach for GKE deployments using Workload Identity.

The following environment variables summarize all GCS authentication options:

```bash
export GCS_PROJECT="my-gcp-project"                          # Optional
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/sa.json"     # Option 1
export GCS_CREDENTIALS_JSON='{"type":"service_account",...}'  # Option 2
```

The service account must have the `Storage Object Admin` role (`roles/storage.objectAdmin`) on the bucket, or at minimum these individual roles:

- `roles/storage.objectViewer`
- `roles/storage.objectCreator`
- `roles/storage.objectDeleter`

### Azure Blob Storage

Azure Blob Storage uses Azure's object storage service for artifact persistence. This is the recommended backend for Azure deployments.

Azure Blob Storage offers high availability and durability with deep integration into the Azure ecosystem. It is fully managed by Azure, scales automatically, and supports RBAC and Azure AD authentication.

To configure Azure Blob Storage, specify your container and account name:

```yaml
artifact_service:
  type: "azure"
  container_name: "my-artifacts-container"
  account_name: "mystorageaccount"
```

Azure supports three authentication methods.

#### Connection String

```bash
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
```

#### Account Name + Account Key

```bash
export AZURE_STORAGE_ACCOUNT_NAME="mystorageaccount"
export AZURE_STORAGE_ACCOUNT_KEY="your-account-key"
```

#### Account Name Only (Workload Identity / Managed Identity)

```bash
export AZURE_STORAGE_ACCOUNT_NAME="mystorageaccount"
```

When only the account name is set (no key or connection string), the client uses `DefaultAzureCredential`, which supports Azure Managed Identity and Workload Identity. This is the recommended approach for AKS deployments.

The following environment variables summarize all Azure authentication options:

```bash
export AZURE_STORAGE_CONNECTION_STRING="..."   # Option 1
export AZURE_STORAGE_ACCOUNT_NAME="..."        # Option 2 or 3
export AZURE_STORAGE_ACCOUNT_KEY="..."         # Option 2 only
```

The identity (service principal, managed identity, or user) must have the following role on the storage account or container:

- `Storage Blob Data Contributor` — grants read, write, and delete access to blob data

## Understanding Artifact Versioning

Agent Mesh automatically manages artifact versions, allowing users to access previous versions of files.

When an agent first creates an artifact, it is stored as version 0. Each subsequent append or update increments the version automatically—version 1, then version 2, and so on. All previous versions persist independently, so users can access any version at any time.

Here is an example lifecycle showing how versions accumulate:

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

Each artifact version includes metadata describing the file:

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

2. **Set Up Service Account** with `Storage Object Admin` role on the bucket:
   ```bash
   gcloud storage buckets add-iam-policy-binding gs://my-artifacts-bucket \
     --member="serviceAccount:my-sa@my-project.iam.gserviceaccount.com" \
     --role="roles/storage.objectAdmin"
   ```

3. **Configure Agent Mesh:**
   ```yaml
   artifact_service:
     type: "gcs"
     bucket_name: "my-artifacts-bucket"
     project: "my-gcp-project"
   ```

4. **Set Up Authentication** (choose one):
   ```bash
   # Option A: Service account JSON file
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

   # Option B: Inline credentials JSON
   export GCS_CREDENTIALS_JSON='{"type":"service_account","project_id":"my-project",...}'
   ```

### Azure Cloud Deployment

For production deployments on Azure:

1. **Create Storage Account and Container:**
   ```bash
   az storage account create --name mystorageaccount --resource-group mygroup --location eastus --sku Standard_LRS
   az storage container create --name my-artifacts-container --account-name mystorageaccount
   ```

2. **Assign RBAC Role** (`Storage Blob Data Contributor`) to your service principal or managed identity:
   ```bash
   az role assignment create \
     --role "Storage Blob Data Contributor" \
     --assignee <principal-id> \
     --scope /subscriptions/<sub-id>/resourceGroups/mygroup/providers/Microsoft.Storage/storageAccounts/mystorageaccount
   ```

3. **Configure Agent Mesh:**
   ```yaml
   artifact_service:
     type: "azure"
     container_name: "my-artifacts-container"
     account_name: "mystorageaccount"
   ```

4. **Set Environment Variables** (choose one):
   ```bash
   # Option A: Connection string
   export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=mystorageaccount;AccountKey=...;EndpointSuffix=core.windows.net"

   # Option B: Account name + key
   export AZURE_STORAGE_ACCOUNT_NAME="mystorageaccount"
   export AZURE_STORAGE_ACCOUNT_KEY="your-account-key"

   # Option C: Managed identity / workload identity (account name only)
   export AZURE_STORAGE_ACCOUNT_NAME="mystorageaccount"
   ```

## Migrating Artifact Storage Backends

Moving from one artifact storage backend to another requires no special migration procedure—the system starts fresh with the new backend.

### Before Migration

Before switching backends, you should understand the implications. Existing artifacts stored in the old backend will not be accessible after switching, and new artifacts will be stored in the new backend. If you need to preserve existing artifacts, export them first from the old storage.

### Migration Steps

Step 1: Set up new storage backend

Create the new storage location:
- For filesystem: `mkdir -p /path/to/new/storage`
- For S3: Create bucket and set up credentials
- For GCS: Create bucket and set up service account
- For Azure: Create storage account/container and set up credentials

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

To enable data retention, add the following to your configuration:

```yaml
data_retention:
  enabled: true
  task_retention_days: 90
  cleanup_interval_hours: 24
```

Artifacts older than `task_retention_days` are cleaned up automatically, with the cleanup process running every `cleanup_interval_hours`. This prevents unbounded storage growth over time.

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
- Verify AWS/GCS/Azure credentials are correct
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
