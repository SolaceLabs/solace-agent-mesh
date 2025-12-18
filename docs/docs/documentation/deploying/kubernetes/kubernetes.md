---
title: Kubernetes
sidebar_position: 11
---

# Deploying Agent Mesh to Kubernetes

You can deploy Agent Mesh to Kubernetes using Helm charts, which handle the complexity of creating and configuring Kubernetes resources such as deployments, services, persistent volumes, and configuration management.

## Prerequisites

To deploy Agent Mesh to Kubernetes, you need:

- A running Kubernetes cluster (version 1.20 or later)
- The `kubectl` command-line tool configured to access your cluster
- Helm installed on your system (version 3.0 or later)
- Container registry credentials (if you use private registries)
- Solace broker credentials or Solace Cloud connection details

## Understanding Kubernetes Deployment

The deployment process involves adding the Helm chart repository, customizing values for your environment, and deploying Agent Mesh to your cluster. The Helm charts simplify this process compared to manually managing individual YAML manifests.

## Using the Helm Quickstart

The Solace Agent Mesh Helm quickstart includes pre-configured Helm values, deployment examples, and detailed documentation for common deployment scenarios.

For the quickstart repository and installation files, see [solace-agent-mesh-helm-quickstart](https://github.com/SolaceProducts/solace-agent-mesh-helm-quickstart).

For step-by-step deployment instructions, see the [Helm Deployment Guide](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs-site/).

## Kubernetes Deployment Architecture

You can deploy Agent Mesh as a single monolithic deployment or as multiple specialized deployments that scale independently. The Helm charts support both patterns based on your scale requirements and operational preferences.

When you deploy multiple components as separate deployments, each component runs independently and communicates through the Solace event broker. This approach provides better fault isolation and allows you to scale specific components based on demand. All components must connect to the same Solace broker and use consistent storage configurations to maintain system coherence.

## Configuring for Kubernetes

Several configuration considerations apply specifically to Kubernetes deployments.

### Queue Configuration

For Kubernetes environments with container restarts, you should configure Agent Mesh to use durable queues instead of temporary queues. Set the environment variable:

```bash
USE_TEMPORARY_QUEUES=false
```

This configuration ensures that messages persist even when pods restart and allows multiple instances to connect to the same queue. For detailed queue configuration guidance, including Queue Template setup in Solace Cloud, see [Choosing Deployment Options](../deployment-options.md#setting-up-queue-templates).

### Secrets Management

You should use Kubernetes Secrets to store sensitive information such as API keys, broker credentials, and authentication tokens. Never embed these values in container images or configuration files.

### Storage

If you run multiple pod replicas, ensure all instances access the same persistent storage with identical configurations. Inconsistent storage across instances can cause data synchronization issues.

### Resource Limits

You should define resource requests and limits for your containers to ensure stable operation and enable effective autoscaling. The Helm quickstart includes recommended resource configurations.
