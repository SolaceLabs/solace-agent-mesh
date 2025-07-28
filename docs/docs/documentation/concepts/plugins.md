---
title: Plugins
sidebar_position: 60
---

## Plugins

Plugins provide a mechanism to extend the functionality of Solace Agent Mesh in a modular, shareable, and reusable way. The current plugin ecosystem includes agents, gateways, and specialized integrations.

:::tip[In one sentence]
Plugins are modular Python packages that extend SAM's capabilities through agents, gateways, and specialized integrations.
:::

Plugins are packaged as Python modules that can be installed using various package managers (`pip`, `uv`, `poetry`, `conda`). They integrate seamlessly with the A2A protocol and can provide:

- **Agent Plugins**: Specialized agents with domain-specific capabilities
- **Gateway Plugins**: New interface types for external system integration
- **Custom Plugins**: Custom integrations such as HR providers.

All plugin interactions (create, build, add) are managed through the SAM CLI.

:::info
Run `sam plugin --help` to see the list of available commands for plugins.
:::

### Official Core Plugins

Solace Agent Mesh comes with a set of official core plugins that can be used to extend the functionality of the system. You can find the repository of the official core plugins [here 🔗](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins).

For more information about how to use the official core plugins, see [Use Plugins](#use-a-plugin).


## Create a Plugin

To get started, [install the SAM CLI](../getting-started/installation.md) and run the following command:

```bash
solace-agent-mesh plugin create <plugin-name>
```

Follow the prompts to create a new plugin. A plugin can be one of the following types:
- **Agent Plugin**: Contains custom agents that can be used in a Solace Agent Mesh project.
- **Gateway Plugin**: Contains custom gateways that can be used in a Solace Agent Mesh project.
- **Custom Plugin**: Contains custom integrations such as HR providers or other specialized functionality.

The Solace Agent Mesh (SAM) CLI creates a directory with the provided name and the following structure:

```
plugin-name/
├─ config.yaml
├─ src/
│  ├─ __init__.py
│  ├─ [...Other type specific python files]
├─ .gitignore
├─ pyproject.toml
├─ README.md
```

- The `src` directory contains the python source code. 
- The `config.yaml` file holds the configuration for the plugin, and how to be used in a SAM application.

Once the plugin is created, you can start customizing the config.yaml or the python files.

### Build the Plugin

Building the plugin creates a Python wheel package that can be installed using `pip` or other package managers.

Python `build` package must be installed already since `sam plugin build` command uses `build` package, if not, run `pip install build`.

To build the plugin, run the following SAM CLI command:

```bash
solace-agent-mesh plugin build
```

The plugin uses the standard `pyproject.toml` file to build the package. 

### Share the Plugin

To share the plugin, you can upload the wheel package to a package repository or share the wheel package directly, or any other valid way to share a `pyproject` project.

## Use a Plugin

To use a plugin in your project, use the `plugin add` command, which performs two steps under-the-hood:

- Locates the plugin or installs the plugin package using a Python package manager (like `pip` or `uv`)
- Creates a component instance based on the plugin

```bash
solace-agent-mesh plugin add <COMPONENT_NAME> --plugin <PLUGIN_NAME>
``` 
where:

`<COMPONENT_NAME>` is the name you choose for the component instance in your project.

`<PLUGIN_NAME>`, you can use:
- Name of the plugin as published to a package manager like `pypi`, for example `my-plugin`
- Name of the plugin that has been already installed into your Python environment. 
- A local path to the plugin directory, for example `./my-plugin`
- A path to a wheel package, for example `./my-plugin/dist/my_plugin-0.1.0-py3-none-any.whl`
- A URL to a git repository, for example `git+https://github.com/<USERNAME>/<REPOSITORY>`
  - If the plugin is in a subdirectory of the repository, you can specify the subdirectory using the `git+https://github.com/<USERNAME>/<REPOSITORY>#subdirectory=<PLUGIN_NAME>` syntax.

The CLI handles both steps automatically, or you can manage the plugin installation yourself using your preferred Python package manager.

:::tip
You can also customize the python package manager command used to install the plugin by setting the `SAM_PLUGIN_INSTALL_COMMAND` environment variable or passing the `--install-command` option to the `plugin add` command.
For example, to use `uv` as the package manager, you can run:

```bash
export SAM_PLUGIN_INSTALL_COMMAND="uv pip install {package}"
```

or

```bash
solace-agent-mesh plugin add <COMPONENT_NAME> --plugin <PLUGIN_NAME> --install-command "uv pip install {package}"
```
:::


This command adds the plugin instance configuration to your `configs` directory.

Depending on the plugin, you may need to update the newly added plugin configuration file. Follow the instructions provided by the plugin author for any specific configurations.

## Plugin Catalog Dashboard

You can manage available plugins with the `plugin catalog` command, which launches a user-friendly interface.

```bash
solace-agent-mesh plugin catalog
``` 
