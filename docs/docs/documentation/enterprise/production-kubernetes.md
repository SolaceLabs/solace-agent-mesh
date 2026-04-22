---
title: Kubernetes Production Installation
sidebar_position: 5
---

# Kubernetes Production Installation

Deploy SAM Enterprise on Kubernetes for production with full configuration, high availability, and security.

:::info
For quick evaluation, see the [Kubernetes Quick Start](./quickstart-kubernetes.md). For airgapped environments, see the [Airgap Kubernetes Installation](./airgap-kubernetes.md).
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
| **Agent** (per instance) | Runtime for each deployed agent | 175m | 200m | 625 MiB | 768 MiB | Burstable |

**Capacity Planning:**

Budget the following per concurrent agent you plan to deploy:
- **Memory Request:** 625 MiB
- **Memory Limit:** 768 MiB
- **CPU Request:** 175m (0.175 vCPU)
- **CPU Limit:** 200m (0.2 vCPU)

### External Services (Required)

Production deployments **must** use managed external services. Embedded components are not supported for production.

**Database:**
- PostgreSQL 17+ (AWS RDS, Azure Database for PostgreSQL, Cloud SQL, etc.)
- Standard username/password authentication via Kubernetes Secret
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

For detailed infrastructure guidance, see the [Kubernetes Deployment Guide](/docs/documentation/deploying/kubernetes/kubernetes-deployment-guide).

## Architecture Overview

<!-- Content: Production K8s architecture diagram -->

## Step 1: Infrastructure Preparation

<!-- Content: Cluster setup, node requirements -->

### Cluster Sizing

<!-- Content: Production cluster sizing recommendations -->

### Network Configuration

<!-- Content: Network policies, ingress, load balancers -->

### Storage Classes

<!-- Content: PVC requirements, storage class configuration -->

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

```yaml
dataStores:
  database:
    host: "your-postgres-host.rds.amazonaws.com"
    port: "5432"
    adminUsername: "postgres"
    adminPassword: "your-admin-password"
    applicationPassword: "your-app-password"
  
  objectStorage:
    type: "s3"
  
  s3:
    bucketName: "sam-artifacts"
    connectorSpecBucketName: "sam-artifacts"
    accessKey: "your-access-key"
    secretKey: "your-secret-key"
    region: "us-east-1"
```

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

<!-- Content: Complete production values.yaml template -->
