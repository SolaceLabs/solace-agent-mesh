---
title: Deployment
sidebar_position: 10
---

# Deployment

## Development

In a development environment, you can use Solace Agent Mesh CLI to run the project as a single application. By default, environment variables are loaded from your configuration file (typically a `.env` file at the project root):

```bash
sam run
```

## Production

For a production environment, use a containerized and reproducible setup. We recommend Docker or Kubernetes.

If your host system architecture is not `linux/amd64`, add the `--platform linux/amd64` flag when you run the container.

### Docker Deployment

Below is a sample Dockerfile for a Solace Agent Mesh project:

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

And the following `.dockerignore`

```
.env
*.log
dist
.git
.vscode
.DS_Store
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

### Splitting and Scaling

For a robust production setup, consider splitting components into separate containers. This practice enhances scalability and ensures that if one process crashes, the rest of the system remains unaffected. Upon restarting, the failed process rejoins the system.

To adapt the setup:
- Reuse the same Docker image.
- Adjust the startup command to run only the necessary components.
- Scale containers independently based on their resource needs.

### Storage Considerations


:::warning
If using multiple containers, ensure all instances access the same storage with identical configurations.
:::

### Security Best Practices

- **Environment Variables**: Store secrets in a secure vault (for example, AWS Secrets Manager, HashiCorp Vault) rather than in `.env` files.
- **TLS Encryption**: Ensure that communication between components and with the Solace event broker is encrypted using TLS.
- **Container Security**: Regularly update container images and use security scanning tools (for example, Trivy, Clair).

### Solace Event Broker Configuration

For production environments, it's recommended to use a cloud-managed Solace event broker (or event broker service). For more information, see  [Solace Cloud](https://solace.com/products/event-broker/).


