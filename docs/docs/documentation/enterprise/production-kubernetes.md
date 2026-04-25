---
title: Kubernetes Production Installation
sidebar_position: 5
---

# Kubernetes Production Installation

Deploy SAM Enterprise on Kubernetes for production with full configuration, high availability, and security.

:::info
For quick evaluation, see the [Kubernetes Quick Start](./quickstart-kubernetes.md). For air-gapped environments, see the [Air-Gapped Kubernetes Installation](./airgap-kubernetes.md).
:::

## Production vs Quick Start

Quick Start is designed for **evaluation only** and uses embedded components unsuitable for production:

| Component | Quick Start | Production |
|-----------|-------------|------------|
| **Solace Broker** | Embedded in cluster | External Solace Cloud or on-premises broker |
| **Storage** | Embedded PostgreSQL/SeaweedFS | External S3-compatible storage, managed databases |
| **Authentication** | Disabled | RBAC + SSO (OIDC) |
| **High Availability** | Single instance | Multi-replica, auto-recovery |
| **TLS/Certificates** | None | Full TLS with trusted certificates |
| **Monitoring** | Basic logs | Full observability (Prometheus, Grafana, etc.) |
| **Suitable For** | Testing, evaluation, demos | Production workloads |

## Production Prerequisites

### Kubernetes Platform Requirements

**Supported Kubernetes Versions:**
- The **three most recent minor versions** of upstream Kubernetes
- For managed services (EKS, AKS, GKE): validated against provider's default release channels
- For on-premises (OpenShift, Rancher, etc.): compatibility based on underlying K8s API version

**Platform Support Matrix:**

| Category | Distributions | Support Level |
|----------|---------------|---------------|
| **Validated** | AWS EKS<br/>Azure AKS<br/>Google GKE | **Tier 1 Support** - Explicitly validated by Solace QA |
| **Compatible** | Red Hat OpenShift<br/>VMware Tanzu (TKG)<br/>SUSE Rancher (RKE2)<br/>Oracle OKE<br/>Canonical Charmed K8s<br/>Upstream K8s (kubeadm) | **Tier 2 Support** - Compatible with standard K8s APIs. Proprietary security features (SCCs, PSPs) are customer responsibility |

**Constraints & Limitations:**

- **Node Architecture:** Standard worker nodes (VMs or bare metal) required
  - ❌ **Not Supported:** Serverless nodes (AWS Fargate, GKE Autopilot, Azure Virtual Nodes)
- **Security Context:** Containers run as non-root (UID 999), no privileged capabilities required
  - For OpenShift: May need to add service account to `nonroot` SCC if cluster enforces `restricted-v2`
- **Monitoring:** SAM does NOT deploy DaemonSets - observability is customer responsibility

### Compute Resources

**Processor Architecture:**
- **ARM64** (recommended) - Better price/performance (AWS Graviton, Azure Cobalt, Google Axion)
- **x86_64** (Intel/AMD) - Fully supported

**Recommended Production Node Sizing:**

Use latest-generation general-purpose nodes with 1:4 CPU:Memory ratio:

| Specification | vCPU | RAM | ARM Examples | x86 Examples |
|---------------|------|-----|--------------|--------------|
| **Recommended** | 4 | 16 GiB | AWS `m8g.xlarge`<br/>Azure `Standard_D4ps_v6`<br/>GCP `c4a-standard-4` | AWS `m8i.xlarge`<br/>Azure `Standard_D4s_v6`<br/>GCP `n2-standard-4` |
| **Minimum** | 2 | 8 GiB | AWS `m8g.large`<br/>Azure `Standard_D2ps_v6`<br/>GCP `c4a-standard-2` | AWS `m8i.large`<br/>Azure `Standard_D2s_v6`<br/>GCP `n2-standard-2` |

:::tip Instance Availability
If the listed instance types are unavailable in your region, choose the next closest equivalent (e.g., `m7g.large` instead of `m8g.large`).
:::

**Component Resource Specifications:**

Default resource requests and limits for core components (excluding sidecar overhead):

| Component | Description | CPU Request | CPU Limit | RAM Request | RAM Limit | QoS Class |
|-----------|-------------|-------------|-----------|-------------|-----------|-----------|
| **Agent Mesh** | Core services, Orchestrator, WebUI | 1000m | 2000m | 1024 MiB | 2048 MiB | Burstable |
| **Deployer** | Manages agent/gateway deployments | 100m | 200m | 256 MiB | 512 MiB | Burstable |
| **Agent** (per instance) | Runtime for each deployed agent | 1000m | 2000m | 1024 MiB | 2048 MiB | Burstable |

**Capacity Planning:**

Budget the following per concurrent agent you plan to deploy:
- **Memory Request:** 1024 MiB (1 GiB)
- **Memory Limit:** 2048 MiB (2 GiB)
- **CPU Request:** 1000m (1 vCPU)
- **CPU Limit:** 2000m (2 vCPU)

### External Services (Required)

Production deployments **must** use managed external services. Embedded components are not supported for production.

**Database:**
- PostgreSQL 17+ (AWS RDS, Azure Database for PostgreSQL, Cloud SQL, etc.)
- Admin credentials with `SUPERUSER` privileges (recommended) or minimum `CREATEROLE` and `CREATEDB`
- SAM's init container uses admin credentials to automatically create users and databases
- See [Session Storage](/docs/documentation/installing-and-configuring/session-storage) for configuration

**Object Storage:**
- S3-compatible API (AWS S3, Azure Blob Storage, Google Cloud Storage)
- See [Artifact Storage](/docs/documentation/installing-and-configuring/artifact-storage) for configuration

**Solace Event Broker:**
- Solace Cloud-managed broker (recommended) or self-hosted PubSub+
- SMF over TLS (port 55443) or WebSocket Secure connectivity

**LLM Service:**
- OpenAI, Azure OpenAI, AWS Bedrock, or compatible endpoint
- Can be configured post-install via Model Config UI or pre-configured in values.yaml

**Identity Provider (IdP):**
- OIDC-compliant provider (Microsoft Entra ID, Okta, AWS Cognito, etc.)
- Required for SSO and RBAC
- See [Single Sign-On](./single-sign-on.md) for configuration

**S3 Bucket for OpenAPI Connector Specs (Optional):**

If using OpenAPI Connector features, a separate S3 bucket is required:
- **Public read access** - Agents download specs without authentication
- **Authenticated write** - SAM platform uploads/manages specs
- **Security:** Only API schemas stored, never credentials
- Configure via `dataStores.s3.connectorSpecBucketName` in values.yaml

:::info Why Separate Bucket?
OpenAPI connector specs must be publicly readable for agents to download at startup, while artifact storage requires authentication. Separation maintains security boundaries.
:::

For detailed setup instructions, see [S3 Buckets for OpenAPI Connector Specs](#s3-buckets-for-openapi-connector-specs) below.

### Network Connectivity

**Inbound Traffic:**
- Ingress controller required (NGINX, ALB, etc.)
- TLS certificate for production (via cert-manager or manual)
- See [Network Configuration Guide](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs/network-configuration) for ingress setup

**Outbound Platform Access:**

The following outbound connectivity is required:

| Destination | Purpose | Notes |
|-------------|---------|-------|
| `gcr.io/gcp-maas-prod` | Container registry | Requires Pull Secret from Solace Cloud Console<br/>**OR** mirror to private registry |
| `*.messaging.solace.cloud` | Solace Cloud broker | **OR** self-hosted broker at SMF/SMF+TLS ports |
| LLM provider endpoints | Model inference | e.g., `api.openai.com`, Azure OpenAI endpoints |
| Identity Provider (IdP) | Authentication/authorization | Your OIDC provider endpoints |

**Corporate Proxy Support:**
- HTTP/HTTPS proxy configuration supported for egress filtering
- See [Proxy Configuration](/docs/documentation/deploying/proxy_configuration) for setup

**Application & Mesh Components:**
- Custom agents may require access to external systems (Salesforce, Jira, databases, etc.)
- Ensure worker nodes have network reachability to target services

### Command-Line Tools

- Helm v3.0 or later ([installation guide](https://helm.sh/docs/intro/install/))
- `kubectl` configured with appropriate RBAC permissions
- Optional: `helm diff` plugin for upgrade previews

### Additional Requirements

**TLS Certificates:**
- Required for production Ingress or LoadBalancer/NodePort with TLS
- Managed via Ingress annotations (cert-manager, ACM) or manual Secret creation
- See values.yaml inline documentation for configuration options

**RBAC Permissions:**
- Namespace creation and management
- Deployment, Service, ConfigMap, Secret creation
- PVC creation (if using bundled persistence for dev/staging)

**Queue Template Configuration (Recommended):**

For production Kubernetes deployments, configure Solace broker queue templates to prevent message buildup and startup issues. See [Queue Template Configuration for Kubernetes](#queue-template-configuration-for-kubernetes) in Step 2 for detailed setup instructions.


## Architecture Overview

<!-- Content: Production K8s architecture diagram -->

## Step 1: Infrastructure Preparation

Prepare your Kubernetes cluster infrastructure before deploying SAM.

### Cluster Sizing

**Production Cluster Requirements:**

For production deployments using external components (no embedded broker/persistence), plan for the following baseline resources:

- **Minimum per node:** 2 vCPU / 8 GiB RAM
- **Recommended per node:** 4 vCPU / 16 GiB RAM

**Per-Agent Capacity Planning:**

Budget the following per concurrent agent:
- CPU Request: 175m
- CPU Limit: 200m
- Memory Request: 625 MiB
- Memory Limit: 768 MiB

**Node Instance Examples:**

| Specification | ARM64 (Recommended) | x86_64 |
|---------------|---------------------|--------|
| **Recommended** (4 vCPU / 16 GiB) | AWS `m8g.xlarge`<br/>Azure `Standard_D4ps_v6`<br/>GCP `c4a-standard-4` | AWS `m8i.xlarge`<br/>Azure `Standard_D4s_v6`<br/>GCP `n2-standard-4` |
| **Minimum** (2 vCPU / 8 GiB) | AWS `m8g.large`<br/>Azure `Standard_D2ps_v6`<br/>GCP `c4a-standard-2` | AWS `m8i.large`<br/>Azure `Standard_D2s_v6`<br/>GCP `n2-standard-2` |

:::tip ARM64 Recommended
ARM64 instances (AWS Graviton, Azure Cobalt, Google Axion) offer better price/performance. If listed instances are unavailable in your region, choose the next closest equivalent (e.g., `m7g.large` instead of `m8g.large`).
:::

### Node Pool Topology (Multi-AZ Clusters)

:::info Stateless Workloads
When using external persistence (recommended for production), all SAM workloads are stateless and do not have multi-AZ topology constraints. This section is only relevant if you're using embedded persistence for dev/staging environments on production-grade clusters.
:::

In multi-AZ clusters (EKS, AKS, GKE), when using embedded persistence (`global.persistence.enabled: true`), one node pool must be provisioned per availability zone due to volume affinity constraints.

**Simplest Approach:**

Provision SAM in **one availability zone only** to avoid multi-AZ complexity.

**Official Cloud Provider Guidance:**
- **AKS:** [Cluster Autoscaler Documentation](https://learn.microsoft.com/en-us/azure/aks/cluster-autoscaler?tabs=azure-cli#re-enable-the-cluster-autoscaler-on-a-node-pool)
- **EKS:** [Managed Node Groups](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html#managed-node-group-concepts)
- **GKE:** Follow the same pattern for simplicity and consistency

**Why This Matters:**

StatefulSets with persistent volumes (PostgreSQL, SeaweedFS) are bound to specific zones. When nodes span multiple AZs without proper node pool configuration, pod scheduling can fail if the PVC and node are in different zones.

### Network Configuration

<!-- Content: Network policies, ingress, load balancers -->

## Step 2: External Dependencies

Configure external services required for production SAM deployments.

### Solace Broker Configuration

Set up your external Solace event broker before installing SAM.

**Solace Cloud (Recommended):**
1. Create a service in [Solace Cloud](https://console.solace.cloud/)
2. Navigate to **Cluster Manager** → Your Service → **Connect**
3. Switch dropdown to **View by Language**
4. Select **Solace Python** with **SMF** protocol
5. Note the following credentials:
   - **Secured SMF URI** (for `broker.url`)
   - **Message VPN** (for `broker.vpn`)
   - **Username** (for `broker.clientUsername`)
   - **Password** (for `broker.password`)

**Self-Hosted PubSub+:**
- Ensure SMF over TLS (port 55443) or WebSocket Secure connectivity
- Provide connection details in values.yaml (see Step 3)

#### Queue Template Configuration for Kubernetes

For production Kubernetes deployments, configure your Solace broker to use durable queues with message TTL to prevent queue buildup and startup issues.

**Why Durable Queues for Kubernetes?**

When `USE_TEMPORARY_QUEUES=true` (default), SAM uses temporary endpoints for agent-to-agent communication. Temporary queues are automatically created and deleted by the broker, but they **do not support multiple client connections** to the same queue.

In container-managed environments like Kubernetes, this causes problems:
- A new pod may start while the previous instance is still terminating
- The new pod cannot connect because the old pod still holds the temporary queue
- Pod startup fails until the old instance fully terminates

**Solution: Use Durable Queues**

Durable queues persist beyond client disconnections and allow multiple instances to connect to the same queue.

**Step 1: Configure SAM to Use Durable Queues**

Set the following in your Helm values:

```yaml
# In your production-overrides.yaml
environmentVariables:
  USE_TEMPORARY_QUEUES: "false"
```

**Step 2: Create Queue Template in Solace Cloud Console**

To prevent messages from piling up when agents are not running, configure message TTL (time-to-live) via a Queue Template:

1. Navigate to **Message VPNs** and select your VPN
2. Go to the **Queues** page
3. Open the **Templates** tab
4. Click **+ Queue Template**

**Template Settings:**

| Setting | Value | Location |
|---------|-------|----------|
| **Queue Name Filter** | `{NAMESPACE}/>` | Replace `{NAMESPACE}` with your SAM namespace (e.g., `sam/>`) |
| **Respect TTL** | `true` | Advanced Settings → Message Expiry |
| **Maximum TTL (sec)** | `18000` | Advanced Settings → Message Expiry |

:::info Template Application
Queue templates only apply to **new queues created by messaging clients**. If you already have durable queues from previous deployments, either:
- Manually enable **TTL** and **Respect TTL** on each existing queue in Solace console, OR
- Delete existing queues and restart SAM to recreate them with the template settings
:::

**Step 3: Verify Configuration**

After deploying SAM, verify queues are created with correct settings:

1. In Solace Cloud Console, navigate to **Queues**
2. Find queues matching your namespace pattern (e.g., `sam/...`)
3. Check that **Respect TTL** is enabled
4. Verify **Maximum TTL** is set to 18000 seconds

For more details on queue configuration, see [Queue Template Configuration](/docs/documentation/deploying/deployment-options#setting-up-queue-templates).

### S3-Compatible Storage

Configure external object storage for artifacts and session data.

### Certificate Management

<!-- Content: TLS cert setup with cert-manager or manual -->

### S3 Buckets for OpenAPI Connector Specs

If you plan to use the **OpenAPI Connector** feature for REST API integrations, you must configure a dedicated S3 bucket for OpenAPI specification files. This is separate from artifact storage and required for agents to download OpenAPI specs at startup.

#### When is a Connector Specs Bucket Required?

- ✅ When using the OpenAPI Connector feature for REST API integrations
- ✅ When agents must access OpenAPI spec files at startup
- ✅ For all Kubernetes deployments using OpenAPI connectors
- ❌ Not required if you're not using OpenAPI Connector features

#### Why a Separate Bucket?

- **Public read access** - Agents must download OpenAPI specs without authentication
- **Security isolation** - Keeps infrastructure files separate from user artifacts  
- **No secrets** - Only API schemas, endpoints, and models are stored (never credentials)

#### Setup Instructions

**Step 1: Create the Connector Specs S3 Bucket**

```bash
aws s3 mb s3://my-connector-specs-bucket --region us-west-2
```

Replace `my-connector-specs-bucket` with your bucket name and `us-west-2` with your region.

**Step 2: Apply Public Read Policy**

Create a policy file `connector-specs-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::my-connector-specs-bucket/*"
  }]
}
```

Apply the policy:

```bash
aws s3api put-bucket-policy \
  --bucket my-connector-specs-bucket \
  --policy file://connector-specs-policy.json
```

**Step 3: Configure IAM Permissions for SAM Platform**

Grant the SAM platform's IAM user/role the following permissions for write access:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ],
    "Resource": [
      "arn:aws:s3:::my-connector-specs-bucket",
      "arn:aws:s3:::my-connector-specs-bucket/*"
    ]
  }]
}
```

**Step 4: Configure in Helm Values**

Add the bucket name to your `production-overrides.yaml`:

```yaml
dataStores:
  s3:
    bucketName: "sam-artifacts"              # Main artifact storage
    connectorSpecBucketName: "my-connector-specs-bucket"  # OpenAPI connector specs
    region: "us-west-2"
    # ... other S3 config
```

#### Other Cloud Providers

For Azure Blob Storage, Google Cloud Storage, or other S3-compatible storage, configure the `connectorSpecBucketName` (or equivalent container name) in your Helm values under the appropriate `dataStores` section. Ensure the bucket/container has public read access and that the SAM platform has write permissions.

#### Security Best Practices

:::warning Security Guidelines
- Never store API keys, passwords, or secrets in OpenAPI spec files
- Public read is safe - only API schemas are stored
- Write access should be restricted to the SAM platform
:::

#### Verification

After setup, verify the bucket is accessible:

```bash
# Test public read access (should work without credentials)
curl https://my-connector-specs-bucket.s3.amazonaws.com/test-spec.yaml
```

If you get a 403 Forbidden error, check your bucket policy. If you get 404 Not Found, the bucket is correctly configured (just no files uploaded yet).

## Step 3: Helm Chart Configuration

<!-- Content: Production values.yaml -->

### Core Configuration

Create a production overrides file (`production-overrides.yaml`) based on the comprehensive inline documentation in the chart's `values.yaml`.

**Disable Embedded Components:**

```yaml
global:
  broker:
    embedded: false  # Use external Solace broker
  persistence:
    enabled: false   # Use external datastores
```

**Configure External Solace Broker:**

```yaml
broker:
  url: "tcps://your-broker.messaging.solace.cloud:55443"
  clientUsername: "your-username"
  password: "your-password"
  vpn: "your-vpn"
```

**Configure External Datastores:**

Configure PostgreSQL database and object storage. The `applicationPassword` is **required** - this single password will be used for all database users created by SAM (webui, orchestrator, platform, and all agents).

:::warning Password Rotation Limitation
Once database users are created for a given `namespaceId`, the `applicationPassword` cannot be changed. To change passwords, you must either use a new `namespaceId` (creates new databases/users) or manually update passwords directly in the database.
:::

**Provider-Specific Configuration Examples:**

**AWS RDS + S3:**

```yaml
dataStores:
  database:
    protocol: "postgresql+psycopg2"
    host: "mydb.abc123.us-east-1.rds.amazonaws.com"
    port: "5432"
    adminUsername: "postgres"
    adminPassword: "your-rds-password"
    applicationPassword: "your-secure-app-password"  # REQUIRED
  
  objectStorage:
    type: "s3"
  
  s3:
    endpointUrl: "https://s3.us-east-1.amazonaws.com"
    bucketName: "my-sam-artifacts"
    connectorSpecBucketName: "my-sam-connector-specs"
    accessKey: "AKIAIOSFODNN7EXAMPLE"
    secretKey: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    region: "us-east-1"
```

**Supabase with Connection Pooler:**

If using Supabase with the connection pooler (required for IPv4 networks):

```yaml
dataStores:
  database:
    protocol: "postgresql+psycopg2"
    host: "aws-1-us-east-1.pooler.supabase.com"
    port: "5432"
    adminUsername: "postgres"
    adminPassword: "your-supabase-postgres-password"
    applicationPassword: "your-secure-app-password"
    supabaseTenantId: "your-project-id"  # Extract from connection string
  
  s3:
    endpointUrl: "https://your-project-id.storage.supabase.co/storage/v1/s3"
    bucketName: "your-bucket-name"
    connectorSpecBucketName: "your-connector-specs-bucket-name"
    accessKey: "your-supabase-s3-access-key"
    secretKey: "your-supabase-s3-secret-key"
```

:::info Supabase Direct Connection
If using Supabase's Direct Connection with IPv4 addon, omit the `supabaseTenantId` field.
:::

**NeonDB:**

```yaml
dataStores:
  database:
    protocol: "postgresql+psycopg2"
    host: "ep-cool-name-123456.us-east-2.aws.neon.tech"
    port: "5432"
    adminUsername: "neondb_owner"
    adminPassword: "your-neon-password"
    applicationPassword: "your-secure-app-password"
  
  s3:
    endpointUrl: "https://s3.amazonaws.com"
    bucketName: "my-sam-artifacts"
    connectorSpecBucketName: "my-sam-connector-specs"
    accessKey: "your-access-key"
    secretKey: "your-secret-key"
```

**Azure Blob Storage:**

Option 1: Using account name and key:

```yaml
dataStores:
  objectStorage:
    type: "azure"
  
  database:
    protocol: "postgresql+psycopg2"
    host: "your-postgres-host"
    port: "5432"
    adminUsername: "postgres"
    adminPassword: "your-db-password"
    applicationPassword: "your-secure-app-password"
  
  azure:
    accountName: "mystorageaccount"
    accountKey: "your-azure-storage-account-key"
    containerName: "my-sam-artifacts"
    connectorSpecContainerName: "my-sam-connector-specs"
```

Option 2: Using connection string:

```yaml
  azure:
    connectionString: "DefaultEndpointsProtocol=https;AccountName=mystorageaccount;AccountKey=...;EndpointSuffix=core.windows.net"
    containerName: "my-sam-artifacts"
    connectorSpecContainerName: "my-sam-connector-specs"
```

**Google Cloud Storage:**

```yaml
dataStores:
  objectStorage:
    type: "gcs"
  
  database:
    protocol: "postgresql+psycopg2"
    host: "your-postgres-host"
    port: "5432"
    adminUsername: "postgres"
    adminPassword: "your-db-password"
    applicationPassword: "your-secure-app-password"
  
  gcs:
    project: "my-gcp-project"
    credentialsJson: '{"type":"service_account","project_id":"my-gcp-project",...}'
    bucketName: "my-sam-artifacts"
    connectorSpecBucketName: "my-sam-connector-specs"
```

**Workload Identity (Recommended for Cloud):**

Workload identity allows SAM pods to authenticate with cloud storage using the pod's Kubernetes service account, eliminating static credentials (access keys, account keys, JSON key files).

Enable workload identity:

```yaml
dataStores:
  objectStorage:
    type: "s3"  # or "azure" or "gcs"
    workloadIdentity:
      enabled: true
```

Annotate the SAM service account:

```yaml
samDeployment:
  serviceAccount:
    annotations:
      # AWS IRSA:
      eks.amazonaws.com/role-arn: "arn:aws:iam::123456789012:role/my-sam-role"
      # OR Azure Workload Identity:
      azure.workload.identity/client-id: "00000000-0000-0000-0000-000000000000"
      # OR GCP Workload Identity:
      iam.gke.io/gcp-service-account: "my-sa@my-project.iam.gserviceaccount.com"
```

**Per-Provider Setup (High-Level):**

- **AWS IRSA:** Create IAM role with S3 permissions, associate with K8s service account, omit `accessKey`/`secretKey`
- **Azure Workload Identity:** Create managed identity with Storage Blob Data Contributor role, establish federated credential, omit `accountKey`/`connectionString`
- **GCP Workload Identity:** Create GCP service account with Storage Object Admin, bind to K8s service account, omit `credentialsJson`

**Enable Authorization and OIDC:**

```yaml
sam:
  authorization:
    enabled: true
  
  oauthProvider:
    oidc:
      issuer: "https://login.microsoftonline.com/YOUR-TENANT-ID/v2.0"
      clientId: "your-client-id"
      clientSecret: "your-client-secret"
```

**Configure Ingress:**

```yaml
ingress:
  enabled: true
  className: "nginx"
  host: "sam.example.com"
  autoConfigurePaths: true
  tls:
    - secretName: sam-tls-cert
      hosts:
        - sam.example.com
```

**Secret Management:**
- `SESSION_SECRET_KEY` is auto-generated if not provided
- Once generated, it is preserved across upgrades to prevent session invalidation
- For production, explicitly set it for consistency: `sam.sessionSecretKey: "your-secret-key"`

**LLM Configuration (Optional):**
- LLM can be configured post-install via the Model Config UI
- Alternatively, pre-configure in values.yaml under `llmService.*`

**Custom CA Certificates (For Internal Infrastructure):**

If your internal infrastructure (Solace broker, OIDC provider, LLM service) uses self-signed or private CA certificates, configure SAM to trust them.

**When needed:**
- Solace broker with custom CA
- OIDC provider (Keycloak, etc.) with custom CA
- LLM service with custom CA
- Any internal endpoint using private certificates

**Prerequisites:**

:::warning Certificate Requirements
- Use the **CA certificate** (issuer), not the server certificate
- Certificate must include **SAN (Subject Alternative Name)** extension
- File must have **`.crt` extension** (REQUIRED)
- PEM format with `-----BEGIN CERTIFICATE-----` headers
:::

**Verify SAN Extension:**

Before creating the ConfigMap, verify your CA certificate includes SAN:

```bash
openssl x509 -in ca-cert.pem -noout -text | grep -A1 "Subject Alternative Name"
```

Expected output:
```
X509v3 Subject Alternative Name:
    DNS:mybroker.messaging.solace.cloud
```

**Certificate Format Conversion (if needed):**

If your certificate is not in PEM format:

```bash
# DER (binary) to PEM
openssl x509 -inform der -in ca.der -out ca.crt

# PKCS#7 bundle → PEM (extracts all CA certs)
openssl pkcs7 -print_certs -in ca.p7b -out ca.crt

# PKCS#12 (.pfx / .p12) → PEM (CA certs only, no private keys)
openssl pkcs12 -in ca.pfx -out ca.crt -nokeys -cacerts
```

**Configuration Steps:**

**Step 1: Prepare CA bundle**

Ensure file has `.crt` extension:

```bash
cp ca-cert.pem ca-cert.crt
```

**Step 2: Create Kubernetes ConfigMap**

Single CA certificate:

```bash
kubectl create configmap truststore \
  --from-file=ca.crt=/path/to/your-ca.crt \
  -n <namespace>
```

Multiple CA certificates:

```bash
kubectl create configmap truststore \
  --from-file=ca1.crt=/path/to/ca1.crt \
  --from-file=ca2.crt=/path/to/ca2.crt \
  --from-file=ca3.crt=/path/to/ca3.crt \
  -n <namespace>
```

:::tip Multiple CAs
If you have multiple CAs (e.g., broker CA, Keycloak CA, LLM CA), pass each as a separate `--from-file` flag. All keys must end in `.crt`.
:::

**Step 3: Enable in Helm values**

Add to your `production-overrides.yaml`:

```yaml
samDeployment:
  customCA:
    enabled: true
    configMapName: "truststore"  # Optional: default is "truststore"
```

**Step 4: Install or upgrade**

```bash
helm upgrade sam solace/solace-agent-mesh \
  -n <namespace> \
  -f production-overrides.yaml
```

The chart will automatically inject a `ca-merge` init container that merges your CA bundle with the system trust store.

**Updating CA Certificates:**

To rotate or update certificates:

```bash
# Delete old ConfigMap
kubectl delete configmap truststore -n <namespace>

# Create new ConfigMap
kubectl create configmap truststore \
  --from-file=ca.crt=/path/to/new-ca.crt \
  -n <namespace>

# Restart deployment
kubectl rollout restart deployment/sam-solace-agent-mesh-core -n <namespace>
```

**Important Notes:**
- If ConfigMap doesn't exist when pod starts, SAM falls back to system CA bundle silently (no error raised)
- Pod restart is always required for CA changes (no hot reload)
- ConfigMap name can be customized via `customCA.configMapName` if `truststore` conflicts with existing resources

:::info Embedded vs External Components
Production deployments must use external components. Embedded PostgreSQL, SeaweedFS, and Solace broker lack high availability, backup/restore, and proper resource limits.
:::

### High Availability Configuration

<!-- Content: Multi-replica, PDB, affinity -->

### Security Configuration

<!-- Content: RBAC, pod security, network policies -->

### Resource Limits

<!-- Content: Production resource requests/limits -->

### Monitoring Configuration

<!-- Content: Prometheus, logging integration -->

## Step 4: Pre-Installation Validation

Validate your production configuration before deploying:

**Dry-run installation:**

```bash
helm install sam solace/solace-agent-mesh \
  --namespace sam \
  --dry-run \
  -f production-overrides.yaml
```

**Validate Kubernetes manifests (optional):**

```bash
helm template sam solace/solace-agent-mesh \
  -f production-overrides.yaml | \
  kubeconform -strict -summary -kubernetes-version 1.28.0
```

**Verify external service connectivity:**
- Confirm PostgreSQL is accessible from the cluster
- Confirm S3 endpoint is accessible
- Confirm Solace broker is reachable
- Confirm LLM endpoint is accessible (if pre-configured)

## Step 5: Installation

Install SAM with your production overrides:

```bash
helm install sam solace/solace-agent-mesh \
  --namespace sam \
  --create-namespace \
  -f production-overrides.yaml
```

The chart's default `values.yaml` contains comprehensive inline documentation for all configuration options. Reference it when creating your production overrides.

## Step 6: Post-Installation Configuration

<!-- Content: Post-install setup -->

**Verify Production Readiness:**

- ✓ **Persistence**: External PostgreSQL and S3 (not embedded)
- ✓ **Authorization**: Enabled
- ✓ **OIDC**: Issuer configured
- ✓ **TLS**: Certificates configured
- ✓ **Ingress/LoadBalancer**: External access enabled

### Configure Authentication

<!-- Content: SSO setup -->

See [Single Sign-On](./single-sign-on.md) for detailed OAuth/OIDC provider setup.

### Configure Authorization

<!-- Content: RBAC setup -->

See [RBAC Setup Guide](./rbac-setup-guide.md) for detailed access control configuration.

### Set Up Ingress

<!-- Content: Ingress configuration for production -->

### Configure Monitoring

<!-- Content: Monitoring setup -->

## Step 7: Production Validation

Perform comprehensive validation before going live.

### Health Checks

SAM provides HTTP health check endpoints that integrate with Kubernetes probes for automated lifecycle management. Configure startup, readiness, and liveness probes in your deployment manifests to enable graceful deployments and automatic recovery from failures.

**Verify health endpoints:**

```bash
# Check WebUI health
kubectl exec -n sam deployment/sam-solace-agent-mesh-core -- curl -s http://localhost:80/health

# Check Platform API health
kubectl exec -n sam deployment/sam-solace-agent-mesh-core -- curl -s http://localhost:8080/api/v1/platform/health
```

For detailed probe configuration options and examples, see [Health Checks](/docs/documentation/deploying/health-checks).

### Health Checks

<!-- Content: Health endpoint validation -->

### Load Testing

<!-- Content: Basic load testing -->

### Disaster Recovery Testing

<!-- Content: Backup/restore validation -->

## Production Operations

<!-- Content: Day 2 operations -->

### Backup & Restore

<!-- Content: Backup procedures -->

### Updates & Upgrades

<!-- Content: Production upgrade procedures -->

### Monitoring & Alerting

<!-- Content: Production monitoring setup -->

### Troubleshooting

<!-- Content: Production troubleshooting -->

## Security Hardening

<!-- Content: Production security best practices -->

## Performance Tuning

<!-- Content: Production performance optimization -->

## Upgrading from Quick Start

If you started with the Quick Start installation (chart defaults), upgrade to production using `helm upgrade`:

```bash
helm upgrade sam solace/solace-agent-mesh \
  --namespace sam \
  -f production-overrides.yaml
```

**Progressive Upgrade Strategy:**

You can enable external components one at a time to reduce risk:

1. **First upgrade**: External datastores only
   ```yaml
   global:
     persistence:
       enabled: false
   dataStores:
     database: { ... }
     s3: { ... }
   ```

2. **Second upgrade**: Add external broker
   ```yaml
   global:
     broker:
       embedded: false
   broker: { ... }
   ```

3. **Third upgrade**: Enable auth and TLS
   ```yaml
   sam:
     authorization:
       enabled: true
   ingress:
     enabled: true
     tls: [ ... ]
   ```

:::warning Data Migration Required
When migrating from embedded PostgreSQL to external, you must export and import your data. The embedded database is not automatically migrated.
:::

## Reference

Complete reference for all configuration options in the SAM Helm chart.

### Global Configuration

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `global.broker.embedded` | Deploy embedded single-node Solace event broker alongside SAM. For production, set to `false` and configure external broker. | boolean | `true` |
| `global.persistence.enabled` | Deploy bundled persistence with in-cluster PostgreSQL and SeaweedFS. For production, set to `false` and configure external datastores. | boolean | `true` |
| `global.persistence.namespaceId` | Unique identifier for SAM database/user scoping. Must be unique per SAM installation to avoid topic collisions. | string | `"solace-agent-mesh"` |
| `global.imageRegistry` | Container registry for all images. For air-gapped environments, set to your internal registry. | string | `"gcr.io/gcp-maas-prod"` |
| `global.imagePullSecrets` | Image pull secrets applied to ALL pods (core, agent-deployer, postgresql, seaweedfs, broker). Required when using private registry. | list | `[]` |
| `global.imagePullKey` | Docker config JSON for private registry authentication. Mutually exclusive with `imagePullSecrets`. Use with `--set-file global.imagePullKey=credentials.json` | string | `""` |

### Validations

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `validations.clusterResourceChecks` | Template-time cluster resource existence checks. Looks up referenced Secrets, ConfigMaps, StorageClass, IngressClass before install. Set to `false` if service account lacks `get` RBAC on cluster resources. | boolean | `true` |

### SAM Core Configuration

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `sam.communityMode` | Disable SAM enterprise features (internal use only) | boolean | `false` |
| `sam.frontendServerUrl` | Frontend URL for accessing SAM. For port-forward, use `http://localhost:8000`. For production with Ingress, set to `""` (enables auto-detection). For LoadBalancer, set to external URL. | string | `"http://localhost:8000"` |
| `sam.platformServiceUrl` | Platform service URL. For port-forward, use `http://localhost:8080`. For production with Ingress, set to `""` (enables auto-detection). | string | `"http://localhost:8080"` |
| `sam.cors.allowedOriginRegex` | CORS regex pattern for allowed origins. Default allows any localhost:port. For production, set to `""`. | string | `"https?://(localhost\|127\\.0\\.0\\.1)(:\\d+)?"` |
| `sam.authorization.enabled` | Enforce RBAC authorization via OIDC. Default: `false` (all users have admin access). For production, set to `true` and configure oauthProvider/authenticationRbac. | boolean | `false` |
| `sam.dnsName` | External DNS name for SAM. Not required for port-forward or Ingress. For LoadBalancer/NodePort, set to your external DNS name. | string | `""` |
| `sam.sessionSecretKey` | Secure session key. Auto-generates on first install if empty, stable across upgrades. For production, explicitly set for reproducibility. | string | `""` |
| `sam.oauthProvider.oidc.issuer` | OIDC issuer URL for authentication | string | `""` |
| `sam.oauthProvider.oidc.clientId` | OIDC client ID | string | `""` |
| `sam.oauthProvider.oidc.clientSecret` | OIDC client secret | string | `""` |
| `sam.authenticationRbac.customRoles` | Custom role definitions with fine-grained scopes | object | `{}` |
| `sam.authenticationRbac.users` | Static user role assignments | list | See default users in values.yaml |
| `sam.authenticationRbac.idpClaims.enabled` | Enable dynamic role assignment from IDP claims | boolean | `false` |
| `sam.authenticationRbac.idpClaims.oidcProvider` | OIDC provider name for IDP claims | string | `"oidc"` |
| `sam.authenticationRbac.idpClaims.claimKey` | Claim key containing group/role information | string | `"groups"` |
| `sam.authenticationRbac.idpClaims.mappings` | Map IDP claim values to SAM roles | object | `{}` |
| `sam.authenticationRbac.defaultRoles` | Default roles assigned when no explicit role match found | list | `["sam_user"]` |
| `sam.taskLogging.enabled` | Enable SAM logging during task execution | boolean | `true` |
| `sam.taskLogging.logStatusUpdates` | Log status updates during tasks | boolean | `true` |
| `sam.taskLogging.logArtifactEvents` | Log artifact events | boolean | `false` |
| `sam.taskLogging.logFileParts` | Log file parts | boolean | `true` |
| `sam.taskLogging.maxFilePartSizeBytes` | Maximum file part size for logging | integer | `10240` |
| `sam.taskLogging.hybridBuffer.enabled` | Enable hybrid buffer for logging | boolean | `true` |
| `sam.taskLogging.hybridBuffer.flushThreshold` | Flush threshold for hybrid buffer | integer | `10` |
| `sam.featureEnablement.awsBedrockEnabled` | Enable AWS Bedrock integration | boolean | `true` |
| `sam.featureEnablement.backgroundTasks` | Enable background tasks feature | boolean | `true` |
| `sam.featureEnablement.binaryArtifactPreview` | Enable binary artifact preview | boolean | `true` |

### Broker Configuration (External)

Configure external Solace Event Broker. For production, set `global.broker.embedded: false` and configure these values.

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `broker.url` | Solace broker connection URL (e.g., `tcps://broker.messaging.solace.cloud:55443` or `wss://...:443`) | string | `""` |
| `broker.clientUsername` | Broker username for authentication | string | `""` |
| `broker.password` | Broker password | string | `""` |
| `broker.vpn` | Broker VPN name | string | `""` |

### LLM Service Configuration

Configure LLM service here or via SAM UI after installation. All fields are optional.

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `llmService.llmServiceEndpoint` | LLM API endpoint (e.g., `https://api.openai.com/v1`) | string | N/A (optional) |
| `llmService.llmServiceApiKey` | API key for LLM service | string | N/A (optional) |
| `llmService.planningModel` | Model name for planning tasks (e.g., `gpt-4o`) | string | N/A (optional) |
| `llmService.generalModel` | Model name for general tasks (e.g., `gpt-4o`) | string | N/A (optional) |
| `llmService.reportModel` | Model name for reports (optional) | string | N/A (optional) |
| `llmService.imageModel` | Model name for image generation (e.g., `dall-e-3`, optional) | string | N/A (optional) |
| `llmService.transcriptionModel` | Model name for audio transcription (e.g., `whisper-1`, optional) | string | N/A (optional) |

### Environment Variables

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `extraSecretEnvironmentVars` | Load credentials from existing Kubernetes Secrets. List of objects with `envName`, `secretName`, `secretKey` fields. | list | `[]` |
| `environmentVariables` | Inject custom environment variables into SAM core containers. Use for feature flags and custom configuration. | object | Feature flags enabled |

### Network Configuration - Service

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `service.type` | Kubernetes service type. For production, use `ClusterIP` with Ingress, or `LoadBalancer`/`NodePort` for direct access. | string | `"ClusterIP"` |
| `service.annotations` | Service annotations for cloud-specific load balancer configuration | object | `{}` |
| `service.nodePorts.http` | NodePort for HTTP WebUI (30000-32767). Only used if `service.type: NodePort` | string | `""` |
| `service.nodePorts.https` | NodePort for HTTPS WebUI (30000-32767) | string | `""` |
| `service.nodePorts.auth` | NodePort for Auth Service (30000-32767) | string | `""` |
| `service.nodePorts.platformHttp` | NodePort for Platform API HTTP (30000-32767) | string | `""` |
| `service.nodePorts.platformHttps` | NodePort for Platform API HTTPS (30000-32767) | string | `""` |
| `service.tls.enabled` | Enable TLS/SSL for LoadBalancer/NodePort (pod-level TLS termination). Not needed for Ingress. | boolean | `false` |
| `service.tls.existingSecret` | Reference existing kubernetes.io/tls secret for TLS | string | `""` |
| `service.tls.cert` | TLS certificate (inline). Use `--set-file service.tls.cert=/path/to/tls.crt` | string | `""` |
| `service.tls.key` | TLS key (inline). Use `--set-file service.tls.key=/path/to/tls.key` | string | `""` |
| `service.tls.passphrase` | TLS key passphrase | string | `""` |

### Network Configuration - Ingress

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `ingress.enabled` | Enable Ingress for HTTP/HTTPS routing. For production, set to `true`. | boolean | `false` |
| `ingress.className` | Ingress controller class name (e.g., `nginx`, `alb`, `traefik`, `gce`) | string | `""` |
| `ingress.annotations` | Ingress annotations (vary by controller). Examples in values.yaml for NGINX, ALB. | object | `{}` |
| `ingress.autoConfigurePaths` | Automatically configure all required ingress paths (platform API, auth, webui). Recommended. | boolean | `true` |
| `ingress.host` | Hostname for ingress. Leave empty for ALB (accepts all hostnames). Required for NGINX/other name-based controllers. | string | `""` |
| `ingress.hosts` | Manual hosts/paths configuration. Only used when `autoConfigurePaths: false`. | list | `[]` |
| `ingress.tls` | TLS configuration for ingress. Entries trigger HTTPS URL generation (required for OIDC redirects). | list | `[]` |

### Persistence - External Datastores

Configure external PostgreSQL database and object storage. For production, set `global.persistence.enabled: false` and configure these values.

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `dataStores.database.protocol` | Database protocol | string | `"postgresql+psycopg2"` |
| `dataStores.database.host` | PostgreSQL hostname (e.g., `mydb.us-east-1.rds.amazonaws.com`) | string | `""` |
| `dataStores.database.port` | PostgreSQL port | string | `"5432"` |
| `dataStores.database.adminUsername` | PostgreSQL admin user (used to create SAM application users) | string | `""` |
| `dataStores.database.adminPassword` | PostgreSQL admin password | string | `""` |
| `dataStores.database.applicationPassword` | Shared password for all SAM database users (webui, orchestrator, platform, agents). **Required** for external persistence. | string | `""` |
| `dataStores.database.supabaseTenantId` | Supabase project ID. Required when using Supabase connection pooler. | string | `""` |
| `dataStores.objectStorage.type` | Object storage type: `s3`, `azure`, or `gcs` | string | `"s3"` |
| `dataStores.objectStorage.workloadIdentity.enabled` | Enable cloud-native auth (AWS IRSA, Azure WI, GCP WI) instead of access keys | boolean | `false` |
| `dataStores.s3.endpointUrl` | S3 endpoint URL. Leave empty for AWS S3. Set for MinIO or other S3-compatible stores. | string | `""` |
| `dataStores.s3.bucketName` | S3 bucket for artifact storage | string | `""` |
| `dataStores.s3.connectorSpecBucketName` | S3 bucket for connector specs (can be same as bucketName) | string | `""` |
| `dataStores.s3.accessKey` | S3 access key ID. Omit when using workload identity. | string | `""` |
| `dataStores.s3.secretKey` | S3 secret access key. Omit when using workload identity. | string | `""` |
| `dataStores.s3.region` | AWS S3 region | string | `"us-east-1"` |
| `dataStores.azure.accountName` | Azure storage account name | string | `""` |
| `dataStores.azure.accountKey` | Azure storage account key. Omit when using workload identity. | string | `""` |
| `dataStores.azure.connectionString` | Azure storage connection string. Alternative to accountName/accountKey. | string | `""` |
| `dataStores.azure.containerName` | Azure Blob container for artifacts | string | `""` |
| `dataStores.azure.connectorSpecContainerName` | Azure Blob container for connector specs | string | `""` |
| `dataStores.gcs.project` | GCP project ID | string | `""` |
| `dataStores.gcs.credentialsJson` | GCS service account JSON credentials. Omit when using workload identity. | string | `""` |
| `dataStores.gcs.bucketName` | GCS bucket for artifacts | string | `""` |
| `dataStores.gcs.connectorSpecBucketName` | GCS bucket for connector specs | string | `""` |

### SAM Deployment

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `samDeployment.serviceAccount.name` | Service account name. Auto-generates `{release}-solace-agent-mesh-core-sa` when empty. Set explicitly for workload identity. | string | `""` |
| `samDeployment.serviceAccount.annotations` | Service account annotations for workload identity (AWS IRSA, Azure WI, GCP WI) | object | `{}` |
| `samDeployment.imagePullSecret` | Image pull secret attached to SAM service accounts. Using `global.imagePullSecrets` is preferred. | string | `""` |
| `samDeployment.image.registry` | Overrides `global.imageRegistry` for SAM image only | string | `""` |
| `samDeployment.image.repository` | SAM application image repository | string | `"solace-agent-mesh-enterprise"` |
| `samDeployment.image.tag` | SAM application image tag | string | `"1.143.0"` |
| `samDeployment.image.digest` | SAM image digest. Takes precedence over tag when set. | string | `""` |
| `samDeployment.image.pullPolicy` | Image pull policy | string | `"IfNotPresent"` |
| `samDeployment.agentDeployer.image.registry` | Overrides `global.imageRegistry` for agent deployer image only | string | `""` |
| `samDeployment.agentDeployer.image.repository` | Agent deployer image repository | string | `"sam-agent-deployer"` |
| `samDeployment.agentDeployer.image.tag` | Agent deployer image tag | string | `"1.8.2"` |
| `samDeployment.agentDeployer.image.digest` | Agent deployer image digest | string | `""` |
| `samDeployment.agentDeployer.image.pullPolicy` | Agent deployer pull policy | string | `"IfNotPresent"` |
| `samDeployment.agentDeployer.version` | Agent deployer version identifier | string | `"k8s-2.0.0"` |
| `samDeployment.agentDeployer.chartVersion` | Agent chart version | string | `"2.0.0"` |
| `samDeployment.dbInit.image.registry` | Database init container image registry override | string | `""` |
| `samDeployment.dbInit.image.repository` | Database init container image | string | `"postgres"` |
| `samDeployment.dbInit.image.tag` | Database init container tag | string | `"18.0-trixie"` |
| `samDeployment.dbInit.image.digest` | Database init image digest | string | `""` |
| `samDeployment.dbInit.image.pullPolicy` | Database init pull policy | string | `"IfNotPresent"` |
| `samDeployment.customCA.enabled` | Enable custom CA certificate injection via ConfigMap | boolean | `false` |
| `samDeployment.customCA.configMapName` | ConfigMap name containing custom CA certificates (`.crt` files) | string | `"truststore"` |
| `samDeployment.rollout.strategy` | Deployment rollout strategy | string | `"RollingUpdate"` |
| `samDeployment.podSecurityContext.runAsUser` | Pod security context user ID | integer | `10001` |
| `samDeployment.podSecurityContext.fsGroup` | Pod security context filesystem group ID | integer | `10002` |
| `samDeployment.securityContext.allowPrivilegeEscalation` | Allow privilege escalation | boolean | `false` |
| `samDeployment.securityContext.runAsUser` | Container runs as user ID | integer | `999` |
| `samDeployment.securityContext.runAsGroup` | Container runs as group ID | integer | `999` |
| `samDeployment.securityContext.runAsNonRoot` | Enforce non-root container | boolean | `true` |
| `samDeployment.nodeSelector` | Node selector for pod placement | object | `{}` |
| `samDeployment.tolerations` | Tolerations for pod scheduling | list | `[]` |
| `samDeployment.annotations` | Deployment annotations | object | `{}` |
| `samDeployment.podAnnotations` | Pod annotations | object | `{}` |
| `samDeployment.podLabels` | Pod labels | object | `{}` |
| `samDeployment.resources.sam.requests.cpu` | CPU request for SAM core container | string | `"1000m"` |
| `samDeployment.resources.sam.requests.memory` | Memory request for SAM core container | string | `"1024Mi"` |
| `samDeployment.resources.sam.limits.cpu` | CPU limit for SAM core container | string | `"2000m"` |
| `samDeployment.resources.sam.limits.memory` | Memory limit for SAM core container | string | `"2048Mi"` |
| `samDeployment.resources.agentDeployer.requests.cpu` | CPU request for agent deployer container | string | `"100m"` |
| `samDeployment.resources.agentDeployer.requests.memory` | Memory request for agent deployer container | string | `"256Mi"` |
| `samDeployment.resources.agentDeployer.limits.cpu` | CPU limit for agent deployer container | string | `"200m"` |
| `samDeployment.resources.agentDeployer.limits.memory` | Memory limit for agent deployer container | string | `"512Mi"` |

### SAM Doctor (Pre-Flight Validation)

Run sam-doctor before install/upgrade to validate configuration. For production, consider enabling to catch configuration issues early.

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `samDoctor.enabled` | Run sam-doctor validation before install/upgrade | boolean | `true` |
| `samDoctor.failOnError` | Block install/upgrade on validation failure. Set to `false` to always proceed. | boolean | `true` |
| `samDoctor.timeoutSeconds` | Hook job timeout in seconds | integer | `120` |
| `samDoctor.tlsDnsName` | DNS name for TLS certificate validation. Defaults to `sam.dnsName` if not set. | string | `""` |

### Bundled Components - Persistence Layer

Configure embedded PostgreSQL and SeaweedFS. Only used when `global.persistence.enabled: true`. Not recommended for production.

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `persistence-layer.postgresql.serviceAccountName` | Service account for PostgreSQL pod | string | `""` |
| `persistence-layer.postgresql.commonLabels` | Common labels applied to PostgreSQL resources | object | `{"app.kubernetes.io/service": "database"}` |
| `persistence-layer.postgresql.imagePullSecrets` | Image pull secrets for PostgreSQL image (merged with `global.imagePullSecrets`) | list | `[]` |
| `persistence-layer.postgresql.image.registry` | Overrides `global.imageRegistry` for PostgreSQL image | string | `""` |
| `persistence-layer.postgresql.image.repository` | PostgreSQL image repository | string | `"postgres"` |
| `persistence-layer.postgresql.image.tag` | PostgreSQL image tag | string | `"18.0-trixie"` |
| `persistence-layer.postgresql.image.digest` | PostgreSQL image digest | string | `""` |
| `persistence-layer.seaweedfs.serviceAccountName` | Service account for SeaweedFS pod | string | `""` |
| `persistence-layer.seaweedfs.commonLabels` | Common labels applied to SeaweedFS resources | object | `{"app.kubernetes.io/service": "s3"}` |
| `persistence-layer.seaweedfs.imagePullSecrets` | Image pull secrets for SeaweedFS image (merged with `global.imagePullSecrets`) | list | `[]` |
| `persistence-layer.seaweedfs.image.registry` | Overrides `global.imageRegistry` for SeaweedFS image | string | `""` |
| `persistence-layer.seaweedfs.image.repository` | SeaweedFS image repository | string | `"chrislusf/seaweedfs"` |
| `persistence-layer.seaweedfs.image.tag` | SeaweedFS image tag | string | `"3.97"` |
| `persistence-layer.seaweedfs.image.digest` | SeaweedFS image digest | string | `""` |

### Bundled Components - Embedded Broker

Configure embedded Solace PubSub+ broker. Only used when `global.broker.embedded: true`. Not recommended for production.

| Parameter | Description | Type | Default |
|-----------|-------------|------|---------|
| `embeddedBroker.imagePullSecrets` | Image pull secrets for broker image (merged with `global.imagePullSecrets`) | list | `[]` |
| `embeddedBroker.image.registry` | Overrides `global.imageRegistry` for broker image | string | `""` |
| `embeddedBroker.image.repository` | Solace broker image repository | string | `"solace-pubsub-enterprise"` |
| `embeddedBroker.image.tag` | Solace broker image tag | string | `"10.25.0.193-multi-arch"` |
| `embeddedBroker.image.digest` | Solace broker image digest | string | `""` |

---

**For complete inline documentation and examples, see the chart's `values.yaml` file.**
