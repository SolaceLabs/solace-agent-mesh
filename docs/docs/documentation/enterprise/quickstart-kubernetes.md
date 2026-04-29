---
title: Kubernetes Quick Start
sidebar_position: 4
---

# Kubernetes Quick Start

Deploy Solace Agent Mesh Enterprise on Kubernetes in ~10 minutes using Helm with **zero required configuration**.

:::warning Evaluation Only
This Quick Start uses **embedded Solace broker, PostgreSQL, and SeaweedFS** with **authentication disabled**. It is designed for evaluation and testing only. **Do not use in production.** See [Production Kubernetes Installation](./production-kubernetes.md) for production-ready deployments.
:::

**What You'll Deploy:**
- Agent Mesh Core (orchestrator, platform services, WebUI)
- Embedded Solace PubSub+ broker
- Embedded PostgreSQL database
- Embedded SeaweedFS object storage
- All accessed via `kubectl port-forward` (no Ingress/LoadBalancer)

## Prerequisites

### Kubernetes Cluster Requirements

#### Minimum Node Requirements

The following table shows resource requirements for embedded broker mode (quickstart). These values account for all Agent Mesh components plus embedded PostgreSQL, SeaweedFS, and Solace broker.

| Scenario | CPU Requests | Memory Requests | Recommended Node Size |
|----------|--------------|-----------------|----------------------|
| **Install only** (no upgrade support) | 3500m | 4164Mi | 4 vCPU / 5 GiB allocatable |
| **Install + upgrade safety** | 4600m | 5424Mi | 6 vCPU / 7 GiB allocatable |
| **Recommended with headroom** (kube-system, bursts, limits) | ~5200m | ~6500Mi | **6 vCPU / 8 GiB allocatable** |

:::info Below-Minimum Behavior
If your cluster does not meet the CPU or memory requests, the scheduler reports which pod could not be placed and why. The error identifies the specific unmet resource (for example, `0/1 nodes are available: Insufficient cpu`), not a generic installation failure.
:::

:::tip Recommended Node Specification
Use **6 vCPU / 8 GiB RAM** nodes to accommodate:
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

### Image Registry Configuration

By default, all images (including embedded components) pull from Solace's GCR registry (`gcr.io/gcp-maas-prod`). This requires a GCR credentials file provided by Solace.

#### Default Embedded Component Images

| Component | Repository | Tag | Full Image Reference |
|-----------|------------|-----|---------------------|
| **PostgreSQL** | `postgres` | `18.0-trixie` | `gcr.io/gcp-maas-prod/postgres:18.0-trixie` |
| **SeaweedFS** | `chrislusf/seaweedfs` | `3.97-compliant` | `gcr.io/gcp-maas-prod/chrislusf/seaweedfs:3.97-compliant` |
| **Solace Broker** | `solace-pubsub-enterprise` | `10.25.0.193-multi-arch` | `gcr.io/gcp-maas-prod/solace-pubsub-enterprise:10.25.0.193-multi-arch` |

The chart inherits `global.imageRegistry` for all components automatically. No additional configuration needed unless using a custom registry.

#### GCR Credentials File

Solace provides a JSON credentials file for authenticating with the GCR registry. Before using it, verify the file is in the expected dockerconfigjson format:

```json
{
  ".dockerconfigjson": "<base64-encoded-auth>"
}
```

### Command-Line Tools

- `kubectl` configured to access your cluster
- Helm 3.0 or later

## Step 1: Install with Zero Configuration

Download the Helm chart from the [Solace Product Portal](https://products.solace.com/prods/Agent_Mesh/Enterprise/). The GCR credentials file is provided separately by Solace. Once you have both, run:

```bash
helm install sam /path/to/charts/solace-agent-mesh-<version>.tgz \
  --namespace sam \
  --create-namespace \
  --set-file global.imagePullKey=sam-pull-credentials.json
```

The chart defaults are optimized for quickstart evaluation. No values file is needed beyond the credentials. After installation completes, the terminal displays post-install instructions including the port-forward command and the URL to access the Console UI.

**What gets deployed** (chart defaults):

- **Embedded Solace broker** - Pre-configured message broker for evaluation (`global.broker.embedded: true`)
- **Embedded PostgreSQL** - For session and artifact storage (evaluation only, NOT production-grade)
- **Embedded SeaweedFS** - For file storage (evaluation only, NOT production-grade)
- **Service type**: ClusterIP (accessed via port-forward)
- **RBAC authorization**: Disabled (`sam.authorization.enabled: false`)
- **OIDC authentication**: Disabled (no login required)
- **Session secret**: Auto-generated and preserved across upgrades

## Step 2: Wait for Installation to Complete

Wait for all pods to be ready:

```bash
kubectl get pods -n sam -l app.kubernetes.io/instance=sam -w
```

Press `Ctrl-C` after all pods show `Running` status.

## Step 3: Access the WebUI

Port-forward the Console UI:

```bash
kubectl port-forward -n sam svc/sam-solace-agent-mesh-core 8000:80 8080:8080
```

This forwards both the WebUI (port 80) and Platform API (port 8080).

Open your browser to:

```
http://localhost:8000
```

### First-Time Model Configuration

On first login, the **Model Configuration UI** prompts you to configure your LLM provider.

#### Getting Started with Agent Mesh

1. **Access the Console UI**
2. **Configure your LLM models** via the UI prompt. After saving, navigate to **Chat** in the left sidebar to start using Agent Mesh.
3. **Send your first chat message** to the orchestrator
4. **Build a custom agent** via Agent Builder
5. **Deploy your agent**
6. **Chat with your deployed agent**

## What's Next?

### Explore Agent Mesh Features

Now that your quickstart installation is running, explore Agent Mesh capabilities:

- **Agent Builder** - Create custom agents with specialized capabilities
- **Multi-Agent Workflows** - Deploy multiple agents that collaborate
- **Platform Services** - Connect agents to external APIs and services
- **Gateways** - Integrate with Slack, Teams, or other messaging platforms

See the main [Enterprise documentation](./enterprise.md) for detailed feature guides.

### Moving to Production

When ready for production, see the [Production Kubernetes Installation](./production-kubernetes.md) guide for complete deployment guidance, including external broker and datastore configuration, authorization, TLS, and the upgrade path from this quickstart.

:::danger Embedded Components Not for Production
The embedded PostgreSQL, SeaweedFS, and Solace broker are designed for evaluation only. They lack high availability, backup/restore capabilities, and proper resource limits for production workloads.
:::

## Troubleshooting

If something looks wrong after accessing the Console, verify Agent Mesh is healthy:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8080/api/v1/platform/health
```

Both endpoints should return a successful response when Agent Mesh is running correctly.

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

**Agent timeouts:**

Performance of the embedded PostgreSQL and SeaweedFS is heavily dependent on the underlying disk I/O. Standard HDD-backed storage causes agent timeouts. If you experience this, configure a faster StorageClass for the persistence layer:

| Provider | StorageClass |
|----------|-------------|
| **AWS EKS** | `gp3` |
| **Azure AKS** | `managed-csi-premium` |
| **Google GKE** | `pd-ssd` or `hyperdisk-balanced` |

```yaml
persistence-layer:
  postgresql:
    persistence:
      storageClassName: "gp3"
  seaweedfs:
    persistence:
      storageClassName: "gp3"
```
