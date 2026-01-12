# Kubernetes Deployment Guide

**Target Audience:** DevOps Engineers & Kubernetes Administrators

**Purpose:** Infrastructure prerequisites and sizing guidance for deploying Solace Agent Mesh (SAM) Enterprise in customer-managed Kubernetes environments.

## 1. Kubernetes Platform Support

SAM is designed to run on standard, CNCF-compliant Kubernetes clusters. While we adhere to open standards, our Quality Assurance (QA) validation focuses on the managed services of major cloud providers.

### Supported Versions

We support the **three (3) most recent minor versions of upstream Kubernetes**.

* **For Cloud Managed (EKS, AKS, GKE):** We validate against the provider's default release channels.
* **For On-Premise (OpenShift, Rancher, etc.):** Compatibility is determined by the **underlying Kubernetes API version**, not the vendor's product version. Ensure your distribution's K8s version falls within the supported upstream window.

### Distribution Support Matrix

<table>
<thead>
<tr>
<th style={{textAlign: 'left'}}><strong>Category</strong></th>
<th style={{textAlign: 'left'}}><strong>Distributions</strong></th>
<th style={{textAlign: 'left'}}><strong>Support Level</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td style={{verticalAlign: 'top'}}><strong>Validated</strong></td>
<td style={{verticalAlign: 'top'}}>• AWS EKS<br/>• Azure AKS<br/>• Google GKE</td>
<td style={{verticalAlign: 'top'}}><strong>Tier 1 Support.</strong> We explicitly validate SAM releases against these environments.</td>
</tr>
<tr>
<td style={{verticalAlign: 'top'}}><strong>Compatible</strong></td>
<td style={{verticalAlign: 'top'}}>• Red Hat OpenShift<br/>• VMware Tanzu (TKG)<br/>• SUSE Rancher (RKE2)<br/>• Oracle Container Engine (OKE)<br/>• Canonical Charmed Kubernetes<br/>• Upstream K8s (kubeadm)</td>
<td style={{verticalAlign: 'top'}}><strong>Tier 2 Support.</strong> SAM is compatible with standard Kubernetes APIs. For distributions with proprietary security constraints (e.g., OpenShift SCCs, Tanzu PSPs), Solace support is limited to confirming API compatibility only. Solace does not provide setup, configuration, or troubleshooting assistance for customer-specific security policies or proprietary features—these remain the customer's responsibility.</td>
</tr>
</tbody>
</table>

### Constraints & Limitations

To prevent deployment failures, ensure your cluster meets the following constraints:

1. **Node Architecture:** SAM requires **Standard Worker Nodes** backed by VMs or Bare Metal.

    * **Not Supported:** Serverless or Virtual Nodes (e.g., **AWS Fargate, GKE Autopilot**, Azure Virtual Nodes) are not supported due to local storage and networking limitations.

2. **Security Context:**

    * SAM containers run as **non-root users** (UID 999) by default.
    * SAM **does NOT** require `privileged: true` capabilities or root access.
    * _OpenShift Note:_ You may need to add the service account to the `nonroot` SCC if your cluster enforces `restricted-v2` by default.

3. **Monitoring:**

    * SAM **does NOT** deploy DaemonSets for monitoring.
    * Observability/Monitoring is the customer's responsibility.


## 2. Compute Resource Guidance

SAM workloads utilize a microservices architecture. Resource requirements scale based on the number of concurrent Agents you intend to run.

### Processor Architecture Support

SAM container images are built for multi-architecture support. You may provision nodes using either architecture based on your organization's standards:

* **ARM64 (Recommended):** Offers the best price/performance ratio (e.g., AWS Graviton, Azure Cobalt, Google Axion).
* **x86_64 (Intel/AMD):** Fully supported for standard deployments.

### Recommended Node Sizing

For Production environments, we recommend using latest-generation **General Purpose** worker nodes to balance CPU and Memory (with a 1:4 ratio).

* **Recommended Specification:** **4 vCPU / 16 GB RAM**

    * _ARM Examples:_ AWS `m8g.xlarge`, Azure `Standard_D4ps_v6`, GCP `c4a-standard-4`
    * _x86 Examples:_ AWS `m8i.xlarge`, Azure `Standard_D4s_v6`, GCP `n2-standard-4`

* **Minimum Specification:** **2 vCPU / 8 GB RAM** (Note: smaller nodes will limit agent density).

    * _ARM Examples:_ AWS `m8g.large`, Azure `Standard_D2ps_v6`, GCP `c4a-standard-2`
    * _x86 Examples:_ AWS `m8i.large`, Azure `Standard_D2s_v6`, GCP `n2-standard-2`


**Note**: For AWS, Azure, and GCP, should any of these instance types be unavailable in your region of choice, we recommend choosing the next closest equivalent (e.g. `m7g.large` instead of `m8g.large`).

### Component Resource Specifications

To assist with Quota planning and, if in use, Cluster Autoscaler configuration, the following table details the default Resource Requests and Limits for the mandatory core components.

> **Note:** These values represent the application container only. If your environment injects sidecars (e.g., Istio, Dapr, Splunk), ensure you calculate additional overhead to prevent scheduling failures.

<table>
<thead>
<tr>
<th style={{textAlign: 'left'}}><strong>Component</strong></th>
<th style={{textAlign: 'left'}}><strong>Description</strong></th>
<th style={{textAlign: 'left'}}><strong>CPU Request</strong></th>
<th style={{textAlign: 'left'}}><strong>CPU Limit</strong></th>
<th style={{textAlign: 'left'}}><strong>RAM Request</strong></th>
<th style={{textAlign: 'left'}}><strong>RAM Limit</strong></th>
<th style={{textAlign: 'left'}}><strong>QoS Class</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td style={{verticalAlign: 'top'}}><strong>Agent Mesh</strong></td>
<td style={{verticalAlign: 'top'}}>Includes Core services, Orchestrator Agent, and Web UI Gateway.</td>
<td style={{verticalAlign: 'top'}}>175m</td>
<td style={{verticalAlign: 'top'}}>200m</td>
<td style={{verticalAlign: 'top'}}>625 MiB</td>
<td style={{verticalAlign: 'top'}}>1 GiB</td>
<td style={{verticalAlign: 'top'}}>Burstable</td>
</tr>
<tr>
<td style={{verticalAlign: 'top'}}><strong>Deployer</strong></td>
<td style={{verticalAlign: 'top'}}>Responsible for dynamically deploying SAM-managed Agents, Gateways, and mesh components.</td>
<td style={{verticalAlign: 'top'}}>100m</td>
<td style={{verticalAlign: 'top'}}>100m</td>
<td style={{verticalAlign: 'top'}}>100 MiB</td>
<td style={{verticalAlign: 'top'}}>100 MiB</td>
<td style={{verticalAlign: 'top'}}>Guaranteed</td>
</tr>
<tr>
<td style={{verticalAlign: 'top'}}><strong>Agent</strong></td>
<td style={{verticalAlign: 'top'}}>The runtime for a single Agent instance (scales horizontally).</td>
<td style={{verticalAlign: 'top'}}>175m</td>
<td style={{verticalAlign: 'top'}}>200m</td>
<td style={{verticalAlign: 'top'}}>625 MiB</td>
<td style={{verticalAlign: 'top'}}>768 MiB</td>
<td style={{verticalAlign: 'top'}}>Burstable</td>
</tr>
</tbody>
</table>

### Custom Mesh Components (Customer-Managed)

For **Custom Agents** or external components that are not managed/provisioned by the Deployer:

* **Responsibility:** The customer is responsible for defining the Deployment manifests and resource requirements.
* **Sizing:** We recommend starting with the `SAM Agent` baseline (175m / 625 MiB) and adjusting based on the specific logic or model inference requirements of your custom code.

### Capacity Planning (Per Agent)

When sizing your cluster, budget the following reservations for _each_ concurrent Solace Agent you plan to deploy:

* **Memory Request:** **625 MiB**
* **Memory Limit:** **768 MiB**
* **CPU Request:** **175m** (0.175 vCPU)
* **CPU Limit:** **200m** (0.2 vCPU)

## 3. Persistence Layer Strategy

SAM requires a relational database (PostgreSQL) and an object store (S3-compatible) to function.

### A. Production Deployments (Mandatory)

For production environments, you **must** provide your own managed external persistence services. Solace does not support running stateful databases inside the SAM cluster for production traffic.

* **Database:** PostgreSQL 17+ (e.g., AWS RDS, Azure Database for PostgreSQL, Cloud SQL).
* **Object Store:** S3-Compatible API (e.g., AWS S3, Azure Blob, Google Cloud Storage).
* **Configuration:** Refer to the [_Session Storage_](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/installing-and-configuring/session-storage) _and_ [_Artifact Storage_](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/installing-and-configuring/artifact-storage) to configure connection strings and secrets for your installation.
* **Authentication:** Standard Username/Password authentication via Kubernetes Secret is supported.

### B. Dev / POC Deployments (Optional Starter Layer)

For convenience, the [SAM Helm Quickstart](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/deploying/kubernetes-deployment#using-the-helm-quickstart) chart includes an optional "Starter Persistence Layer" (Containerized PostgreSQL + SeaweedFS).

* **Use Case:** Strictly for **Evaluation, Development, and Proof of Concept (POC)**.
* **Support Policy:** **Unsupported.** Solace provides these components "as-is" for quick startup. We do not provide patches, backups, or data recovery support for embedded persistence pods.
* **Data Persistence:** If the pods restart, data is preserved only if a valid StorageClass is configured.

**Starter Layer Resource Requirements:**

<table>
<thead>
<tr>
<th style={{textAlign: 'left'}}><strong>Component</strong></th>
<th style={{textAlign: 'left'}}><strong>Description</strong></th>
<th style={{textAlign: 'left'}}><strong>CPU Request</strong></th>
<th style={{textAlign: 'left'}}><strong>CPU Limit</strong></th>
<th style={{textAlign: 'left'}}><strong>RAM Request</strong></th>
<th style={{textAlign: 'left'}}><strong>RAM Limit</strong></th>
<th style={{textAlign: 'left'}}><strong>Recommended Volume Size</strong></th>
<th style={{textAlign: 'left'}}><strong>QoS Class</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td style={{verticalAlign: 'top'}}><strong>Postgres</strong> (Starter)</td>
<td style={{verticalAlign: 'top'}}>Embedded database for configuration state (Dev/POC only).</td>
<td style={{verticalAlign: 'top'}}>175m</td>
<td style={{verticalAlign: 'top'}}>175m</td>
<td style={{verticalAlign: 'top'}}>625 MiB</td>
<td style={{verticalAlign: 'top'}}>625 MiB</td>
<td style={{verticalAlign: 'top'}}>30 GiB</td>
<td style={{verticalAlign: 'top'}}>Guaranteed</td>
</tr>
<tr>
<td style={{verticalAlign: 'top'}}><strong>SeaweedFS</strong> (Starter)</td>
<td style={{verticalAlign: 'top'}}>Embedded S3-compatible object storage for artifacts (Dev/POC only).</td>
<td style={{verticalAlign: 'top'}}>175m</td>
<td style={{verticalAlign: 'top'}}>175m</td>
<td style={{verticalAlign: 'top'}}>625 MiB</td>
<td style={{verticalAlign: 'top'}}>625 MiB</td>
<td style={{verticalAlign: 'top'}}>50 GiB</td>
<td style={{verticalAlign: 'top'}}>Guaranteed</td>
</tr>
</tbody>
</table>

**Storage Class Recommendations (Starter Layer Only):**

If you choose to use the **Starter Persistence Layer** for development, performance is heavily dependent on the underlying disk I/O. Using slow standard disks (HDD) will cause Agent timeouts.

> **Warning:**
>
> * Default StorageClasses often have `reclaimPolicy: Delete`. If you're using SAM Helm Quickstart, uninstalling the Helm release will permanently delete your Dev data. If data persistence is required across re-installs, please configure a StorageClass with `reclaimPolicy: Retain`.
> * For managed Kubernetes clusters (e.g., EKS, AKS, GKE), use a `StorageClass` with `volumeBindingMode: WaitForFirstConsumer` and ensure the underlying disk is single-zone. This avoids initial scheduling and later re-scheduling failures due to cross-zone volumes.
>

We recommend using **SSD-backed Storage Classes**:

<table>
<thead>
<tr>
<th style={{textAlign: 'left'}}><strong>Provider</strong></th>
<th style={{textAlign: 'left'}}><strong>Recommended StorageClass</strong></th>
<th style={{textAlign: 'left'}}><strong>Underlying Tech (Disk Type)</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td style={{verticalAlign: 'top'}}><strong>AWS EKS</strong></td>
<td style={{verticalAlign: 'top'}}>Any storage class using the <code>gp3</code> disk type.</td>
<td style={{verticalAlign: 'top'}}>EBS General Purpose SSD. EBS volumes are implicitly zoned.</td>
</tr>
<tr>
<td style={{verticalAlign: 'top'}}><strong>Azure AKS</strong></td>
<td style={{verticalAlign: 'top'}}>Any storage class that uses zoned SSDs.</td>
<td style={{verticalAlign: 'top'}}>Azure Zoned Premium SSD (<code>Premium_LRS</code>).</td>
</tr>
<tr>
<td style={{verticalAlign: 'top'}}><strong>Google GKE</strong></td>
<td style={{verticalAlign: 'top'}}>Variable, depends on chosen instance type.</td>
<td style={{verticalAlign: 'top'}}>Variable, support depends on instance type. Search for <code>Supported disk types</code> in https://docs.cloud.google.com/compute/docs/general-purpose-machines. Examples: hyperdisk-balanced pd-ssd</td>
</tr>
<tr>
<td style={{verticalAlign: 'top'}}><strong>Generic</strong></td>
<td style={{verticalAlign: 'top'}}>Any CSI driver supporting SSD</td>
<td style={{verticalAlign: 'top'}}>NVMe / SSD</td>
</tr>
</tbody>
</table>

**Node Pool Topology Recommendations (Starter Layer Only):**

In AKS, EKS, and GKE, if nodes are available in more than one availability zone for a region, one node pool (e.g. node group, or provider-specific equivalent) must be provisioned for each availability zone. The simplest approach with the starter layer is to provision node instances for SAM deployments in **one availability zone only** to avoid this complexity. Official recommendations from cloud providers are as follows:

* AKS: [https://learn.microsoft.com/en-us/azure/aks/cluster-autoscaler?tabs=azure-cli#re-enable-the-cluster-autoscaler-on-a-node-pool](https://learn.microsoft.com/en-us/azure/aks/cluster-autoscaler?tabs=azure-cli#re-enable-the-cluster-autoscaler-on-a-node-pool)
* EKS: [https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html#managed-node-group-concepts](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html#managed-node-group-concepts)
* GKE: We recommend following the above pattern for simplicity and consistency.

We recommend a similar approach for other cloud providers as applicable. This does not apply when using external persistence solutions (e.g. managed Postgres and S3-compatible storage) as all SAM workloads will be stateless.

## 5. Network Connectivity & Prerequisites

SAM operates as a connected application mesh. To ensure proper functionality, your network environment must allow specific inbound and outbound traffic flows.

### A. Inbound Traffic (Web Gateway)

SAM provisions a **Web Gateway** service to handle incoming API traffic and UI access.

* **Ingress Controller:** An Ingress Controller (e.g., NGINX, ALB) must be present in the cluster to route traffic to this Gateway.
* **TLS Termination:** Production deployments should terminate TLS at the Ingress layer. You must supply your TLS Certificate and Key as a standard Kubernetes Secret and reference it in your Helm `values.yaml`.

### B. Outbound Platform Access

The core SAM platform requires outbound connectivity to specific infrastructure services.

* **Container Registry:**

    * **Direct Access:** Outbound access to `gcr.io/gcp-maas-prod`. Requires a Pull Secret obtained from the Solace Cloud Console.
    * **Private Mirror (Air-Gapped):** If using a private registry (e.g., Artifactory), you must mirror images from `gcr.io` and configure `global.imageRegistry`.

* **Solace Event Broker Access:**

    * **Solace Cloud Event Broker Service:** Allow connectivity to `*.messaging.solace.cloud` or your specific Solace Cloud region CNAMEs.
    * **Self-Hosted Brokers:** Allow traffic to the SMF (55555) or SMF+TLS (55443) ports of your on-premise appliances/software brokers.

* **LLM Providers:**

    * The core platform (and Agents) requires access to your configured Model Providers (e.g., `api.openai.com`, `your-azure-endpoint.openai.azure.com`).

* **Identity Provider (IdP) Access:**

    * The SAM Control Plane requires outbound network connectivity to your organization's IdP (e.g., Microsoft Entra ID, AWS Cognito, or any SAML/OIDC-compliant provider) for authentication and authorization.


### C. Application & Mesh Component Connectivity

Beyond the core platform, the specific **Agents** and **Gateways** you deploy will require their own network paths.

* **Agent Integrations:** If you deploy Agents designed to interact with external enterprise systems (e.g., Salesforce, Jira, Snowflake, Oracle DB), you must ensure the Kubernetes worker nodes have network reachability to these target services.
* **Gateway Exposure:** If you deploy additional Mesh Gateways for specific domains or protocols, ensure your Ingress configuration allows for the necessary inbound routes, ports, and protocols.

### D. Corporate Proxy Configuration

For environments with strict egress filtering, SAM supports routing outbound traffic through a corporate **HTTP/HTTPS Proxy**.

### E. Tooling & Guides

* **Installation Tooling:**

    * **Helm v3** is the recommended installer.
    * **Alternative:** You may use `helm template` to render manifests for direct `kubectl` application or integration with GitOps tools (ArgoCD, Flux).

* **Documentation:** Please refer to the [SAM Kubernetes Deployment Guide](kubernetes.md#using-the-helm-quickstart) for detailed configuration steps regarding the Helm chart, secrets, proxies, and network rules.