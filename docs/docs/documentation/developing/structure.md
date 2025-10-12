---
title: Project Structure
sidebar_position: 410
---

# Project Structure

Agent Mesh is built on the A2A (Agent-to-Agent) protocol architecture, powered by [Solace AI Connector](https://github.com/SolaceLabs/solace-ai-connector), and uses the Solace event broker as the communication backbone. The framework is controlled by YAML configuration files that define agents, gateways, and plugins, enabling distributed AI agent communication through event-driven messaging.

A fresh Agent Mesh project follows this structure:

```
my-sam-project/
├── configs/
│   ├── shared_config.yaml           # Shared broker, models, and services config
│   ├── agents/
│   │   └── main_orchestrator.yaml   # Default orchestrator agent
│   └── gateways/
│   │   └── webui.yaml              # Default web UI gateway
│   ├── plugins/
├── src/                            # Custom Python components (optional)
│   └── __init__.py
```

The `configs/` directory uses a logical organization:

- the `agents/` directory contains agent configuration files
- the `gateways/` directory contains gateway configuration files
- the `plugins/` directory contains plugin configuration files (created when plugins are added)

Further subdirectories can be created within `agents/`, `gateways/`, and `plugins/` to organize configurations by functionality or purpose. 


:::info[File Discovery]
The CLI automatically crawls through the `configs` directory to find configuration files. Files that start with `_` (underscore) or `shared_config` are ignored and not processed by the CLI. For example:
- `_example_agent.yaml` is ignored
- `shared_config_for_db_agents.yaml` is ignored (Can still be included in other config files using `!include` directive)
:::

### Shared Configuration

The `shared_config.yaml` file is the foundation of your project configuration. It contains common elements that are reused across all agents and gateways using YAML anchors:

- **Broker Connection**: Solace event broker settings for A2A communication
- **Model Definitions**: LLM model configurations (planning, general, multimodal, etc.)
- **Services**: Artifact service, session service, and data tools configuration

This shared configuration approach eliminates duplication and ensures consistency across your entire project. Each agent and gateway configuration file references these shared elements using YAML anchor syntax (`*reference_name`).

Further values can be added to the shared configuration file as needed, and they are available to all agents and gateways that include it.

## YAML Configuration Files

Each configuration file defines one (recommended) or more applications that can be run independently. The framework supports:

- **Agent Applications**: A2A-enabled agents that use Google ADK runtime and Agent Mesh framework
- **Gateway Applications**: Protocol translators that bridge external interfaces to adopted A2A protocol
- **Plugin Applications**: Specialized components that extend framework capabilities

## Configuration Management

- **Environment Variables**: Configuration values use environment variables for flexibility across environments
- **Shared Configuration**: Common settings are defined once in `shared_config.yaml` and referenced using YAML anchors (`&` and `*`)
- **Automatic Generation**: The `sam add agent`, `sam add gateway`, and `sam plugin add` commands automatically generate appropriate configuration files
- **Standalone Execution**: Each configuration file can be run independently using `sam run <config-file>`

## Python Components

Although most functionality is configured through YAML, custom Python components can be added to the `src/` directory when needed. The framework provides base classes for extending functionality such as custom agent tools, gateway protocol handlers, and service providers.
