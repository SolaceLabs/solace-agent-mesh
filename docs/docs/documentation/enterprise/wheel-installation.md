---
title: Running from Wheel File
sidebar_position: 6
---

# Running Agent Mesh Enterprise from Wheel File

You can run Agent Mesh Enterprise directly from a Python wheel file without using Docker containers. This approach provides more control over your Python environment and allows for easier integration with existing Python-based deployments.

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
solace_agent_mesh-<version>-py3-none-any.whl
```

## Step 2: Install the Wheel File

Install the wheel file using pip or uv:

Using pip:
```bash
pip install solace_agent_mesh-<version>-py3-none-any.whl
```

Using uv:
```bash
uv pip install solace_agent_mesh-<version>-py3-none-any.whl
```

This installation provides the `solace-agent-mesh` CLI tool and the Agent Mesh Enterprise framework.

## Step 3: Prepare Your Configuration

Agent Mesh Enterprise requires configuration files that define your agents, gateways, and system settings.

### Configuration Directory Structure

Create a project directory with the following structure:

```
my-sam-project/
├── configs/
│   ├── shared_config.yaml
│   ├── agents/
│   │   └── orchestrator.yaml
│   └── gateways/
│       └── webui.yaml
└── .env
```

### Environment Variables

Create a `.env` file with your credentials:

```bash
# LLM Configuration
LLM_SERVICE_API_KEY=<your-llm-api-key>
LLM_SERVICE_ENDPOINT=<your-llm-endpoint>
LLM_SERVICE_PLANNING_MODEL_NAME=<your-model-name>
LLM_SERVICE_GENERAL_MODEL_NAME=<your-model-name>

# Namespace
NAMESPACE=<your-namespace>

# Solace Broker (for production)
SOLACE_DEV_MODE=false
SOLACE_BROKER_URL=<your-broker-url>
SOLACE_BROKER_VPN=<your-broker-vpn>
SOLACE_BROKER_USERNAME=<your-username>
SOLACE_BROKER_PASSWORD=<your-password>
```

For development mode with an embedded broker, set:
```bash
SOLACE_DEV_MODE=true
```

### Configuration Files

You need to provide YAML configuration files for your deployment. You can either:

1. Use the community edition's `sam init` command to generate starter configurations
2. Create configurations manually based on your requirements
3. Copy configurations from an existing Agent Mesh project

For configuration file structure and options, see [Configuring Agent Mesh](../installing-and-configuring/configurations.md).

## Step 4: Run Agent Mesh Enterprise

Start Agent Mesh Enterprise using the `solace-agent-mesh run` command:

```bash
solace-agent-mesh run
```

This command:
- Loads environment variables from your `.env` file
- Starts all agents and gateways defined in your `configs/` directory
- Launches the web UI (if configured)

### Running Specific Components

To run only specific agents or gateways, provide the configuration files as arguments:

```bash
solace-agent-mesh run configs/agents/orchestrator.yaml configs/gateways/webui.yaml
```

### Using the Short Alias

You can use the `sam` alias instead of the full command name:

```bash
sam run
```

## Limitations

When running from a wheel file, certain features have limitations compared to the Docker-based deployment.

### No Dynamic Agent Deployment

Dynamic agent deployment through the UI or API is not supported when running from a wheel file. You cannot:

- Deploy new agents at runtime through the web interface
- Upload agent configurations through the API
- Dynamically add or remove agents without restarting

All agents must be defined in configuration files before starting the application.

### Custom Agent Code Requirements

For custom agents with Python code (tools, lifecycle functions), you must use configuration-based agents. This means:

- Custom Python modules must be installed in your Python environment
- Tool functions must be accessible via Python import paths
- You cannot upload arbitrary Python code through the UI

To use custom agent code:

1. Package your custom tools as a Python module
2. Install the module in the same environment as Agent Mesh Enterprise
3. Reference the module in your agent configuration:

```yaml
tools:
  - tool_type: python
    component_module: "my_custom_tools.weather"
    function_name: "get_weather"
```

## Accessing the Web UI

After starting Agent Mesh Enterprise, access the web interface at the configured port (default: `http://localhost:8000`).

If you specified a different port in your gateway configuration, use that port instead.

## Next Steps

After running Agent Mesh Enterprise from the wheel file:

- Configure [Single Sign-On](./single-sign-on.md) for authentication
- Set up [Role-Based Access Control](./rbac-setup-guide.md) for authorization
- Review [deployment options](../deploying/deployment-options.md) for production considerations
