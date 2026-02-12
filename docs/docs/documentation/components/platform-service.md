---
title: Platform Service
sidebar_position: 265
---

# Platform Service

The Platform Service is a backend microservice responsible for management operations in Solace Agent Mesh. It operates independently from other components, allowing it to scale separately.

## What Does It Provide?

The Platform Service provides the backend infrastructure for:

- **Agent Builder** *(Enterprise)* - Create, read, update, and delete AI agents
- **Connector Management** *(Enterprise)* - Manage database connectors that enable agents to query SQL databases
- **Deployment Orchestration** *(Enterprise)* - Deploy agents to runtime environments
- **Deployer Monitoring** *(Enterprise)* - Track health and availability of deployer services

## Running the Platform Service

A sample Platform Service configuration is automatically generated when you run:

```bash
sam init --gui
```

When prompted to enable the WebUI Gateway, select **Yes**. This will generate `configs/services/platform.yaml` with all necessary configuration.

Start the Platform Service using the SAM CLI:

```bash
sam run configs/services/platform.yaml
```

The service runs on **port 8001** by default.

:::note
A Platform Service instance is only required when running the WebUI Gateway in combination with Agent Mesh Enterprise.
:::

## Authentication and Authorization

The Platform Service shares the same authentication and authorization infrastructure as the WebUI Gateway. Both services use the same OAuth2 middleware to validate bearer tokens and the same RBAC configuration to enforce permissions.

To ensure both services use the same authorization configuration, set the `SAM_AUTHORIZATION_CONFIG` environment variable. This variable applies globally to all services in the process and is the recommended way to configure RBAC. If you configure authorization only in the WebUI Gateway's YAML file without setting this environment variable, the Platform Service will not inherit that configuration and will default to denying all access.

For details on how this shared model works and how to troubleshoot it, see [Authentication and Authorization](../enterprise/platform-service-auth.md).

