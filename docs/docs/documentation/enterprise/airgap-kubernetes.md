---
title: Air-Gapped Kubernetes Installation
sidebar_position: 6
---

# Air-Gapped Kubernetes Installation

This guide covers deploying Solace Agent Mesh Enterprise to Kubernetes clusters in air-gapped environments using Helm charts. Some features require network access to external services. Ensure the necessary routes and firewall rules are in place for any external endpoints your deployment uses (LLM, OIDC, Slack, and so on).

:::info
For internet-connected deployments, see [Kubernetes Quick Start](./quickstart-kubernetes.md) or [Production Kubernetes Installation](./production-kubernetes.md).
:::

## Prerequisites

### Required Access

- Access to the [Solace Product Portal](https://products.solace.com/prods/Agent_Mesh/Enterprise/)
- A system with internet access for downloading the Agent Mesh delivery package
- Transfer capability to move files into your air-gapped environment (USB drives, secure file transfer, and so on)

### Infrastructure Requirements

Air-gapped deployments have the same infrastructure requirements as your target deployment type, plus the following air-gapped-specific requirements. See [Kubernetes Quick Start](./quickstart-kubernetes.md#prerequisites) for evaluation or [Production Kubernetes Installation](./production-kubernetes.md#production-prerequisites) for production.

**Air-Gapped-Specific Requirements:**
- A private container registry accessible from your air-gapped cluster (Harbor, Artifactory, ECR, ACR, GCR, and so on)
- Registry credentials with push/pull permissions

**Within Air-Gapped Network:**
- Kubernetes cluster (version 1.20 or later) with standard worker nodes
- Solace event broker (external recommended for production)
- PostgreSQL 17+ database (for production)
- S3-compatible object storage (for production)
- LLM service endpoint (self-hosted or via internal proxy)
- Identity Provider (IdP) accessible within the network (for production deployments with OIDC/SSO enabled)

For detailed infrastructure requirements (node sizing, compute resources, storage classes), see [Production Prerequisites](./production-kubernetes.md#production-prerequisites).

## Step 1: Obtaining the Agent Mesh Delivery Package

### Package Contents

The Agent Mesh delivery package folder contains everything needed for an air-gapped Kubernetes deployment. No internet access is required after downloading.

**Folder structure:**

```
<enterprise-version>/
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
| `solace-agent-mesh-enterprise` | Agent Mesh core application |
| `sam-agent-deployer` | Manages agent and gateway deployments |
| `postgres` | Database init container (schema initialization on every deployment) and embedded PostgreSQL database (evaluation only) |
| `seaweedfs` | Embedded S3-compatible storage (evaluation only) |
| `solace-pubsub-enterprise` | Embedded Solace event broker (evaluation only) |

**Helm charts:**

| Chart | Description |
|-------|-------------|
| `solace-agent-mesh-<version>.tgz` | Main Agent Mesh Helm chart |
| `sam-agent-<version>.tgz` | Agent sub-chart |

**BOM files:**

| File | Use case | Images included |
|------|----------|-----------------|
| `bom.yaml` | Production (external broker + datastores) | Agent Mesh core images only (`solace-agent-mesh-enterprise`, `sam-agent-deployer`) |
| `bom-quickStart.yaml` | Evaluation (embedded broker + datastores) | All images including `solace-pubsub-enterprise`, `postgres`, `seaweedfs` |

Each BOM file lists charts and images with per-architecture paths, `file_checksum` values for verifying files before loading, and `image_id` values for verifying images after loading. For a first-time evaluation install, use `bom-quickStart.yaml`.

### Verifying Image Integrity (Optional)

For environments with compliance requirements, verify each image against the BOM in two steps.

**Step 1: Verify file integrity before loading**

```bash
sha256sum /path/to/amd64/solace-agent-mesh-enterprise.tar.gz
```

The output must match the `file_checksum` value in the BOM (excluding the `sha256:` prefix). Discard and re-download the file if they differ.

**Step 2: Verify image content after loading**

```bash
docker load -i /path/to/amd64/solace-agent-mesh-enterprise.tar.gz
docker inspect solace-agent-mesh-enterprise:<version> --format '{{.Id}}'
```

The output must match the `image_id` value in the BOM.

Repeat both steps for each image you want to load.

## Step 2: Loading Container Images

All container images are included in the package folder for both `amd64` and `arm64` architectures. No public registry access is required. Load each `.tar.gz` from your architecture directory into your private registry using your organisation's preferred tooling.

The registry path structure matters: when you set `global.imageRegistry` in `values.yaml`, the chart constructs image references as `<registry>/<repository>:<tag>`. Ensure your pushed images are reachable under those paths.

:::tip Example: docker load → tag → push
One common approach using the Docker CLI:

```bash
docker load -i /path/to/amd64/solace-agent-mesh-enterprise.tar.gz
docker tag solace-agent-mesh-enterprise:<version> your-registry.internal/solace-agent-mesh-enterprise:<version>
docker push your-registry.internal/solace-agent-mesh-enterprise:<version>
```

Repeat for each image. Exact tags are listed in `bom.yaml` or `bom-quickStart`.
:::

## Step 3: Configuring Image Pull Secrets

Your private registry requires authentication. The chart provides two mutually exclusive options. Choose one:

### Option 1: Pass a Credentials File (`global.imagePullKey`)

If your private registry provides a credentials file in Kubernetes dockerconfigjson format, the chart creates the pull secret automatically and injects it into all pod specs. The credentials file must be in dockerconfigjson format:

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

The only required change for an air-gapped deployment is pointing to your private registry. Create an `airgap-overrides.yaml` with the following content:

```yaml
global:
  # Redirect all images to your private registry
  imageRegistry: registry.internal.example.com/sam
```

For registry authentication, see [Step 3: Configuring Image Pull Secrets](#step-3-configuring-image-pull-secrets).

This configuration is sufficient for **evaluation**. Embedded broker and persistence are used by default, as in the [Kubernetes Quick Start](./quickstart-kubernetes.md).

For **production** air-gapped deployments, also configure external components. See [Step 3: Helm Chart Configuration](./production-kubernetes.md#step-3-helm-chart-configuration) in the Production guide.

## Step 5: Custom CA Certificates (If Required)

If your environment uses custom or self-signed CA certificates for internal infrastructure (Solace broker, OIDC providers, LLM services), configure this before the Helm install. Pods make outbound calls to these endpoints at startup and the CA bundle must be in place first.

Agent Mesh supports custom CA certificate injection via Kubernetes ConfigMap. See [Custom CA Certificates](./production-kubernetes.md#custom-ca-certificates) in the Production guide for complete setup instructions. The same configuration applies to air-gapped deployments:

```yaml
samDeployment:
  customCA:
    enabled: true
    configMapName: "truststore"
```

If your environment does not use custom CA certificates, skip this step.

## Step 6: Installing Agent Mesh with Helm

For dry-run validation before installing, see [Step 4: Pre-Installation Validation](./production-kubernetes.md#step-4-pre-installation-validation) in the Production guide. The same approaches apply.

Install Agent Mesh using the local chart downloaded earlier and the `airgap-overrides.yaml` file you created in Step 4.

**Option 1** — with a credentials file (from Step 3, Option 1):

```bash
helm install sam /path/to/charts/solace-agent-mesh-<version>.tgz \
  --namespace sam \
  --create-namespace \
  --set-file global.imagePullKey=registry-credentials.json \
  -f airgap-overrides.yaml
```

**Option 2** — with a pre-created secret (from Step 3, Option 2):

```bash
helm install sam /path/to/charts/solace-agent-mesh-<version>.tgz \
  --namespace sam \
  --create-namespace \
  -f airgap-overrides.yaml
```

## Step 7: Post-Installation Configuration

### Verify All Pods are Running

Wait for all pods to reach `Running` status:

```bash
kubectl get pods -n sam -l app.kubernetes.io/instance=sam -w
```

Press `Ctrl-C` after all pods show `Running` status. For additional post-installation steps by deployment type, see [Quick Start: Step 2](./quickstart-kubernetes.md#step-2-wait-for-installation-to-complete) (evaluation) or [Production: Step 6](./production-kubernetes.md#step-6-post-installation-configuration) (production).

### Access the WebUI

**For evaluation:** see [Step 3: Access the WebUI](./quickstart-kubernetes.md#step-3-access-the-webui) in the Quick Start guide.

**For production:** access is via Ingress or LoadBalancer as configured in your `airgap-overrides.yaml`.

### First Login

For first login guidance (OIDC redirect vs LLM prompt), see [First Login](./production-kubernetes.md#first-login) in the Production guide.

:::info Air-Gapped Note
Ensure your LLM endpoint and OIDC provider are accessible from within the air-gapped network before logging in.
:::

### Health Checks

Verify Agent Mesh is healthy after installation:

```bash
curl -s https://<your-sam-domain>/health
curl -s https://<your-sam-domain>/api/v1/platform/health
```

Both endpoints should return a successful response. For detailed probe configuration, see [Health Checks](/docs/documentation/deploying/health-checks).

## Air-Gapped-Specific Considerations

### Components Requiring External Connectivity

The following Agent Mesh components require internet access or external service connectivity to function. In air-gapped environments, you must provide alternative solutions:

### Solace Broker Configuration

Configure your external Solace broker within the air-gapped network.

**Queue Template Configuration:**

For Kubernetes deployments, configure durable queues with message TTL. See [Queue Template Configuration for Kubernetes](./production-kubernetes.md#queue-template-configuration-for-kubernetes) in the Production guide for detailed setup instructions. The same configuration applies to air-gapped deployments.

### LLM Service Configuration

In air-gapped environments, ensure your LLM service endpoint is accessible from within the isolated network.

**Configuration Options:**

**Option 1: Post-Install via Model Config UI**

On first login to the Console UI, you are prompted to configure your LLM provider. Ensure the LLM endpoint is accessible from your air-gapped network.

**Option 2: Pre-Configure via values.yaml**

Add LLM configuration to your `airgap-overrides.yaml`:

```yaml
llmService:
  llmServiceEndpoint: "https://llm.internal.example.com/v1"
  llmServiceApiKey: "your-api-key"
  planningModel: "gpt-4o"
  generalModel: "gpt-4o"
```

:::warning Credential Security
Do not store API keys or passwords directly in `values.yaml` or `airgap-overrides.yaml`. Use `extraSecretEnvironmentVars` to reference existing Kubernetes Secrets instead. See [Secret Management](./production-kubernetes.md#secret-management) in the Production guide.
:::

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

:::warning Credential Security
Do not store `accessKey` or `secretKey` directly in `values.yaml`. Use `extraSecretEnvironmentVars` to reference existing Kubernetes Secrets instead. See [Secret Management](./production-kubernetes.md#secret-management) in the Production guide.
:::

Agents authenticate to download connector specs using the same credentials as artifact storage.

## Troubleshooting

### Image Pull Failures

If pods enter `ImagePullBackOff`, the images are not reachable from the registry path the chart constructs:

```bash
kubectl describe pod -n sam <pod-name> | grep -A5 "Failed\|Error"
```

Check that:
- `global.imageRegistry` in your values file matches the registry prefix you used when pushing images
- The image pull secret is correctly configured (see [Step 3](#step-3-configuring-image-pull-secrets))
- Your private registry is accessible from within the cluster network

### CA Trust Errors

If pods fail with TLS handshake errors when connecting to your LLM, OIDC provider, or Solace broker, your custom CA is not trusted. Verify that the `truststore` ConfigMap exists and that `samDeployment.customCA.enabled: true` is set before running `helm install`. See [Step 5: Custom CA Certificates](#step-5-custom-ca-certificates-if-required).

### Pods Not Starting

Inspect pod events and logs:

```bash
kubectl get pods -n sam
kubectl describe pod -n sam <pod-name>
kubectl logs -n sam <pod-name>
```

### Health Check Endpoints Not Responding

After the port-forward is running, verify Agent Mesh is healthy:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8080/api/v1/platform/health
```

If using Ingress, replace `localhost` with your domain. For detailed probe configuration, see [Health Checks](/docs/documentation/deploying/health-checks).

## Additional Resources

- [Kubernetes Quick Start](./quickstart-kubernetes.md) - Quick evaluation setup
- [Production Kubernetes Installation](./production-kubernetes.md) - Production deployment and infrastructure requirements
- [RBAC Setup Guide](./rbac-setup-guide.md) - Access control configuration
- [Single Sign-On](./single-sign-on.md) - Authentication setup
