---
title: Choosing Deployment Options
sidebar_position: 10
---

# Choosing Deployment Options

Solace Agent Mesh offers flexible deployment options designed to meet different operational requirements. Understanding these options helps you choose the right approach for your specific environment and scale needs.

## Development Environment

During development, simplicity and rapid iteration are key priorities. The Solace Agent Mesh CLI provides a streamlined way to run your entire project as a single application, making it easy to test changes and debug issues locally.

The development setup automatically loads environment variables from your configuration file (typically a `.env` file at the project root), eliminating the need for complex environment management:

```bash
sam run
```

This command starts all configured components together, providing immediate feedback and allowing you to see how different agents interact within your mesh.

## Production Environment

Production deployments require different considerations than development environments. You need reproducible builds, scalable infrastructure, and robust monitoring capabilities. Containerization addresses these requirements by providing consistent runtime environments and enabling modern orchestration platforms.

We recommend using Docker for single-node deployments or Kubernetes for multi-node, scalable deployments. These technologies ensure your application runs consistently across different environments and can scale to meet demand.

:::note Platform Compatibility
If your host system architecture is not `linux/amd64`, add the `--platform linux/amd64` flag when you run the container to ensure compatibility with the pre-built images.
:::

### Deploying with Docker

Docker provides an excellent foundation for production deployments because it packages your application with all its dependencies into a portable container. This approach ensures consistent behavior across different environments and simplifies deployment processes.

The following Dockerfile demonstrates how to containerize a Solace Agent Mesh project:

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

To optimize build performance and security, create a `.dockerignore` file that excludes unnecessary files from the Docker build context:

```
.env
*.log
dist
.git
.vscode
.DS_Store
```


### Deploying with Kubernetes

Kubernetes excels at managing containerized applications at scale, providing features like automatic scaling, rolling updates, and self-healing capabilities. When your Solace Agent Mesh deployment needs to handle varying loads or requires high availability, Kubernetes becomes the preferred orchestration platform.

The following example shows a basic Kubernetes Deployment configuration that you can customize based on your specific requirements:

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

### Separating and Scaling Components

A microservices approach to deployment offers significant advantages for production systems. By splitting your Solace Agent Mesh components into separate containers, you achieve better fault isolation, independent scaling, and more granular resource management.

This architectural pattern ensures that if one component experiences issues, the rest of your system continues operating normally. When the failed component restarts, it automatically rejoins the mesh through the Solace event broker, maintaining system resilience.

To implement component separation:

**Reuse the same Docker image**: Your base container image remains consistent across all components, simplifying maintenance and ensuring compatibility.

**Customize startup commands**: Each container runs only the components it needs by specifying different configuration files in the startup command.

**Scale independently**: Components with higher resource demands or traffic can be scaled separately, optimizing resource utilization and cost.

For example, you might run your main orchestrator in one deployment while scaling your specialized tool agents in separate deployments based on demand.

### Managing Storage Requirements

When deploying multiple containers, shared storage becomes critical for maintaining consistency across your Solace Agent Mesh deployment. All container instances must access the same storage location with identical configurations to ensure proper operation.

:::warning Shared Storage Requirement
If using multiple containers, ensure all instances access the same storage with identical configurations. Inconsistent storage configurations can lead to data synchronization issues and unpredictable behavior.
:::

Consider using persistent volumes in Kubernetes or shared file systems in Docker deployments to meet this requirement.

### Implementing Security Best Practices

Production deployments require robust security measures to protect sensitive data and ensure system integrity. Implementing these practices helps safeguard your Solace Agent Mesh deployment against common security threats.

**Environment Variables and Secrets Management**: Never store sensitive information like API keys, passwords, or certificates in `.env` files or container images. Instead, use dedicated secret management solutions such as AWS Secrets Manager, HashiCorp Vault, or Kubernetes Secrets. These tools provide encryption at rest, access controls, and audit trails for sensitive data.

**TLS Encryption**: All communication channels should use TLS encryption to protect data in transit. This includes communication between Solace Agent Mesh components and connections to the Solace event broker. TLS prevents eavesdropping and ensures data integrity during transmission.

**Container Security**: Maintain security throughout your container lifecycle by regularly updating base images to include the latest security patches. Implement security scanning tools like Trivy or Clair in your CI/CD pipeline to identify vulnerabilities before deployment. Additionally, run containers with minimal privileges and avoid running processes as root when possible.

### Configuring Solace Event Broker

The Solace event broker serves as the communication backbone for your agent mesh, handling all message routing and delivery between components. For production environments, using a cloud-managed Solace event broker provides significant advantages over self-managed installations.

Cloud-managed event brokers offer built-in high availability, automatic scaling, security updates, and professional support. These managed services eliminate the operational overhead of maintaining event broker infrastructure while providing enterprise-grade reliability and performance.

For more information about cloud-managed options, see [Solace Cloud](https://solace.com/products/event-broker/). For detailed configuration instructions, see [Broker Connection Configuration](../installing-and-configuring/configurations.md#broker-connection-configuration).


