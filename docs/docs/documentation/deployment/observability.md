---
title: Observability
sidebar_position: 20
---

# Observability

Solace Agent Mesh provides a comprehensive set of tools for real-time system monitoring and key insights to help you to understand system states, request flows, and key insights for debugging and optimizing your system.

## Visualizer

The Solace Agent Mesh CLI includes a built-in visualizer, which provides an interactive web-based UI. This visualizer allows you to:

- Track the complete life cycle of a stimulus (request) as it moves through the system.
- Monitor all registered agents and their activity in real-time.

To launch the visualizer, run the following command:

```bash
sam visualize
```

For information about the available command options, see [Solace Agent Mesh CLI](../concepts/cli.md#visualize---run-a-web-gui-visualizer).

## Broker Observability

Solace Agent Mesh relies on a PubSub+ event broker for all its communication. Various tools are available to monitor the event broker’s activity and message flows:

- **PubSub+ Broker Manager** – A web-based interface where you can use the *Try Me!* tab to send and receive messages interactively.
- **[Solace Try Me VSCode Extension](https://marketplace.visualstudio.com/items?itemName=solace-tools.solace-try-me-vsc-extension)** – A convenient way to test message flows within Visual Studio Code.
- **[Solace Try Me (STM) CLI Tool](https://github.com/SolaceLabs/solace-tryme-cli)** – A command-line tool for sending and receiving messages.

To observe all message flows within the event broker, subscribe to the following topic:

```
[NAME_SPACES]solace-agent-mesh/v1/>
```

Replace `[NAME_SPACES]` with the namespace you are using. If none, omit the `[NAME_SPACES]` part.

:::tip
Agents periodically send registration messages, which may clutter your UI if you're using the STM VSCode extension. To filter out these messages, you can add the following topic to the ignore list:

```
![NAME_SPACES]solace-agent-mesh/v1/register/agent/>
```
:::

## Custom Monitors

In addition to built-in observability tools, you can create your own custom monitoring components to track system behavior according to your needs. 

For more information, see [Monitors](../concepts/monitors.md).

## Stimulus Logs

Solace Agent Mesh includes a default monitor that records each stimulus (request) life cycle. These logs are stored as `.stim` files using the [File service](../user-guide/advanced/services/file-service.md).

Each `.stim` file captures a complete trace of a stimulus, including:

- Every component it passed through.
- Timing and sequencing details.
- Additional contextual metadata.

These logs provide a valuable data source for further visualization, troubleshooting, and performance analysis.

By default, `.stim` files follow the [File Service](../user-guide/advanced/services/file-service.md) configuration, including automatic expiration settings to prevent unnecessary storage accumulation.
