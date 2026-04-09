---
title: Kubernetes Production Installation
sidebar_position: 5
---

# Kubernetes Production Installation

Deploy SAM Enterprise on Kubernetes for production with full configuration, high availability, and security.

:::info
For quick evaluation, see the [Kubernetes Quick Start](./quickstart-kubernetes.md). For airgapped environments, see the [Airgap Kubernetes Installation](./airgap-kubernetes.md).
:::

## Production vs Quick Start

Quick Start is designed for **evaluation only** and uses embedded components unsuitable for production:

| Component | Quick Start | Production |
|-----------|-------------|------------|
| **Solace Broker** | Embedded in cluster | External Solace Cloud or on-premises broker |
| **Storage** | Embedded PostgreSQL/SeaweedFS | External S3-compatible storage, managed databases |
| **Authentication** | Disabled | RBAC + SSO (OIDC) |
| **High Availability** | Single instance | Multi-replica, auto-recovery |
| **TLS/Certificates** | None | Full TLS with trusted certificates |
| **Monitoring** | Basic logs | Full observability (Prometheus, Grafana, etc.) |
| **Suitable For** | Testing, evaluation, demos | Production workloads |

## Production Prerequisites

<!-- Content: Full K8s production prereqs -->

## Architecture Overview

<!-- Content: Production K8s architecture diagram -->

## Step 1: Infrastructure Preparation

<!-- Content: Cluster setup, node requirements -->

### Cluster Sizing

<!-- Content: Production cluster sizing recommendations -->

### Network Configuration

<!-- Content: Network policies, ingress, load balancers -->

### Storage Classes

<!-- Content: PVC requirements, storage class configuration -->

## Step 2: External Dependencies

<!-- Content: Setting up external services -->

### Solace Broker Configuration

<!-- Content: External broker setup for production -->

### S3-Compatible Storage

<!-- Content: Production storage configuration -->

### Certificate Management

<!-- Content: TLS cert setup with cert-manager or manual -->

## Step 3: Helm Chart Configuration

<!-- Content: Production values.yaml -->

### Core Configuration

<!-- Content: External Solace broker configuration -->
<!-- Content: External storage configuration (S3, PostgreSQL) -->
<!-- Content: Authentication and authorization configuration -->
<!-- Content: SSO configuration -->
<!-- Content: Optional LLM configuration (can use UI post-install) -->
<!-- Content: Note about embedded vs external components for production -->

### High Availability Configuration

<!-- Content: Multi-replica, PDB, affinity -->

### Security Configuration

<!-- Content: RBAC, pod security, network policies -->

### Resource Limits

<!-- Content: Production resource requests/limits -->

### Monitoring Configuration

<!-- Content: Prometheus, logging integration -->

## Step 4: Pre-Installation Validation

<!-- Content: Validation steps before install -->

## Step 5: Installation

<!-- Content: Production helm install -->

## Step 6: Post-Installation Configuration

<!-- Content: Post-install setup -->

### Configure Authentication

<!-- Content: SSO setup -->

### Configure Authorization

<!-- Content: RBAC setup -->

### Set Up Ingress

<!-- Content: Ingress configuration for production -->

### Configure Monitoring

<!-- Content: Monitoring setup -->

## Step 7: Production Validation

<!-- Content: Comprehensive validation -->

### Health Checks

<!-- Content: Health endpoint validation -->

### Load Testing

<!-- Content: Basic load testing -->

### Disaster Recovery Testing

<!-- Content: Backup/restore validation -->

## Production Operations

<!-- Content: Day 2 operations -->

### Backup & Restore

<!-- Content: Backup procedures -->

### Updates & Upgrades

<!-- Content: Production upgrade procedures -->

### Monitoring & Alerting

<!-- Content: Production monitoring setup -->

### Troubleshooting

<!-- Content: Production troubleshooting -->

## Security Hardening

<!-- Content: Production security best practices -->

## Performance Tuning

<!-- Content: Production performance optimization -->

## Upgrading from Quick Start

<!-- Content: How to upgrade from quick start to production -->
<!-- Content: Progressive helm upgrade steps -->
<!-- Content: Enabling external components one by one -->

## Reference

<!-- Content: Complete production values.yaml template -->
