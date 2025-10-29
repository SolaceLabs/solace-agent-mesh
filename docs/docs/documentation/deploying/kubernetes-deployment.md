---
title: Kubernetes Deployment
sidebar_position: 11
---

# Deploying Agent Mesh on Kubernetes

Kubernetes provides a powerful platform for deploying Agent Mesh at scale with automatic scaling, rolling updates, self-healing capabilities, and robust management features. This guide covers containerized deployment on Kubernetes and references comprehensive Helm-based deployment options for enterprise environments.

## Quick Start with Helm

For streamlined Kubernetes deployments, especially in enterprise environments, the Solace Agent Mesh Helm chart automates many deployment tasks and provides production-ready configurations out of the box.

The Helm quickstart repository provides everything you need to deploy Agent Mesh on Kubernetes, including Helm charts with sensible defaults, example configurations, and best practices for production deployments:

**Helm Quickstart Repository**: [solace-agent-mesh-helm-quickstart](https://github.com/SolaceProducts/solace-agent-mesh-helm-quickstart)

**Helm Documentation**: [Getting Started with Helm Deployment](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs-site/)

These resources include pre-configured Helm values, deployment examples, and documentation for common scenarios. If you're deploying to a Kubernetes cluster, the Helm approach provides the fastest path to a production-ready setup.

## Core Kubernetes Deployment

If you prefer to manage Kubernetes manifests directly, the following sections demonstrate how to containerize and deploy Agent Mesh using standard Kubernetes resources.

### Containerizing Your Application

The first step is to build a Docker image containing your Agent Mesh project:

```Dockerfile
FROM solace/solace-agent-mesh:latest
WORKDIR /app

# Install Python dependencies
COPY ./requirements.txt /app/requirements.txt
RUN python3.11 -m pip install --no-cache-dir -r /app/requirements.txt

# Copy project files
COPY . /app

CMD ["run", "--system-env"]

# To run one specific component, use:
# CMD ["run", "--system-env", "configs/agents/main_orchestrator.yaml"]
```

Optimize your build with a `.dockerignore` file:

```
.env
*.log
dist
.git
.vscode
.DS_Store
```

### Creating a Deployment Manifest

The following Deployment manifest provides a basic configuration for running Agent Mesh on Kubernetes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: solace-agent-mesh
  labels:
    app: solace-agent-mesh
spec:
  replicas: 1  # Adjust based on load
  selector:
    matchLabels:
      app: solace-agent-mesh
  template:
    metadata:
      labels:
        app: solace-agent-mesh
    spec:
      containers:
        - name: solace-agent-mesh
          image: your-registry/solace-agent-mesh:latest

          envFrom:
          - secretRef:
              name: solace-agent-mesh-secrets # Configure secrets in a Kubernetes Secret

          command: ["solace-agent-mesh", "run", "--system-env"]
          args:
            - "configs/main_orchestrator.yaml"
            - "configs/gateway/webui.yaml"
            # Add any other components you want to run here

          ports:
            - containerPort: 8000  # Adjust based on your service ports

          volumeMounts:
            - name: shared-storage
              mountPath: /tmp/solace-agent-mesh
      volumes:
        - name: shared-storage
          emptyDir: {}
```

### Exposing Services

Create a Service to expose your Agent Mesh deployment:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: solace-agent-mesh-service
  labels:
    app: solace-agent-mesh
spec:
  type: ClusterIP  # Use LoadBalancer for external access
  ports:
    - port: 8000
      targetPort: 8000
      protocol: TCP
  selector:
    app: solace-agent-mesh
```

For external access, change the service type to `LoadBalancer` or configure an Ingress resource.

## Microservices Architecture

A microservices approach to deployment offers significant advantages for production systems. By splitting your Agent Mesh components into separate containers, you achieve better fault isolation, independent scaling, and more granular resource management.

This architectural pattern ensures that if one component experiences issues, the rest of your system continues operating normally. When the failed component restarts, it automatically rejoins the mesh through the Solace event broker, maintaining system resilience.

### Implementing Component Separation

**Reuse the same Docker image**: Your base container image remains consistent across all components, simplifying maintenance and ensuring compatibility.

**Customize startup commands**: Each container runs only the components it needs by specifying different configuration files in the startup command.

**Scale independently**: Components with higher resource demands or traffic can be scaled separately, optimizing resource utilization and cost.

Example: Run your main orchestrator in one deployment while scaling your specialized tool agents in separate deployments based on demand.

### Multiple Deployments

```yaml
# Orchestrator Deployment
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: solace-orchestrator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: orchestrator
  template:
    metadata:
      labels:
        app: orchestrator
    spec:
      containers:
        - name: orchestrator
          image: your-registry/solace-agent-mesh:latest
          command: ["solace-agent-mesh", "run", "--system-env"]
          args:
            - "configs/orchestrator.yaml"
          envFrom:
          - secretRef:
              name: solace-agent-mesh-secrets

---
# Tool Agents Deployment (can scale independently)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: solace-tool-agents
spec:
  replicas: 3  # Scale based on demand
  selector:
    matchLabels:
      app: tool-agents
  template:
    metadata:
      labels:
        app: tool-agents
    spec:
      containers:
        - name: tool-agents
          image: your-registry/solace-agent-mesh:latest
          command: ["solace-agent-mesh", "run", "--system-env"]
          args:
            - "configs/agents/tool_agent.yaml"
          envFrom:
          - secretRef:
              name: solace-agent-mesh-secrets
```

## Storage Management

When deploying multiple containers, shared storage becomes critical for maintaining consistency across your Agent Mesh deployment. All container instances must access the same storage location with identical configurations to ensure proper operation.

:::warning Shared Storage Requirement
If using multiple containers, ensure all instances access the same storage with identical configurations. Inconsistent storage configurations can lead to data synchronization issues and unpredictable behavior.
:::

### Using Persistent Volumes

For persistent storage in Kubernetes:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: solace-agent-mesh-storage
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: fast-ssd

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: solace-agent-mesh
spec:
  template:
    spec:
      volumes:
        - name: shared-storage
          persistentVolumeClaim:
            claimName: solace-agent-mesh-storage
      containers:
        - name: solace-agent-mesh
          volumeMounts:
            - name: shared-storage
              mountPath: /tmp/solace-agent-mesh
```

## Queue Configuration

### Temporary vs. Durable Queues

When the `app.broker.temporary_queue` parameter is set to `true` (default), the system uses [temporary endpoints](https://docs.solace.com/Messaging/Guaranteed-Msg/Endpoints.htm#temporary-endpoints) for A2A communication. Temporary queues are automatically created and deleted by the broker, simplifying management but not supporting multiple client connections to the same queue.

In Kubernetes environments with container restarts, temporary queues can cause connection issues. Multiple instances or container restarts may fail if a new pod attempts to connect while the previous instance is still running.

:::tip Kubernetes Configuration
For production Kubernetes deployments, set `temporary_queue` to `false` using the environment variable:

```bash
USE_TEMPORARY_QUEUES=false
```

Durable queues allow multiple agent instances to share the same queue and persist beyond client connections, ensuring messages are not lost during container restarts.
:::

### Queue Template Setup

To prevent messages from piling up in durable queues when an agent is not running, configure a Queue Template in your Solace Cloud Console:

1. Navigate to **Message VPNs** and select your VPN
2. Go to the **Queues** page
3. Open the **Templates** tab
4. Click **+ Queue Template**

Use these settings:

- **Queue Name Filter** = `{NAMESPACE}q/a2a/>`
  (Replace `{NAMESPACE}` with your configured namespace, e.g., `sam/`)
- **Respect TTL** = `true`
  *(Under: Advanced Settings > Message Expiry)*
- **Maximum TTL (sec)** = `18000`
  *(Under: Advanced Settings > Message Expiry)*

:::info
Queue templates are only applied when new queues are created. If you already have durable queues, you can either enable TTL manually in the Solace console or delete existing queues and restart to recreate them with the template applied.
:::

## Security Best Practices

Production Kubernetes deployments require robust security measures to protect sensitive data and ensure system integrity.

### Secrets Management

Never store sensitive information like API keys, passwords, or certificates in `.env` files or container images. Use Kubernetes Secrets or external secret management solutions:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: solace-agent-mesh-secrets
type: Opaque
stringData:
  BROKER_URL: your-broker-url
  BROKER_USERNAME: your-username
  BROKER_PASSWORD: your-password
  API_KEYS: your-api-keys
```

Reference secrets in your deployment:

```yaml
containers:
  - name: solace-agent-mesh
    envFrom:
    - secretRef:
        name: solace-agent-mesh-secrets
```

### TLS Encryption

All communication channels should use TLS encryption to protect data in transit. This includes communication between Agent Mesh components and connections to the Solace event broker.

### Container Security

Maintain security throughout your container lifecycle:

- Regularly update base images with the latest security patches
- Implement security scanning tools (Trivy, Clair) in your CI/CD pipeline
- Run containers with minimal privileges and avoid running as root
- Use resource limits to prevent resource exhaustion attacks

```yaml
containers:
  - name: solace-agent-mesh
    image: your-registry/solace-agent-mesh:latest
    resources:
      requests:
        memory: "512Mi"
        cpu: "250m"
      limits:
        memory: "1Gi"
        cpu: "500m"
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
```

## Platform Compatibility

:::note
If your host system architecture is not `linux/amd64`, add the `--platform linux/amd64` flag when building or running containers to ensure compatibility with pre-built images.
:::

## Configuring Solace Event Broker

The Solace event broker serves as the communication backbone for your agent mesh. For production environments, using a Solace Cloud-managed event broker provides significant advantages over self-managed installations.

Solace Cloud-managed event brokers offer:
- Built-in high availability
- Automatic scaling
- Security updates
- Professional support

For more information, see [Solace Cloud](https://solace.com/products/event-broker/). For detailed configuration instructions, see [Configuring the Event Broker Connection](../installing-and-configuring/configurations.md#configuring-the-event-broker-connection).

## Scaling and Auto-Scaling

Kubernetes Horizontal Pod Autoscaler (HPA) can automatically scale your deployments based on resource usage:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: solace-agent-mesh-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: solace-tool-agents
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Next Steps

For comprehensive Helm-based deployments with enterprise features, see the [Helm Quickstart Documentation](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs-site/).

For additional deployment patterns and enterprise deployment considerations, see [Deployment Options](./deployment-options.md) and [Choosing Deployment Options](./deployment-options.md).
