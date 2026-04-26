---
title: Air-Gapped Kubernetes Installation
sidebar_position: 7
---

# Air-Gapped Kubernetes Installation

This guide covers deploying Agent Mesh Enterprise (SAM) to Kubernetes clusters in air-gapped environments using Helm charts.

:::info
For internet-connected deployments, see [Kubernetes Quick Start](./quickstart-kubernetes.md) or [Production Kubernetes Installation](./production-kubernetes.md).
:::

## What is an Air-Gapped Deployment?

An air-gapped deployment runs in an environment with no direct internet connectivity. All container images, dependencies, and artifacts must be pre-loaded into private registries within the isolated network. This approach ensures compliance with security policies while maintaining full SAM functionality.

Air-gapped installations are common in regulated industries such as financial services, government, and healthcare where security policies require complete network isolation.

:::info
Air-gapped deployments require advance planning for image distribution, dependency management, and component configuration. Review this entire guide before beginning your installation.
:::

## Prerequisites

### Required Access

- Access to the [Solace Product Portal](https://products.solace.com/prods/Agent_Mesh/Enterprise/)
- A system with internet access for downloading the SAM delivery bundle
- Transfer capability to move files into your air-gapped environment (USB drives, secure file transfer, etc.)

### Infrastructure Requirements

Air-gapped deployments have the same infrastructure requirements as [Production Kubernetes Installation](./production-kubernetes.md#production-prerequisites), plus the following air-gapped-specific requirements:

**Air-Gapped-Specific Requirements:**
- A private container registry accessible from your air-gapped cluster (Harbor, Artifactory, ECR, ACR, GCR, etc.)
- Registry credentials with push/pull permissions
- Ability to transfer files into the air-gapped environment (USB, secure file transfer, etc.)
- System with internet access for downloading the SAM delivery bundle

**Within Air-Gapped Network:**
- Kubernetes cluster (version 1.20 or later) with standard worker nodes
- Private container registry (all SAM images must be mirrored)
- Solace event broker (external recommended for production)
- PostgreSQL 17+ database (for production)
- S3-compatible object storage (for production)
- LLM service endpoint (self-hosted or via internal proxy)
- Identity Provider (IdP) accessible within the network (for OIDC/SSO)

For detailed infrastructure requirements (node sizing, compute resources, storage classes), see [Production Prerequisites](./production-kubernetes.md#production-prerequisites).

## Understanding the Air-Gapped Installation Process

<!-- Content: Overview of the air-gapped installation workflow -->

## Step 1: Obtaining the SAM Delivery Bundle

<!-- Content: How to download bundle from Solace Product Portal -->

### Bundle Contents

The SAM delivery bundle contains everything needed for an air-gapped Kubernetes deployment — no internet access required after downloading.

**Bundle structure:**

```
bundle/
├── amd64/
│   ├── postgres.tar.gz
│   ├── sam-agent-deployer.tar.gz
│   ├── seaweedfs.tar.gz
│   ├── solace-agent-mesh-enterprise.tar.gz
│   └── solace-pubsub-enterprise.tar.gz
├── arm64/
│   ├── postgres.tar.gz
│   ├── sam-agent-deployer.tar.gz
│   ├── seaweedfs.tar.gz
│   ├── solace-agent-mesh-enterprise.tar.gz
│   └── solace-pubsub-enterprise.tar.gz
├── charts/
│   ├── solace-agent-mesh-<version>.tgz
│   └── sam-agent-<version>.tgz
├── bom.yaml
└── bom-quickStart.yaml
```

**Container images** (available for both `amd64` and `arm64`):

| Image | Description |
|-------|-------------|
| `solace-agent-mesh-enterprise` | SAM core application |
| `sam-agent-deployer` | Manages agent and gateway deployments |
| `postgres` | Embedded PostgreSQL (evaluation only) |
| `seaweedfs` | Embedded S3-compatible storage (evaluation only) |
| `solace-pubsub-enterprise` | Embedded Solace event broker (evaluation only) |

**Helm charts:**

| Chart | Description |
|-------|-------------|
| `solace-agent-mesh-<version>.tgz` | Main SAM Helm chart |
| `sam-agent-<version>.tgz` | Agent sub-chart |

**BOM files:**

| File | Use case | Images included |
|------|----------|-----------------|
| `bom.yaml` | Production (external broker + datastores) | SAM core images only (`solace-agent-mesh-enterprise`, `sam-agent-deployer`) |
| `bom-quickStart.yaml` | Evaluation (embedded broker + datastores) | All images including `solace-pubsub-enterprise`, `postgres`, `seaweedfs` |

Each BOM file lists charts and images with per-architecture paths and `sha256` digests for integrity verification.

### Verifying Bundle Integrity

<!-- Content: Checksum verification instructions -->

### Understanding the Bill of Materials

<!-- Content: Document BOM/dependency manifest format -->

### Extract the Bundle

<!-- Content: How to extract and prepare bundle -->

## Step 2: Preparing Your Private Registry

<!-- Content: Overview of registry setup -->

### Supported Registry Types

<!-- Content: List compatible private registries -->

### Registry Authentication

<!-- Content: How to authenticate to your registry -->

### Certificate Authority Configuration

<!-- Content: CA configuration for private registries with self-signed certs -->

## Step 3: Loading Container Images

All container images are included in the bundle for both `amd64` and `arm64` architectures — no public registry access required. Load each `.tar.gz` from your architecture directory into your private registry using your organisation's preferred tooling.

The registry path structure matters: when you set `global.imageRegistry` in `values.yaml`, the chart constructs image references as `<registry>/<repository>:<tag>`. Ensure your pushed images are reachable under those paths.

:::tip Example: docker load → tag → push
One common approach using the Docker CLI:

```bash
docker load -i bundle/amd64/solace-agent-mesh-enterprise.tar.gz
docker tag solace-agent-mesh-enterprise:<version> your-registry.internal/solace-agent-mesh-enterprise:<version>
docker push your-registry.internal/solace-agent-mesh-enterprise:<version>
```

Repeat for each image in the bundle. Exact tags are listed in `bom.yaml`.
:::

### Registry-Specific Examples

<!-- Content: Registry-specific authentication and push commands -->

### Verifying Image Availability

<!-- Content: How to verify all images are loaded correctly -->

## Step 4: Verifying Dependencies Using the BOM

<!-- Content: Dependency verification -->

### Automated Verification

<!-- Content: Using verification scripts if available -->

### Manual Verification

<!-- Content: How to manually verify against BOM -->

### Identifying Missing Components

<!-- Content: How to identify missing images or components -->

## Step 5: Creating Kubernetes Namespace

<!-- Content: Namespace creation for air-gapped -->

## Step 6: Configuring Image Pull Secrets

Your private registry requires authentication. The chart provides two mutually exclusive options — choose one:

### Option 1: Pass a Credentials File (`global.imagePullKey`)

If your private registry provides a credentials file in Kubernetes dockerconfigjson format, pass it directly to Helm. The chart automatically creates the pull secret and injects it into all pod specs:

```bash
helm install sam solace/solace-agent-mesh \
  --namespace sam \
  --set-file global.imagePullKey=registry-credentials.json \
  -f airgap-overrides.yaml
```

The credentials file must be in dockerconfigjson format:

```json
{
  ".dockerconfigjson": "<base64-encoded-auth>"
}
```

### Option 2: Reference a Pre-Created Secret (`global.imagePullSecrets`)

If you have already created a Kubernetes image pull secret (common with enterprise registries such as Harbor or Artifactory), reference it by name in your `airgap-overrides.yaml`:

```yaml
global:
  imagePullSecrets:
    - name: your-registry-secret
```

:::warning Mutually Exclusive
`global.imagePullKey` and `global.imagePullSecrets` cannot be used together. Providing both will cause the Helm installation to fail with a clear error.
:::

## Step 7: Configuring values.yaml for Air-Gapped

<!-- Content: Comprehensive values.yaml configuration -->

### Minimal Air-Gapped Configuration

The only required change for an air-gapped deployment is pointing to your private registry. Create an `airgap-overrides.yaml` with:

```yaml
global:
  # Redirect all images to your private registry
  imageRegistry: registry.internal.example.com/sam
```

For registry authentication, see [Step 6: Configuring Image Pull Secrets](#step-6-configuring-image-pull-secrets).

This is sufficient for **evaluation** — embedded broker and persistence are used by default, just as in the [Kubernetes Quick Start](./quickstart-kubernetes.md).

For **production** air-gapped deployments, also configure external components — see [Core Configuration](./production-kubernetes.md#core-configuration) in the Production guide.

:::info Bundled Agent Charts
The SAM Helm chart always bundles the agent chart (as `sam-agent-{version}.tgz`). No additional configuration is required to enable local chart support for air-gapped deployments — it works out of the box.
:::

### Production Air-Gapped Configuration

<!-- Content: Production settings for air-gapped -->

## Step 8: Installing SAM with Helm

Install SAM in your air-gapped environment with your custom overrides:

```bash
helm install sam ./solace-agent-mesh-chart.tgz \
  --namespace sam \
  --create-namespace \
  -f airgap-overrides.yaml
```

Note: Use the local chart archive (`.tgz`) from your SAM delivery bundle, not the remote Helm repository.

### Dry Run Installation

<!-- Content: How to validate config before applying -->

### Monitor Installation Progress

<!-- Content: How to watch installation progress -->

## Step 9: Post-Installation Configuration

<!-- Content: Post-install configuration steps -->

### Verify All Pods are Running

Wait for all pods to be ready:

```bash
kubectl get pods -n sam -l app.kubernetes.io/instance=sam -w
```

Press `Ctrl-C` once all pods show `Running` status.

### First Login

**With OIDC configured:**

On first login you will be redirected to your identity provider. Before logging in, ensure your OIDC callback URI is registered with your provider:

```
https://<your-sam-domain>/callback
```

**Without OIDC:**

On first login you'll be prompted to configure your LLM API key via the Model Configuration UI. Ensure your LLM endpoint is accessible from within the air-gapped network.

### Configure RBAC

<!-- Content: RBAC setup for air-gapped -->

### Set Up Ingress

<!-- Content: Internal ingress setup -->

## Step 10: Validation and Testing

<!-- Content: Validation procedures -->

### Health Check Endpoints

Verify SAM is healthy after installation:

```bash
curl -s https://<your-sam-domain>/health
curl -s https://<your-sam-domain>/api/v1/platform/health
```

Both endpoints should return a successful response.

For detailed probe configuration, see [Health Checks](/docs/documentation/deploying/health-checks).

### Validate Image Sources

<!-- Content: Confirm pods use private registry -->

Verify that all pods are using images from your private registry and that air-gapped mode (bundled agent charts) is active.

### Test Agent Deployment

<!-- Content: Deploy test agent to validate -->

### Network Isolation Verification

<!-- Content: Confirm no external egress -->

## Air-Gapped-Specific Considerations

<!-- Content: Air-gapped specific considerations overview -->

### Components Requiring External Connectivity

The following SAM components require internet access or external service connectivity to function. In air-gapped environments, you must provide alternative solutions:

### Solace Broker Configuration

Configure your external Solace broker within the air-gapped network.

**Queue Template Configuration:**

For Kubernetes deployments, configure durable queues with message TTL. See [Queue Template Configuration for Kubernetes](./production-kubernetes.md#queue-template-configuration-for-kubernetes) in the Production guide for detailed setup instructions. The same configuration applies to air-gapped deployments.

#### Bedrock Knowledge Base Tool

<!-- Content: Bedrock tool air-gapped configuration -->

#### Slack Gateway Adapter

<!-- Content: Slack gateway air-gapped configuration -->

#### Teams Gateway Adapter

<!-- Content: Teams gateway air-gapped configuration -->

### LLM Service Configuration

In air-gapped environments, ensure your LLM service endpoint is accessible from within the isolated network.

**Configuration Options:**

**Option 1: Post-Install via Model Config UI**

On first login to the Console UI, you'll be prompted to configure your LLM provider. Ensure the LLM endpoint is accessible from your air-gapped network.

**Option 2: Pre-Configure via values.yaml**

Add LLM configuration to your `airgap-overrides.yaml`:

```yaml
llmService:
  llmServiceEndpoint: "https://llm.internal.example.com/v1"
  llmServiceApiKey: "your-api-key"
  planningModel: "gpt-4o"
  generalModel: "gpt-4o"
```

**LLM Deployment Options in Air-Gapped:**
- Self-hosted LLM within the air-gapped network
- Azure OpenAI with private endpoints
- AWS Bedrock with VPC endpoints
- Internal LLM proxy service

### Storage Services

Configure S3-compatible object storage accessible within your air-gapped network.

**Storage Requirements:**

1. **Artifact Storage** - For user files, session data, and artifacts
2. **OpenAPI Connector Specs Storage** (if using OpenAPI Connectors)

**Air-Gapped-Specific Considerations:**

Unlike internet-connected deployments, air-gapped environments cannot use public S3 buckets. Both artifact storage and connector specs storage must be accessible within the air-gapped network using internal S3-compatible storage or cloud storage with private endpoints.

#### OpenAPI Connector Specs in Air-Gapped

**Key Difference from Internet-Connected Deployments:**

In internet-connected environments, the connector specs bucket uses public read access. In air-gapped environments, you must configure authenticated access for agents:

```yaml
dataStores:
  objectStorage:
    type: "s3"
  
  s3:
    endpointUrl: "https://storage.internal.example.com"  # Internal S3 endpoint
    bucketName: "sam-artifacts"
    connectorSpecBucketName: "sam-connector-specs"  # Same auth as artifacts
    region: "us-east-1"
    accessKey: "..."  # Agents use credentials for both buckets
    secretKey: "..."
```

**No Public Access Required:** Agents authenticate to download connector specs using the same credentials as artifact storage.

Configure identical access credentials for both buckets in your Helm values.

### Custom CA Certificates

Air-gapped environments often use custom or self-signed CA certificates for internal infrastructure (Solace broker, OIDC providers, LLM services).

SAM supports custom CA certificate injection via Kubernetes ConfigMap. See [Custom CA Certificates](./production-kubernetes.md#custom-ca-certificates-for-internal-infrastructure) in the Production guide for complete setup instructions.

The same configuration applies to air-gapped deployments:

```yaml
samDeployment:
  customCA:
    enabled: true
    configMapName: "truststore"
```

## Security Best Practices

<!-- Content: Security for air-gapped deployments -->

### Network Policies

<!-- Content: Network policy examples -->

### Secret Management

<!-- Content: Secret management in air-gapped -->

### Monitoring and Auditing

<!-- Content: Monitoring for air-gapped -->

## Troubleshooting Air-Gapped Installations

<!-- Content: Common air-gapped issues -->

### Image Pull Failures

<!-- Content: Troubleshooting image pull errors -->

### Dependency Resolution Failures

<!-- Content: Troubleshooting missing dependencies -->

### Certificate Trust Issues

<!-- Content: Troubleshooting TLS/cert problems -->

### Storage Connectivity Problems

<!-- Content: Troubleshooting storage issues -->

## Updating Air-Gapped Kubernetes Deployments

<!-- Content: Update procedures -->

### Preparing for Updates

<!-- Content: Pre-update checklist -->

### Performing Rolling Update

<!-- Content: Helm upgrade for air-gapped -->

### Rollback Procedure

<!-- Content: How to rollback -->

## Reference

<!-- Content: Complete configuration templates -->

## Additional Resources

- [Kubernetes Quick Start](./quickstart-kubernetes.md) - Quick evaluation setup
- [Production Kubernetes Installation](./production-kubernetes.md) - Production deployment and infrastructure requirements
- [RBAC Setup Guide](./rbac-setup-guide.md) - Access control configuration
- [Single Sign-On](./single-sign-on.md) - Authentication setup
