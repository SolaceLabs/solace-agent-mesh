---
title: Air-Gapped Kubernetes Installation
sidebar_position: 6
---

# Air-Gapped Kubernetes Installation

This guide covers deploying Agent Mesh Enterprise (SAM) to Kubernetes clusters in air-gapped environments using Helm charts.

:::info
For internet-connected deployments, see [Kubernetes Quick Start](./quickstart-kubernetes.md) or [Production Kubernetes Installation](./production-kubernetes.md).
:::

## What is an Air-Gapped Deployment?

An air-gapped deployment runs in an environment with no direct internet connectivity. All container images, dependencies, and artifacts must be pre-loaded into private registries within the isolated network. This approach ensures compliance with security policies while maintaining full SAM functionality.

Air-gapped installations are common in regulated industries such as financial services, government, and healthcare where security policies require complete network isolation.

## Prerequisites

### Required Access

- Access to the [Solace Product Portal](https://products.solace.com/prods/Agent_Mesh/Enterprise/)
- A system with internet access for downloading the SAM delivery bundle
- Transfer capability to move files into your air-gapped environment (USB drives, secure file transfer, etc.)

### Infrastructure Requirements

Air-gapped deployments have the same infrastructure requirements as your target deployment type — see [Kubernetes Quick Start](./quickstart-kubernetes.md#prerequisites) for evaluation or [Production Kubernetes Installation](./production-kubernetes.md#production-prerequisites) for production — plus the following air-gapped-specific requirements:

**Air-Gapped-Specific Requirements:**
- A private container registry accessible from your air-gapped cluster (Harbor, Artifactory, ECR, ACR, GCR, etc.)
- Registry credentials with push/pull permissions

**Within Air-Gapped Network:**
- Kubernetes cluster (version 1.20 or later) with standard worker nodes
- Solace event broker (external recommended for production)
- PostgreSQL 17+ database (for production)
- S3-compatible object storage (for production)
- LLM service endpoint (self-hosted or via internal proxy)
- Identity Provider (IdP) accessible within the network (for production deployments with OIDC/SSO enabled)

For detailed infrastructure requirements (node sizing, compute resources, storage classes), see [Production Prerequisites](./production-kubernetes.md#production-prerequisites).

## Understanding the Air-Gapped Installation Process

## Step 1: Obtaining the SAM Delivery Bundle

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
| `postgres` | Database init container (schema initialization on every deployment) and embedded PostgreSQL database (evaluation only) |
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

## Step 2: Loading Container Images

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

## Step 3: Configuring Image Pull Secrets

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

## Step 4: Configuring values.yaml for Air-Gapped

The only required change for an air-gapped deployment is pointing to your private registry. Create an `airgap-overrides.yaml` with:

```yaml
global:
  # Redirect all images to your private registry
  imageRegistry: registry.internal.example.com/sam
```

For registry authentication, see [Step 3: Configuring Image Pull Secrets](#step-3-configuring-image-pull-secrets).

This is sufficient for **evaluation** — embedded broker and persistence are used by default, just as in the [Kubernetes Quick Start](./quickstart-kubernetes.md).

For **production** air-gapped deployments, also configure external components — see [Step 3: Helm Chart Configuration](./production-kubernetes.md#step-3-helm-chart-configuration) in the Production guide.

## Step 5: Installing SAM with Helm

For dry-run validation before installing, see [Step 4: Pre-Installation Validation](./production-kubernetes.md#step-4-pre-installation-validation) in the Production guide — the same approaches apply.

Install SAM in your air-gapped environment with your custom overrides:

```bash
helm install sam /../bundle/charts/solace-agent-mesh-<version>.tgz \
  --namespace sam \
  --create-namespace \
  -f airgap-overrides.yaml
```

## Step 6: Post-Installation Configuration

### Verify All Pods are Running

**For evaluation** — see [Step 2: Wait for Installation to Complete](./quickstart-kubernetes.md#step-2-wait-for-installation-to-complete) in the Quick Start guide.

**For production** — see [Step 6: Post-Installation Configuration](./production-kubernetes.md#step-6-post-installation-configuration) in the Production guide.

### Access the WebUI

**For evaluation** — see [Step 3: Access the WebUI](./quickstart-kubernetes.md#step-3-access-the-webui) in the Quick Start guide.

**For production** — access is via Ingress or LoadBalancer as configured in your `airgap-overrides.yaml`.

### First Login

For first login guidance (OIDC redirect vs LLM prompt), see [First Login](./production-kubernetes.md#first-login) in the Production guide.

:::info Air-Gapped Note
Ensure your LLM endpoint and OIDC provider are accessible from within the air-gapped network before logging in.
:::

### Health Checks

Verify SAM is healthy after installation:

```bash
curl -s https://<your-sam-domain>/health
curl -s https://<your-sam-domain>/api/v1/platform/health
```

Both endpoints should return a successful response. For detailed probe configuration, see [Health Checks](/docs/documentation/deploying/health-checks).

## Air-Gapped-Specific Considerations

### Custom CA Certificates

Air-gapped environments often use custom or self-signed CA certificates for internal infrastructure (Solace broker, OIDC providers, LLM services).

SAM supports custom CA certificate injection via Kubernetes ConfigMap. See [Custom CA Certificates](./production-kubernetes.md#custom-ca-certificates) in the Production guide for complete setup instructions.

The same configuration applies to air-gapped deployments:

```yaml
samDeployment:
  customCA:
    enabled: true
    configMapName: "truststore"
```

### Components Requiring External Connectivity

The following SAM components require internet access or external service connectivity to function. In air-gapped environments, you must provide alternative solutions:

### Solace Broker Configuration

Configure your external Solace broker within the air-gapped network.

**Queue Template Configuration:**

For Kubernetes deployments, configure durable queues with message TTL. See [Queue Template Configuration for Kubernetes](./production-kubernetes.md#queue-template-configuration-for-kubernetes) in the Production guide for detailed setup instructions. The same configuration applies to air-gapped deployments.

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

## Additional Resources

- [Kubernetes Quick Start](./quickstart-kubernetes.md) - Quick evaluation setup
- [Production Kubernetes Installation](./production-kubernetes.md) - Production deployment and infrastructure requirements
- [RBAC Setup Guide](./rbac-setup-guide.md) - Access control configuration
- [Single Sign-On](./single-sign-on.md) - Authentication setup
