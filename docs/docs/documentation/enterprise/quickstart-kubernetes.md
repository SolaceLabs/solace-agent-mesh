---
title: Kubernetes Quick Start
sidebar_position: 4
---

# Kubernetes Quick Start

Deploy SAM Enterprise on Kubernetes in ~10 minutes using Helm with **zero required configuration**.

:::warning Evaluation Only
This Quick Start uses **embedded Solace broker, PostgreSQL, and SeaweedFS** with **authentication disabled**. It is designed for evaluation and testing only. **Do not use in production.** See [Production Kubernetes Installation](./production-kubernetes.md) for production-ready deployments.
:::

**What You'll Deploy:**
- SAM Core (orchestrator, platform services, WebUI)
- Embedded Solace PubSub+ broker
- Embedded PostgreSQL database
- Embedded SeaweedFS object storage
- All accessed via `kubectl port-forward` (no Ingress/LoadBalancer)

## Prerequisites

### Kubernetes Cluster Requirements

**Minimum Node Requirements:**

The table below shows resource requirements for embedded broker mode (quickstart). These values account for all SAM components plus embedded PostgreSQL, SeaweedFS, and Solace broker.

| Scenario | CPU Requests | Memory Requests | Recommended Node Size |
|----------|--------------|-----------------|----------------------|
| **Install only** (no upgrade support) | 3500m | 4164Mi | 4 vCPU / 5 GiB allocatable |
| **Install + upgrade safety** | 4600m | 5424Mi | 6 vCPU / 7 GiB allocatable |
| **Recommended with headroom** (kube-system, bursts, limits) | ~5200m | ~6500Mi | **6 vCPU / 8 GiB allocatable** |

:::tip Recommended Node Specification
For the best quickstart experience, use **6 vCPU / 8 GiB RAM** nodes to accommodate:
- Kubernetes system components (kube-system)
- CPU/memory bursts during agent operations
- Safe headroom for Helm upgrades
- Resource limits (not just requests)
:::

**Node Instance Examples:**
- **ARM64 (better price/performance):** AWS `m8g.xlarge`, Azure `Standard_D4ps_v6`, GCP `c4a-standard-4`
- **x86_64:** AWS `m8i.xlarge`, Azure `Standard_D4s_v6`, GCP `n2-standard-4`

**Cluster Requirements:**
- Kubernetes version 1.20 or later

### Storage Requirements

Embedded persistence requires SSD-backed storage for acceptable performance.

**Volume Requirements:**

| Component | Volume Size (Default) |
|-----------|----------------------|
| **PostgreSQL** | 30 GiB |
| **SeaweedFS** | 50 GiB |

**Recommended Storage Classes by Provider:**

| Provider | Storage Class | Notes |
|----------|--------------|-------|
| **AWS EKS** | `gp3` | EBS General Purpose SSD, zoned automatically |
| **Azure AKS** | `Premium_LRS` | Azure Zoned Premium SSD |
| **Google GKE** | `pd-ssd` or `hyperdisk-balanced` | Depends on instance type |

**Storage Class Configuration (Optional):**

Override the default StorageClass or volume size:

```yaml
persistence-layer:
  postgresql:
    persistence:
      storageClassName: "gp3"  # Override default
      size: "50Gi"  # Override default 10Gi
  seaweedfs:
    persistence:
      storageClassName: "gp3"
      size: "100Gi"  # Override default 20Gi
```

**Image Registry Configuration:**

By default, all images (including embedded components) pull from Solace's GCR registry (`gcr.io/gcp-maas-prod`). This requires an image pull secret.

**Default Embedded Component Images:**

| Component | Repository | Tag | Full Image Reference |
|-----------|------------|-----|---------------------|
| **PostgreSQL** | `postgres` | `18.0-trixie` | `gcr.io/gcp-maas-prod/postgres:18.0-trixie` |
| **SeaweedFS** | `chrislusf/seaweedfs` | `3.97` | `gcr.io/gcp-maas-prod/chrislusf/seaweedfs:3.97` |
| **Solace Broker** | `solace-pubsub-enterprise` | `10.25.0.193-multi-arch` | `gcr.io/gcp-maas-prod/solace-pubsub-enterprise:10.25.0.193-multi-arch` |

The chart inherits `global.imageRegistry` for all components automatically. No additional configuration needed unless using a custom registry.

:::warning Important Caveats
- **PVCs persist after uninstall:** When you run `helm uninstall`, PersistentVolumeClaims are NOT automatically deleted (prevents accidental data loss). To clean up: `kubectl delete pvc -l app.kubernetes.io/namespace-id=<your-namespace-id>`
- **Single instance only:** Bundled persistence deploys single-instance databases with no HA or automatic failover
- **No automatic backups:** You are responsible for implementing backup strategies
- **Storage Class Configuration:** Use SSD-backed storage classes (not HDD) to avoid agent timeouts
- **Data loss on uninstall:** Default StorageClasses often have `reclaimPolicy: Delete` - uninstalling Helm will permanently delete your data unless you use `reclaimPolicy: Retain`
:::

### Command-Line Tools

- `kubectl` configured to access your cluster
- Helm 3.0 or later

### Optional for Evaluation

- LLM service API key (OpenAI, Azure OpenAI, etc.) - can be configured post-install via UI

## Step 1: Add Helm Repository

<!-- Content: Helm repo setup -->

## Step 2: Create Namespace

<!-- Content: Namespace creation -->

## Step 3: Install with Zero Configuration

Install SAM with zero required configuration:

```bash
helm install sam solace/solace-agent-mesh --namespace sam
```

No values file needed - the chart defaults are optimized for quickstart evaluation.

**What gets deployed** (chart defaults):

- **Embedded Solace broker** - Pre-configured message broker for evaluation (`global.broker.embedded: true`)
- **Embedded PostgreSQL** - For session and artifact storage (evaluation only, NOT production-grade)
- **Embedded SeaweedFS** - For file storage (evaluation only, NOT production-grade)
- **Service type**: ClusterIP (accessed via port-forward)
- **RBAC authorization**: Disabled (`sam.authorization.enabled: false`)
- **OIDC authentication**: Disabled (no login required)
- **Session secret**: Auto-generated and preserved across upgrades

## Step 4: Wait for Installation to Complete

<!-- Content: How to monitor installation progress -->
<!-- Content: kubectl commands to watch pods -->
<!-- Content: How to verify all pods are ready -->

## Step 5: Access the WebUI

Set up port forwarding to access SAM locally:

```bash
kubectl port-forward -n sam svc/sam-solace-agent-mesh-core 8000:80 8080:8080
```

This forwards both the WebUI (port 80) and Platform API (port 8080).

Open your browser to:

```
http://localhost:8000
```

### First-Time Model Configuration

<!-- Content: How to configure LLM endpoint, API key, and model -->

On first login, the **Model Configuration UI** will prompt you to configure your LLM provider.

**Your Zero-to-Hero Journey** (6 steps):

1. **Access the Console UI**
2. **Configure your LLM model** via the UI prompt (or skip to explore)
3. **Send your first chat message** to the orchestrator
4. **Build a custom agent** via Agent Builder
5. **Deploy your agent**
6. **Chat with your deployed agent**

:::tip Alternative: Pre-configure via values.yaml
Configure LLM in your values file before installation:
```yaml
llmService:
  llmServiceEndpoint: "https://api.openai.com/v1"
  llmServiceApiKey: "your-api-key"
  planningModel: "gpt-4o"
  generalModel: "gpt-4o"
```
See the [RBAC Setup Guide](./rbac-setup-guide.md) for `enterprise_config.yaml` configuration.
:::

## Step 6: Send Your First Message

<!-- Content: Verification via chat -->

## Testing Your Installation

<!-- Content: Quick tests -->

## What's Next?

### Explore SAM Features

Now that your quickstart installation is running, explore SAM capabilities:

- **Agent Builder** - Create custom agents with specialized capabilities
- **Multi-Agent Workflows** - Deploy multiple agents that collaborate
- **Platform Services** - Connect agents to external APIs and services
- **Gateways** - Integrate with Slack, Teams, or other messaging platforms

:::info OpenAPI Connector Feature
If you plan to use the **OpenAPI Connector** feature for REST API integrations, you'll need to configure a separate S3 bucket for OpenAPI specification files. This is optional for evaluation but required for production use of this feature. See [Production Installation - S3 Buckets for OpenAPI Connector Specs](./production-kubernetes.md#s3-buckets-for-openapi-connector-specs) for setup instructions.
:::

Refer to the main [Enterprise documentation](./enterprise.md) for detailed feature guides.

### Moving to Production

When ready for production, upgrade using `helm upgrade` with production overrides:

```bash
helm upgrade sam solace/solace-agent-mesh \
  --namespace sam \
  -f production-overrides.yaml
```

Create a `production-overrides.yaml` file with production settings. The main `values.yaml` contains comprehensive inline documentation for all options.

**Production Readiness Checklist** (items to address before production use):

- ☐ **Disable embedded broker** - Set `global.broker.embedded: false` and configure external Solace broker
- ☐ **Disable embedded persistence** - Set `global.persistence.enabled: false` and configure external PostgreSQL and S3
- ☐ **Configure durable queues** - Set `USE_TEMPORARY_QUEUES: "false"` and configure Queue Template on Solace broker
- ☐ **Enable authorization** - Set `sam.authorization.enabled: true`
- ☐ **Configure OAuth/OIDC provider** - Set `sam.oauthProvider.oidc.*` fields
- ☐ **Enable Ingress or LoadBalancer** - Set `ingress.enabled: true` or `service.type: LoadBalancer`
- ☐ **Configure TLS certificates** - Set `service.tls.*` or `ingress.tls.*`

:::danger Embedded Components Not for Production
The embedded PostgreSQL, SeaweedFS, and Solace broker are designed for evaluation only. They lack high availability, backup/restore capabilities, and proper resource limits for production workloads.
:::

See [Production Kubernetes Installation](./production-kubernetes.md) for complete production deployment guidance.

## Troubleshooting

### Health Checks

Verify SAM components are healthy:

```bash
# After port-forward is running (kubectl port-forward -n sam svc/sam-solace-agent-mesh-core 8000:80 8080:8080)

# Check WebUI health
curl -s http://localhost:8000/health

# Check Platform API health
curl -s http://localhost:8080/api/v1/platform/health
```

Both endpoints should return successful responses when SAM is running correctly.

For detailed health check configuration, see [Health Checks](/docs/documentation/deploying/health-checks).

### Common Issues

**Pods not starting:**
- Check pod status: `kubectl get pods -n sam`
- View pod logs: `kubectl logs -n sam <pod-name>`
- Describe pod for events: `kubectl describe pod -n sam <pod-name>`

**Port-forward connection issues:**
- Verify service exists: `kubectl get service -n sam sam-solace-agent-mesh-core`
- Check that all pods are Running: `kubectl get pods -n sam`
- Ensure no other process is using ports 8000 or 8080 on your local machine

**UI loads but shows errors:**
- Verify both ports are forwarded (8000 for UI, 8080 for Platform API)
- Check browser console (F12) for specific error messages
- Ensure you're accessing `http://localhost:8000` (port must match)
