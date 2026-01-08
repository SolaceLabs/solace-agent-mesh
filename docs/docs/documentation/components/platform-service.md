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

