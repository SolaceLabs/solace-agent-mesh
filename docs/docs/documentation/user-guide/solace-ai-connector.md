---
title: Solace AI Event Connector
sidebar_position: 10
---

# Solace AI Event Connector

The Solace AI Event Connector is an important part of Solace Agent Mesh. It is a powerful tool designed to seamlessly integrate AI capabilities into your event-driven architecture. It enables you to create efficient pipelines that can process events from PubSub+ event brokers, using AI and other types of components, and then publish the results back to PubSub+ event brokers.

:::info[GitHub]
For more information, see [Solace AI Event Connector Github](https://github.com/SolaceLabs/solace-ai-connector).
:::

## Key Features

- **Event Processing Pipeline**: Creates flows consisting of input components, processing components, and output components.
- **AI Model Integration**: Built on LangChain and LiteLLM supporting various AI models and providers.
- **Extensible Architecture**: Supports custom plugins and components for specialized processing needs.
- **Resilient Processing**: Ensures reliable event handling with acknowledgment-based processing.
- **Scalable Design**: Supports parallel processing and multiple component instances.

## How It Works

Solace AI Event Connector operates through a series of interconnected components:

![SAC Flow Diagram](../../../static/img/sac-flows.png)

1. **Flow Structure**

   - Each flow has one input component
   - Multiple processing components
   - One output component
   - Components are connected via queues for buffering

2. **Component Processing**

   - Each component runs in its own thread
   - Processes one message at a time
   - Supports input transforms and selections
   - Can be scaled with multiple instances for parallel processing

   ![SAC Component Diagram](../../../static/img/sac_parts_of_a_component.png)

3. **Event Management**
   - Tracks events throughout the processing pipeline
   - Uses acknowledgment system for reliable delivery
   - Ensures no event loss during processing

## Configuration

The Solace AI Event Connector is configured through YAML files that allow you to:

- Define flow components and their sequence
- Set queue depths between components
- Configure the number of parallel instances
- Specify input/output parameters
- Define processing logic and transformations
- Pass the source path for the custom python components

For more information about the connector, see [Solace AI Event Connector](https://github.com/SolaceLabs/solace-ai-connector/blob/main/docs/index.md).
