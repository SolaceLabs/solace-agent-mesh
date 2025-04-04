---
title: Plugins
sidebar_position: 10
---

# Plugins

Plugins provide a mechanism to extend the functionality of Solace Agent Mesh in a modular, shareable, and reusable way. Plugins can be used to add new gateways, agents, and other functionalities to the system.

:::tip[In one sentence]
Plugins are essentially modular components that can be added to Solace Agent Mesh to extend its functionality.
:::

Plugins are packaged as Python modules that can be installed using the `pip` package manager or any other package manager that supports Python packages.

They can be used to import plug-and-play modules that provide complete functionality or to import configurable components that users can customize to meet their specific needs.

All the interactions with the plugins (create, build, add, and remove) are done through the Solace Agent Mesh (SAM) CLI.

:::info
Run `solace-agent-mesh plugin --help` to see the list of available commands for plugins.
:::

## Official Core Plugins

Solace Agent Mesh comes with a set of official core plugins that can be used to extend the functionality of the system. You can find repository of the official core plugins [here 🔗](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins).

For more information about how to use the official core plugins, see [Use Plugins](./use-plugins.md).


## Getting Started with Plugins

:::tip[Contribute]
Consider creating reusable plugins for the community to use and contribute to ecosystem for Solace Agent Mesh.
:::

- To get started with creating a new plugin, see  [Create a Plugin](./create-plugin.md).
- To learn more about how to use plugins, see [Use Plugins](./use-plugins.md).

