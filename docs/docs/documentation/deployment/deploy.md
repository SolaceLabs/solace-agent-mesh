---
title: Deployment
sidebar_position: 10
---

# Deployment

## Development

In a development environment, you can use the Solace Agent Mesh CLI to run the project as a single application. By default, environment variables are loaded from your configuration file (typically a `.env` file at the project root):

```bash
sam run -b
```

:::note
The `-b` flag builds the project before running it.
:::

For file storage in development, you can use the [Volume File Manager](../user-guide/advanced/services/file-service.md#file-managers) provided by the [File service](../user-guide/advanced/services/file-service.md).

## Production

For a production environment, using a containerized and reproducible setup. We recommend Docker or Kubernetes.

### Docker Deployment

Below is a sample Dockerfile for a Solace Agent Mesh project:

```Dockerfile
FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends plantuml graphviz git && \
    apt-get purge -y --auto-remove && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY ./pyproject.toml /app/pyproject.toml
RUN python3.10 -m pip install --no-cache-dir .

# Copy project files
COPY . /app

# Build Solace Agent Mesh
RUN solace-agent-mesh build

# Create a non-root user
RUN groupadd -r samapp && useradd -r -g samapp samapp
RUN chown -R samapp:samapp /app /tmp

# Switch to non-root user
USER samapp

# Default entry point
ENTRYPOINT ["solace-agent-mesh", "run", "--use-system-env"]

# Default command for running multiple configurations
CMD [
     "build/configs/orchestrator.yaml",
     "build/configs/service_llm.yaml",
     "build/configs/service_embedding.yaml",
     "build/configs/agent_global.yaml"
]
```

### Kubernetes Deployment

For scalable and highly available deployments, Kubernetes is recommended. Below is a minimal `Deployment` configuration:

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

          command: ["solace-agent-mesh", "run", "--use-system-env"]
          args:
            - "build/configs/orchestrator.yaml"
            - "build/configs/service_llm.yaml"
            - "build/configs/service_embedding.yaml"
            - "build/configs/agent_global.yaml"
            # Add any other components you want to run here

          volumeMounts:
            - name: shared-storage
              mountPath: /tmp/solace-agent-mesh
      volumes:
        - name: shared-storage
          emptyDir: {}
```

### Splitting and Scaling

For a robust production setup, consider splitting components into separate containers. This practice enhances scalability and ensures that if one process crashes, the rest of the system remains unaffected. Upon restarting, the failed process rejoins the system.

To adapt the setup:
- Reuse the same Docker image.
- Adjust the startup command to run only the necessary components.
- Scale containers independently based on their resource needs.

### Storage Considerations

For production storage, use a shared volume or configure an AWS S3 bucket for the [File service](../user-guide/advanced/services/file-service.md).

:::warning
If using multiple containers, ensure all instances access the same storage with identical configurations.
:::

### Security Best Practices

- **Environment Variables**: Store secrets in a secure vault (for example, AWS Secrets Manager, HashiCorp Vault) rather than in `.env` files.
- **TLS Encryption**: Ensure that communication between components and with the PubSub+ event broker is encrypted using TLS.
- **Container Security**: Regularly update container images and use security scanning tools (for example, Trivy, Clair).

### Solace Event Broker Configuration

For production environments, it's recommended to use a cloud-managed PubSub+ event broker (or event broker service). For more information, see  [Solace PubSub+ Cloud](https://solace.com/products/event-broker/).

## Event Mesh Integration

If you already have an [event mesh](https://solace.com/what-is-an-event-mesh/) in place, you can integrate Solace Agent Mesh into it. This allows you to leverage existing infrastructure while introducing intelligence and automation through Solace Agent Mesh.

#### Benefits of Integrating with an Event Mesh

- **Seamless Communication**: Solace Agent Mesh can subscribe to and publish events across the entire event mesh.
- **Event-Driven Automation**: Intelligent event processing based on patterns and AI-driven insights.
- **Scalability**: Solace Agent Mesh can dynamically participate in large-scale event-driven systems.

#### Integration Steps

To learn more about how to integrate Solace Agent Mesh with an existing Event Mesh, see [Event Mesh Integration](../tutorials/event-mesh-gateway.md).
