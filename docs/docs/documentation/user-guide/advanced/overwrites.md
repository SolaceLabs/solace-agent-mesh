---
title: Overwrites
sidebar_position: 10
---

# Overwrites

Solace Agent Mesh is powered by the [Solace AI Event Connector](../../user-guide/solace-ai-connector.md), which is configured through YAML config files.

:::tip[Prerequisites]  
Before you create overwrites, you should have a good understanding of the Solace AI Event Connector. For more information, see [Solace AI Event Connector](../../user-guide/solace-ai-connector.md).  
:::

There are two cases where you might need to use the `overwrites` feature:

- Overwriting system configurations
- Adding custom workflows

## Overwriting System Configurations

All internal components in Solace Agent Mesh are configured through YAML files. When building a project, you will see these files in the build directory. In some cases, you may want to customize certain files, but **the build directory should never be manually edited**. All content in the build directory is generated and overwritten at build time.

By placing a file with the same name in the `overwrites` directory, you can overwrite the content of the original system file.

The most common use case for this feature is customizing the configurations for the [LLM Service](./services/llm-service.md) or [Embedding Service](./services/embedding-service.md).

Check their respective pages for more information on configurations.

## Adding Custom Workflows

There may be cases where you need a specific workflow that does not fall under one of the components in Solace Agent Mesh (agents, gateways, etc.). In such cases, you can create your own custom [Solace AI Event Connector](../../user-guide/solace-ai-connector.md) workflow and place it in the `overwrites` directory.

Ensure sure to use a unique name for your workflow to avoid conflicts with system components.

Your files will be included in the build directory and will run alongside other components, provided you are using the `sam run` command. For more information about custom deployments, check the [Deployments](../../deployment/deploy.md) page.

:::warning  
Avoid placing any YAML files in the `overwrites` directory that are not [Solace AI Event Connector](../../user-guide/solace-ai-connector.md) workflows, as this will cause a runtime error.  
:::
