---
title: Airgap Kubernetes Installation
sidebar_position: 7
---

# Airgap Kubernetes Installation

This guide covers deploying Agent Mesh Enterprise (SAM) to Kubernetes clusters in airgapped environments using Helm charts.

:::info
For internet-connected deployments, see [Kubernetes Quick Start](./quickstart-kubernetes.md) or [Production Kubernetes Installation](./production-kubernetes.md).
:::

## What is an Airgap Deployment?

An airgap deployment runs in an environment with no direct internet connectivity. All container images, dependencies, and artifacts must be pre-loaded into private registries within the isolated network. This approach ensures compliance with security policies while maintaining full SAM functionality.

Airgap installations are common in regulated industries such as financial services, government, and healthcare where security policies require complete network isolation.

:::info
Airgap deployments require advance planning for image distribution, dependency management, and component configuration. Review this entire guide before beginning your installation.
:::

## Prerequisites

### Required Access

- Access to the [Solace Product Portal](https://products.solace.com/prods/Agent_Mesh/Enterprise/)
- A system with internet access for downloading the SAM delivery bundle
- Transfer capability to move files into your airgapped environment (USB drives, secure file transfer, etc.)

### Infrastructure Requirements

Airgap deployments have the same infrastructure requirements as [Production Kubernetes Installation](./production-kubernetes.md#production-prerequisites), plus the following airgap-specific requirements:

**Airgap-Specific Requirements:**
- A private container registry accessible from your airgapped cluster (Harbor, Artifactory, ECR, ACR, GCR, etc.)
- Registry credentials with push/pull permissions
- Ability to transfer files into the airgapped environment (USB, secure file transfer, etc.)
- System with internet access for downloading the SAM delivery bundle

**Within Airgapped Network:**
- Kubernetes cluster (version 1.20 or later) with standard worker nodes
- Private container registry (all SAM images must be mirrored)
- Solace event broker (external recommended for production)
- PostgreSQL 17+ database (for production)
- S3-compatible object storage (for production)
- LLM service endpoint (self-hosted or via internal proxy)
- Identity Provider (IdP) accessible within the network (for OIDC/SSO)

For detailed infrastructure requirements (node sizing, compute resources, storage classes), see [Production Prerequisites](./production-kubernetes.md#production-prerequisites).

## Understanding the Airgap Installation Process

<!-- Content: Overview of the airgap installation workflow -->

## Step 1: Obtaining the SAM Delivery Bundle

<!-- Content: How to download bundle from Solace Product Portal -->

### Bundle Contents

<!-- Content: List what's in the bundle -->

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

<!-- Content: Image pre-loading procedures -->

### Loading Images from Bundle

<!-- Content: How to load images from tar files -->

### Retagging for Your Private Registry

<!-- Content: Retagging requirements -->

### Pushing Images to Private Registry

<!-- Content: How to push images -->

### Registry-Specific Examples

#### Harbor

<!-- Content: Harbor-specific commands -->

#### Artifactory

<!-- Content: Artifactory-specific commands -->

#### AWS Elastic Container Registry (ECR)

<!-- Content: ECR-specific commands -->

#### Azure Container Registry (ACR)

<!-- Content: ACR-specific commands -->

#### Google Artifact Registry

<!-- Content: GCR-specific commands -->

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

<!-- Content: Namespace creation for airgap -->

## Step 6: Configuring Image Pull Secrets

<!-- Content: Creating and configuring image pull secrets -->

### Create Image Pull Secret

<!-- Content: kubectl create secret commands -->

### Registry-Specific Image Pull Secrets

<!-- Content: Examples for different registries -->

## Step 7: Configuring values.yaml for Airgap

<!-- Content: Comprehensive values.yaml configuration -->

### Minimal Airgap Configuration

Create an airgap overrides file (`airgap-overrides.yaml`) with the following settings:

**Configure Private Registry:**

```yaml
global:
  # Redirect all images to your private registry
  imageRegistry: registry.internal.example.com/sam
  
  # Image pull secrets for your private registry
  imagePullSecrets:
    - name: your-registry-secret
```

**Enable Bundled Agent Charts:**

```yaml
samDeployment:
  agentDeployer:
    localCharts:
      enabled: true  # Use bundled agent chart instead of remote
```

**Disable Embedded Components (use external):**

```yaml
global:
  broker:
    embedded: false  # Use external Solace broker in airgapped network
  persistence:
    enabled: false   # Use external datastores in airgapped network

broker:
  url: "tcps://broker.internal.example.com:55443"
  # ... other broker config

dataStores:
  # ... external datastore config
```

:::info Remote vs Local Agent Charts
- **Remote mode** (`localCharts.enabled: false`): Agent charts fetched from `samDeployment.agentDeployer.chartBaseUrl`
- **Airgap mode** (`localCharts.enabled: true`): Agent charts bundled within the installation
:::

### Production Airgap Configuration

<!-- Content: Production settings for airgap -->

## Step 8: Installing SAM with Helm

Install SAM in your airgapped environment with your custom overrides:

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

<!-- Content: How to check pod status -->

### Configure RBAC

<!-- Content: RBAC setup for airgap -->

### Set Up Ingress

<!-- Content: Internal ingress setup -->

## Step 10: Validation and Testing

<!-- Content: Validation procedures -->

### Health Check Endpoints

<!-- Content: How to check health endpoints -->

### Validate Image Sources

<!-- Content: Confirm pods use private registry -->

Verify that all pods are using images from your private registry and that airgap mode (bundled agent charts) is active.

### Test Agent Deployment

<!-- Content: Deploy test agent to validate -->

### Network Isolation Verification

<!-- Content: Confirm no external egress -->

## Airgap-Specific Considerations

<!-- Content: Airgap specific considerations overview -->

### Components Requiring External Connectivity

The following SAM components require internet access or external service connectivity to function. In airgapped environments, you must provide alternative solutions:

### Solace Broker Configuration

Configure your external Solace broker within the airgapped network.

**Queue Template Configuration:**

For Kubernetes deployments, configure durable queues with message TTL. See [Queue Template Configuration for Kubernetes](./production-kubernetes.md#queue-template-configuration-for-kubernetes) in the Production guide for detailed setup instructions. The same configuration applies to airgap deployments.

#### Bedrock Knowledge Base Tool

<!-- Content: Bedrock tool airgap configuration -->

#### Slack Gateway Adapter

<!-- Content: Slack gateway airgap configuration -->

#### Teams Gateway Adapter

<!-- Content: Teams gateway airgap configuration -->

### LLM Service Configuration

In airgapped environments, ensure your LLM service endpoint is accessible from within the isolated network.

**Configuration Options:**

**Option 1: Post-Install via Model Config UI**

On first login to the Console UI, you'll be prompted to configure your LLM provider. Ensure the LLM endpoint is accessible from your airgapped network.

**Option 2: Pre-Configure via values.yaml**

Add LLM configuration to your `airgap-overrides.yaml`:

```yaml
llmService:
  llmServiceEndpoint: "https://llm.internal.example.com/v1"
  llmServiceApiKey: "your-api-key"
  planningModel: "gpt-4o"
  generalModel: "gpt-4o"
```

**LLM Deployment Options in Airgap:**
- Self-hosted LLM within the airgapped network
- Azure OpenAI with private endpoints
- AWS Bedrock with VPC endpoints
- Internal LLM proxy service

### Storage Services

Configure S3-compatible object storage accessible within your airgapped network.

**Storage Requirements:**

1. **Artifact Storage** - For user files, session data, and artifacts
2. **OpenAPI Connector Specs Storage** (if using OpenAPI Connectors)

**Airgap-Specific Considerations:**

Unlike internet-connected deployments, airgap environments cannot use public S3 buckets. Both artifact storage and connector specs storage must be accessible within the airgapped network using internal S3-compatible storage or cloud storage with private endpoints.

#### OpenAPI Connector Specs in Airgap

**Key Difference from Internet-Connected Deployments:**

In internet-connected environments, the connector specs bucket uses public read access. In airgap environments, you must configure authenticated access for agents:

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

## Security Best Practices

<!-- Content: Security for airgap deployments -->

### Network Policies

<!-- Content: Network policy examples -->

### Secret Management

<!-- Content: Secret management in airgap -->

### Monitoring and Auditing

<!-- Content: Monitoring for airgap -->

## Troubleshooting Airgap Installations

<!-- Content: Common airgap issues -->

### Image Pull Failures

<!-- Content: Troubleshooting image pull errors -->

### Dependency Resolution Failures

<!-- Content: Troubleshooting missing dependencies -->

### Certificate Trust Issues

<!-- Content: Troubleshooting TLS/cert problems -->

### Storage Connectivity Problems

<!-- Content: Troubleshooting storage issues -->

## Updating Airgap Kubernetes Deployments

<!-- Content: Update procedures -->

### Preparing for Updates

<!-- Content: Pre-update checklist -->

### Performing Rolling Update

<!-- Content: Helm upgrade for airgap -->

### Rollback Procedure

<!-- Content: How to rollback -->

## Reference

<!-- Content: Complete configuration templates -->

## Additional Resources

- [Kubernetes Quick Start](./quickstart-kubernetes.md) - Quick evaluation setup
- [Production Kubernetes Installation](./production-kubernetes.md) - Production deployment and infrastructure requirements
- [RBAC Setup Guide](./rbac-setup-guide.md) - Access control configuration
- [Single Sign-On](./single-sign-on.md) - Authentication setup
