---
title: Running from Wheel File
sidebar_position: 6
---

# Running Agent Mesh Enterprise from Wheel File

You can run Agent Mesh Enterprise directly from a Python wheel file without using Docker containers. This approach gives you direct control over your Python environment and integrates with existing Python-based deployments.

## Prerequisites

To run Agent Mesh Enterprise from a wheel file, you need:

- Python 3.10.16 or later
- pip or uv package manager
- Access to the [Solace Product Portal](https://products.solace.com/prods/Agent_Mesh/Enterprise/)
- An LLM service API key and endpoint
- For production deployments, Solace broker credentials

## Step 1: Download the Wheel File

Download the Agent Mesh Enterprise wheel file from the [Solace Product Portal](https://products.solace.com/prods/Agent_Mesh/Enterprise/).

The wheel file follows the naming pattern:
```
solace_agent_mesh_enterprise-<version>-py3-none-any.whl
```

## Step 2: Install the Wheel File

You can install the wheel file with either pip or uv.

If you use pip, run:
```bash
pip install solace_agent_mesh_enterprise-<version>-py3-none-any.whl
```

If you use uv, run:
```bash
uv pip install solace_agent_mesh_enterprise-<version>-py3-none-any.whl
```

This installation provides the `solace-agent-mesh` CLI tool and the Agent Mesh Enterprise framework.

## Step 3: Prepare Your Configuration

Agent Mesh Enterprise requires configuration files that define your agents, gateways, and system settings. The `solace-agent-mesh init` command creates the project directory structure, environment variables, and configuration files you need.

Follow the project setup steps in the [Creating and Running an Agent Mesh Project](../installing-and-configuring/run-project.md#create-your-project) guide to initialize your configuration. You can use the web-based interface or command-line options to configure your project settings.

After initialization, your project directory contains the necessary `configs/` directory with agent and gateway configurations, plus a `.env` file with your credentials.

## Step 4: Run Agent Mesh Enterprise

Start Agent Mesh Enterprise using the `solace-agent-mesh run` command:

```bash
solace-agent-mesh run
```

This command loads environment variables from your `.env` file, starts all agents and gateways defined in your `configs/` directory, and launches the web UI if you configured one.

### Running Specific Components

To run only specific agents or gateways, provide the configuration files as arguments:

```bash
solace-agent-mesh run configs/agents/orchestrator.yaml configs/gateways/webui.yaml
```

### Using the Short Alias

The `sam` alias provides a shorter alternative to the full command name:

```bash
sam run
```

## Limitations

When running from a wheel file, certain features have limitations compared to the Docker-based deployment.

### No Dynamic Agent Deployment

Dynamic agent deployment through the UI or API is not supported when running from a wheel file. You cannot deploy new agents at runtime through the web interface, upload agent configurations through the API, or dynamically add or remove agents without restarting. All agents must be defined in configuration files before you start the application.

### Custom Agent Code

To create custom agents with Python tools and lifecycle functions, follow the standard agent creation process. For detailed instructions on creating agents with custom code, see [Creating Agents](../developing/create-agents.md).

## Accessing the Web UI

After starting Agent Mesh Enterprise, access the web interface at the configured port (default: `http://localhost:8000`).

If you specified a different port in your gateway configuration, use that port instead.

## Next Steps

After running Agent Mesh Enterprise from the wheel file, you can configure authentication and authorization for your deployment. For information about setting up authentication, see [Single Sign-On](./single-sign-on.md). For information about configuring authorization, see [Role-Based Access Control](./rbac-setup-guide.md). For production deployment considerations, see [deployment options](../deploying/deployment-options.md).
