---
title: Structure
sidebar_position: 20
---

# Structure

Solace Agent Mesh is powered by [Solace AI Event Connector](./solace-ai-connector.md), which is a tool that is controlled by YAML configuration files. These configuration files declare the flow of the components, and handle their processing and execution.

Solace AI Event Connector comes with a wide range of built-in components, but to extend its capabilities, Solace Agent Mesh introduces its own suite of components. The YAML files can be configured to point to the locations of these Python components, and load them at run-time.

:::success[Summary]
Solace Agent Mesh is built on a series of YAML configuration files that define the flow of components, and Python components that are loaded at run-time to perform the processing.
:::

## YAML Configuration Files

The configuration files required to run Solace Agent Mesh are automatically copied over to your build directory (`build_directory`) at build time when you run the `sam build` command.

- **You do not need to modify these config files directly**, and providing the proper environment variables is enough in most cases. However, in case you do need to modify the configuration files, you can use **overwrites** to do so.
  For more information, see [Overwrites](../user-guide/advanced/overwrites.md).

- **Each time you add an agent or a gateway, appropriate configuration files are generated.** These configuration files are bundled along with the framework configuration files and copied to the build directory.

- **Each YAML configuration file can be run standalone.** You might want to separate your project into multiple processes to meet your scaling needs. For information about different ways to deploy your app, see [Deployment](../deployment/deploy.md).

## Python Components

The Python components you need to run Solace Agent Mesh are provided through the Python SDK installed along with the Solace Agent Mesh CLI. The components can be directly imported into your project.

For example:

```py
from solace_agent_mesh.agents.base_agent_component import BaseAgentComponent

class MyAgent(BaseAgentComponent):
    def __init__(self):
        super().__init__()
```

The Python components from your custom agents and gateways are located under your source directory, which is copied to the build directory at build time.

You are not able to directly change the core components, but many components such as the [File service](../user-guide/advanced/services/file-service.md) and [History service](../user-guide/advanced/services/history-service.md) have base classes that can be extended to meet your requirements.
