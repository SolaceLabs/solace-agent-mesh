---
title: Observability
sidebar_position: 20
---

# Observability

Solace Agent Mesh provides a comprehensive set of tools for real-time system monitoring and key insights to help you understand system states, request flows, and key insights for debugging and optimizing your system.

## Workflow Viewer

The Solace Agent Mesh web UI includes a built-in workflow viewer, which provides an interactive web-based UI for each user query and its corresponding response. This visualizer allows you to:

- Track the complete life cycle of a stimulus (request) as it moves through the system.
- Visualize the flow of requests/responses among agents, the user gateway and LLM.
- Monitor all participating agents and their activity in real-time.

To launch the workflow viewer for a specific query/response pair, click the **View Agent Workflow** icon located at the bottom left of the final response. The complete workflow chart appears in the side panel on the right.

## Agents View

The Solace Agent Mesh web UI also includes an **Agents** view, which provides a comprehensive overview of all registered agents in the system in real-time. This view allows you to:
- See all agents currently registered in the system.
- View agents description, capabilities, and skills
- View agent hierarchical topology and relationships.

To access the Agents view, open the web interface in your browser and switch to the **Agents** tab.

## Broker Observability

Solace Agent Mesh relies on a Solace event broker for all its communication. Various tools are available to monitor the event broker’s activity and message flows:

- **Solace Broker Manager** – A web-based interface where you can use the *Try Me!* tab to send and receive messages interactively.
- **[Solace Try Me VSCode Extension](https://marketplace.visualstudio.com/items?itemName=solace-tools.solace-try-me-vsc-extension)** – A convenient way to test message flows within Visual Studio Code.
- **[Solace Try Me (STM) CLI Tool](https://github.com/SolaceLabs/solace-tryme-cli)** – A command-line tool for sending and receiving messages.

To observe all message flows within the event broker, subscribe to the following topic:

```
[NAME_SPACES]a2a/v1/>
```

Replace `[NAME_SPACES]` with the namespace you are using. If none, omit the `[NAME_SPACES]` part.

:::tip
Agents periodically send registration messages, which may clutter your UI if you're using the STM VSCode extension. To filter out these messages, you can add the following topic to the ignore list:

```
[NAME_SPACES]/a2a/v1/discovery/agentcards
```
:::


## Stimulus Logs

Solace Agent Mesh includes a default monitor that records each request (stimulus) life cycle. These logs are stored as `.stim` files.

Each `.stim` file captures a complete trace of a stimulus, including:

- Every component it passed through.
- Timing and sequencing details.
- Additional contextual metadata.

These logs provide a valuable data source for further visualization, troubleshooting, and performance analysis.

By default, `.stim` files are written to the `/tmp/solace-agent-mesh/` directory.
