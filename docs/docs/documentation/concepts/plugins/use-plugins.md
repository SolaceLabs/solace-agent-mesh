---
title: Use Plugins
sidebar_position: 30
---

# Use a Plugin

To use a plugin, you must first install it. You can do this by using your preferred Python package manager, such as `pip`.

After installation, you can then add the plugin to your project for Solace Agent Mesh.

```bash
solace-agent-mesh plugin add <plugin-name>
```

:::info
If you want to install the plugin with the add command as well, you can use one of the `--pip`, `--poetry`, or `--conda` options.

```bash
solace-agent-mesh plugin add <plugin-name> --pip
```

The following Solace Agent Mesh CLI command will first install the plugin using the specified package manager, and then add it to your project.
If the package is not available on the default package manager registry, you can pass a specific local directory or remote URL path using the `-u` (or `--from-url`) option.

```bash
solace-agent-mesh plugin add <plugin-name> --pip -u <path-to-package>
```
:::

The following command updates the `solace-agent-mesh.yaml` file with the plugin configuration:

```yaml
  plugins:
  - name: plugin_name
    load_unspecified_files: false
    includes_gateway_interface: false
    load:
      agents:
        - agent_name
        - agent_name_2
      gateways: 
        - gateway_name
        - gateway_name_2
      overwrites:
        - overwrite_name.yaml
```

:::tip
An empty array in yaml can be indicated with `[]`, For example, `agents: []`.
:::

- **name**: The name of the plugin.
- **includes_gateway_interface**: This value indicates whether the plugin has gateway interfaces or not. This value comes from the plugin. *Do not change this value*.
- **load_unspecified_files**: The expected behavior for unspecified files. By default, only the file mentioned in the `load` will be loaded into the project. But if you want to load all the files from the plugin, you can set this value to `true`.
- **load**: The list of components to be loaded from the plugin.
  - **agents**: The list of agents to be loaded from the plugin. Only the agent name, without `agent` or `.yaml`.
  - **gateways**: The list of gateways to be loaded from the plugin. Only the gateway name, without `gateway` or `.yaml`.
  - **overwrites**: The list of overwrites to be loaded from the plugin. The complete file name from the plugin `configs/overwrite` directory.

:::warning
When using a plugin, always read the instructions provided by the plugin author regarding the configuration and usage of the plugin.
:::

## Use an Agent

To use a pre-built agent from a plugin, update the plugin config in solace-agent-mesh.yaml to include the agent name under the agents list.

For example, if we want to add the `my-tool` agent from `my-plugin`, we'd update the `solace-agent-mesh.yaml` file as follows:

```yaml
  plugins:
  - name: my-plugin
    load_unspecified_files: false
    includes_gateway_interface: false
    load:
      agents:
        - my-tool
      gateways: []
      overwrites: []
```

## Copy from an Agent

When to create an agent from a plugin source:

- Your agent needs complex configurations that don't work well with environment variables.
- You need multiple instances of the same agent with different configurations.
- You want more control over the agent's configuration.

You can create an agent but use the source from the plugin. The Solace Agent Mesh (SAM) CLI copies the agent configurations YAML file to your project.

```bash
solace-agent-mesh add agent <agent-name> --copy-from <plugin-name>[:<src-agent-name>]
```
- `plugin-name` is just the plugin name. This must already exist in the plugin list in the `solace-agent-mesh.yaml` file.
- `src-agent-name` is the name of the agent in the plugin. This is optional and only needed if the agent name in the plugin is different from the agent name you want to use in your project.
- `agent-name` must be exactly the name of the agent you want to copy from the plugin.

After the config file is copied, you can renamed the file or update the configurations as needed.

Follow the instructions provided by the plugin author for the agent configurations.

## Use a Gateway

To use a gateway from a plugin, you'd need to update the plugin config in `solace-agent-mesh.yaml` to include the gateway name under the `gateways` list.

For example, if we want to add the `my-gateway` gateway from `my-plugin`, you can update the `solace-agent-mesh.yaml` file as follows:

```yaml
  plugins:
  - name: my-plugin
    load_unspecified_files: false
    includes_gateway_interface: false
    load:
      agents: []
      gateways: 
        - my-gateway
      overwrites: []
```

## Instantiate a Gateway Interface

If the plugin has gateway interfaces, `includes_gateway_interface` is set to `true`, which automatically adds the interface to the list of available gateway interfaces.

You can run the following SAM CLI command to instantiate the gateway using the interface name:

```bash
solace-agent-mesh add gateway <gateway-name> --interface <plugin-interface-name>
```
