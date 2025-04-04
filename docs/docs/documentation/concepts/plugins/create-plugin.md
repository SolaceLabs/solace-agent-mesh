---
title: Create Plugins
sidebar_position: 20
---

# Create Plugins

A plugin is a Python package that follows the expected structure and conventions for Solace Agent Mesh and allows for creating [agents](#add-an-agent), [gateways](#add-a-gateway), and [overwrites](#add-an-overwrite) that can be added to a Solace Agent Mesh project.

## Create a Plugin

To get started, [install the SAM CLI](../../getting-started/installation.md) and run the following command:

```bash
solace-agent-mesh plugin create
```

Follow the prompts to create a new plugin. The Solace Agent Mesh (SAM) CLI creates a directory with the provided name and the following structure:

```
plugin-name/
├─ configs/
│  ├─ overwrite/
├─ src/
│  ├─ __init__.py
│  ├─ agents/
│  │  ├─ __init__.py
│  ├─ gateways/
│  │  ├─ __init__.py
├─ interfaces/
├─ solace-agent-mesh-plugin.yaml
├─ .gitignore
├─ pyproject.toml
├─ README.md
```

:::note
The `interfaces` and `configs` directories come with an empty file to prevent Git from ignoring them. These placeholder files can be removed once Git-tracked content is added to the directories. These directories are required for successful build.
:::

- The `src` directory contains the python source code. [more 🔗](../../user-guide/structure.md).
- The `configs` directory contains the configuration files. [more 🔗](../../user-guide/structure.md).
- The `interfaces` directory contains the gateway interfaces. [more 🔗](#add-a-gateway-interface).
- The file `solace-agent-mesh-plugin.yaml` holds the configuration for the plugin. [more 🔗](#plugin-configurations).

Once the plugin is created, you can start adding your custom [agents](#add-an-agent), [gateways](#add-a-gateway), or [overwrites](#add-an-overwrite).

:::info
Adding an agent or gateway follows the same process as adding components to a project for Solace Agent Mesh.
:::

## Plugin Configurations

The `solace-agent-mesh-plugin.yaml` file holds the configuration for the plugin. Here is an example of a plugin configuration file:

```yaml
solace_agent_mesh_plugin:
  name: my-demo-plugin
  includes_gateway_interface: false
```

- **name**: The name of the plugin.
- **includes_gateway_interface**: Set to `true` if providing gateway interface under `./interfaces` directory. Each interface must have an `interface-flows.yaml` and an `interface-default-config.yaml` file. [more 🔗](#add-a-gateway-interface)

## Add Components to the Plugin

### Add an Agent

To create an [agent](../agents.md), run the following SAM CLI command:

```bash
solace-agent-mesh add agent <agent-name>
```

For more information about creating a custom agent, see [Custom Agents](../../user-guide/custom-agents.md).

### Add a Gateway

To create a [gateway](../gateways.md), run the following SAM CLI command:

```bash
solace-agent-mesh add gateway <gateway-name> [--interface <interface-name>]
```

For more information about creating a custom gateway, see [Custom Gateways](../../user-guide/custom-gateways.md).

### Add a Gateway Interface

Instead of creating a [gateway](../gateways.md), you can create a [gateway interface](../gateways.md#gateway-from-interfaces). A gateway interface would allow the plugin users to instantiate a gateway using the interface.

To create a gateway interface, run the following SAM CLI command:

```bash
solace-agent-mesh add <interface-name> --new-interface
```

- `--new-interface` indicates to create an interface. This option can only be used inside a plugin.
- The `interface-name` should be the name of the interface.
- **DO NOT** include the `gateway` keyword in the interface name.
- **DO NOT** include any `--interface` option in the command.

#### Default Gateway Configs for an Interface

When creating a new gateway interface, you can also update the default values for the gateway when the interface is instantiated. 
You can also safely remove the following values if you do not want to provide default values for the interface.

For each interface, a new entry is added to the `solace-agent-mesh-plugin.yaml` file under the `interface_gateway_configs` section:

```yaml
interface_gateway_configs:
  # Your interface name, one entry per interface
  YOUR_INTERFACE_NAME:
    # Whether a human user is expected to interact with the system or it's an autonomous system
    interaction_type: "interactive" # interactive, autonomous
    # The system purpose which will be added to the system prompt
    system_purpose: "The system is an AI Chatbot with agentic capabilities. It will use the agents available to provide information, reasoning and general assistance for the users in this system."
    # The gateway history configuration
    history: 
      # Whether the history is enabled or not
      enabled: true

      # The type of the history, "memory", "file", "redis", "mongodb", "sql"
      type: "file"
      # The configuration for the history type
      type_config:
        # Path is only used for "file" type, check the documentation for other types
        path: /tmp/sam-history

      # How long the history is kept in seconds
      time_to_live: 1000
      # How often the history is checked for expiration in seconds
      expiration_check_interval: 300
      # Maximum number of turns to keep in the history
      max_turns: 40
      # Maximum number of characters to keep in the history
      max_characters: 50000
      # Whether to enforce the alternate message roles (user and assistant)
      enforce_alternate_message_roles: true

      # The long term memory configuration
      long_term_memory:
        # Whether the long term memory is enabled or not
        enabled: true
        
        # The LLM configuration that is used with the long term memory
        llm_config:
          model: ${LLM_SERVICE_PLANNING_MODEL_NAME}
          api_key: ${LLM_SERVICE_API_KEY}
          base_url: ${LLM_SERVICE_ENDPOINT}

        # The store configuration for the long term memory, same as the history type
        store_config:
          # The type of the store, "memory", "file", "redis", "mongodb", "sql"
          type: "file"
          # The configuration for the store type, path is only used for "file" type
          path: /tmp/history
```

:::note
These values only update the initial values of the gateway when the interface is instantiated. The user can still change these values in the project.
:::

**For more information about creating custom gateway interfaces, see [Custom Gateway Interfaces](../../user-guide/custom-gateways.md#creating-gateway-interfaces).**

### Add an Overwrite

Overwrites are YAML configuration files that either:

- Replace the default Solace Agent Mesh YAML configs, or
- Provide standalone configurations for the [solace-ai-connector](../../user-guide/solace-ai-connector.md) that will be added to the project

To add a new overwrite, create a new file under the `configs/overwrite` directory.

For more information, see [Overwrites](../../user-guide/advanced/overwrites.md).

## Build the Plugin

Building the plugin creates a Python wheel package that can be installed using `pip` or other package managers.

To build the plugin, run the following SAM CLI command:

```bash
solace-agent-mesh plugin build
```

The plugin uses the standard `pyproject.toml` file to build the package.

## Share the Plugin

To share the plugin, you can upload the wheel package to a package repository or share the wheel package directly, or any other valid way to share a `pyproject` project.

Alternatively, you can directly point to the GitHub repository of the plugin to perform the build and installation as one step:

```bash
pip install git+https://github.com/<USERNAME>/<REPOSITORY>
```

:::tip
If the `pyproject.toml` of the plugin is not at the root of the repository, you can specify the subdirectory using the `subdirectory` parameter.

```bash
pip install git+https://github.com/<USERNAME>/<REPOSITORY>#subdirectory=<PLUGIN_NAME>
```

:::

You can also use the SAM CLI:

```bash
solace-agent-mesh plugin add PLUGIN_NAME --pip -u git+https://github.com/<USERNAME>/<REPOSITORY>
```
