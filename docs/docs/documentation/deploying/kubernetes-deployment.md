---
title: Kubernetes Deployment
sidebar_position: 11
---

# Deploying Agent Mesh to Kubernetes

This guide walks you through deploying Agent Mesh to Kubernetes using Helm charts. Helm automates the deployment process and provides production-ready configurations that handle the complexity of Kubernetes resource management.

## Prerequisites

Before you begin, ensure you have the following:

- A running Kubernetes cluster (1.20 or later)
- `kubectl` configured to access your cluster
- `helm` installed on your system (3.0 or later)
- Container registry credentials (if using private registries)
- Solace broker credentials or Solace Cloud connection details

## Understanding Kubernetes Deployment

Deploying Agent Mesh to Kubernetes involves several steps. First, you add the Helm chart repository to your Helm installation. This makes the Agent Mesh charts available for deployment. Second, you customize the Helm values to match your environment and requirements. Finally, you deploy Agent Mesh to your cluster using the configured values.

The Helm approach handles all the complexity of creating and configuring Kubernetes resources, including deployments, services, persistent volumes, and configuration management. This significantly simplifies the process compared to manually managing individual YAML manifests.

## Using the Helm Quickstart

The Solace Agent Mesh Helm quickstart provides everything you need to deploy Agent Mesh to Kubernetes with sensible defaults and best practices built in.

**Helm Quickstart Repository**: [solace-agent-mesh-helm-quickstart](https://github.com/SolaceProducts/solace-agent-mesh-helm-quickstart)

**Documentation**: [Helm Deployment Guide](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs-site/)

The quickstart includes pre-configured Helm values, deployment examples, and detailed documentation for common deployment scenarios. For comprehensive step-by-step instructions on deploying with Helm, refer to the Helm quickstart documentation.

## Kubernetes Deployment Architecture

Agent Mesh can be deployed as a single monolithic deployment or as multiple specialized deployments that scale independently. The Helm charts support both patterns depending on your scale requirements and operational preferences.

When deploying multiple components as separate deployments, each component runs independently and communicates through the Solace event broker. This approach provides better fault isolation and allows you to scale specific components based on demand. All components must connect to the same Solace broker and use consistent storage configurations to maintain system coherence.

## Configuring for Kubernetes

Several configuration considerations apply specifically to Kubernetes deployments:

**Queue Configuration**: For Kubernetes environments with container restarts, configure Agent Mesh to use durable queues instead of temporary queues. Set the environment variable:

```bash
USE_TEMPORARY_QUEUES=false
```

This ensures that messages persist even when pods restart, and multiple instances can connect to the same queue. For detailed queue configuration guidance, including Queue Template setup in Solace Cloud, see [Choosing Deployment Options](./deployment-options.md#setting-up-queue-templates).

**Secrets Management**: Use Kubernetes Secrets to store sensitive information such as API keys, broker credentials, and authentication tokens. Never embed these values in container images or configuration files.

**Storage**: If running multiple pod replicas, ensure all instances access the same persistent storage with identical configurations. Inconsistent storage across instances can cause data synchronization issues.

**Resource Limits**: Define resource requests and limits for your containers to ensure stable operation and enable effective autoscaling. The Helm quickstart includes recommended resource configurations.

## Next Steps

For comprehensive step-by-step deployment instructions, refer to the [Helm Quickstart Documentation](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs-site/).

For additional information about deployment options and configurations, see [Choosing Deployment Options](./deployment-options.md).
