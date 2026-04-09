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

- A running Kubernetes cluster (version 1.20 or later) within the airgapped network
- `kubectl` configured to access your cluster
- Helm 3.0 or later installed
- A private container registry accessible from your airgapped cluster (Harbor, Artifactory, ECR, ACR, GCR, etc.)
- Registry credentials with push/pull permissions
- Appropriate RBAC permissions to create namespaces, deployments, and services
- StorageClass configured for persistent volumes
- Storage solution for artifacts and session data accessible from your airgapped network
- Solace broker (embedded or external) within the airgapped network
- LLM service endpoint accessible from your airgapped network (or deployed within it)

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

<!-- Content: Minimal config for airgap K8s -->

### Production Airgap Configuration

<!-- Content: Production settings for airgap -->

## Step 8: Installing SAM with Helm

<!-- Content: Helm installation command and options -->

### Installation Command

<!-- Content: helm install command for airgap -->

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

### Test Agent Deployment

<!-- Content: Deploy test agent to validate -->

### Network Isolation Verification

<!-- Content: Confirm no external egress -->

## Airgap-Specific Considerations

<!-- Content: Airgap specific considerations overview -->

### Components Requiring External Connectivity

The following SAM components require internet access or external service connectivity to function. In airgapped environments, you must provide alternative solutions:

#### Bedrock Knowledge Base Tool

<!-- Content: Bedrock tool airgap configuration -->

#### Slack Gateway Adapter

<!-- Content: Slack gateway airgap configuration -->

#### Teams Gateway Adapter

<!-- Content: Teams gateway airgap configuration -->

### LLM Service Configuration

<!-- Content: How to configure LLM endpoints in airgap -->

### Storage Services

<!-- Content: Internal S3-compatible storage setup -->

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
- [Production Kubernetes Installation](./production-kubernetes.md) - Production deployment
- [Kubernetes Deployment Guide](../deploying/kubernetes/kubernetes-deployment-guide.md) - Infrastructure requirements
- [RBAC Setup Guide](./rbac-setup-guide.md) - Access control configuration
- [Single Sign-On](./single-sign-on.md) - Authentication setup
