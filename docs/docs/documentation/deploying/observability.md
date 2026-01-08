---
title: Monitoring Your Agent Mesh
sidebar_position: 20
---

# Monitoring Your Agent Mesh

Understanding how your Agent Mesh system operates in real-time is crucial for maintaining optimal performance and quickly identifying issues. The platform provides a comprehensive observability suite that gives you deep insights into system behavior, message flows, and agent interactions.

These observability tools work together to create a complete picture of your system's health and performance. Whether you're troubleshooting a specific issue, optimizing performance, or simply monitoring day-to-day operations, these tools provide the visibility you need to maintain a robust agent mesh.

:::tip Complementary Tools
The observability features described here focus on runtime behavior and message flows. For information about application logging, see [Logging Configuration](./logging.md).
:::

## Viewing Workflows

The workflow viewer serves as your primary window into how individual requests flow through your agent mesh. This interactive visualization tool transforms complex multi-agent interactions into clear, understandable diagrams that show exactly how your system processes each user query.

Understanding request flow is essential because Agent Mesh operates as a distributed system where multiple agents collaborate to fulfill user requests. The workflow viewer makes these interactions transparent by providing an interactive web-based interface for each user query and its corresponding response.

The workflow viewer enables you to:

**Track complete request lifecycles**: Follow a stimulus (request) from its initial entry point through every agent interaction until the final response is delivered to the user.

**Visualize inter-component communication**: See how requests and responses flow between agents, the user gateway, and language models, helping you understand the collaboration patterns in your mesh.

**Monitor real-time agent activity**: Observe which agents are actively participating in request processing and identify potential bottlenecks or failures.

To access the workflow viewer for any specific interaction, click the **View Agent Workflow** icon located at the bottom left of the final response in the web UI. The complete workflow chart will appear in the side panel on the right, providing an immediate visual representation of the entire request processing flow.

## Viewing Agents

The Agents view complements the workflow viewer by providing a bird's-eye perspective of your entire agent ecosystem. While the workflow viewer focuses on individual request flows, the Agents view helps you understand the overall structure and health of your agent mesh.

This real-time dashboard becomes particularly valuable as your agent mesh grows in complexity. It allows you to quickly assess which agents are available, understand their capabilities, and visualize how they relate to each other within the system hierarchy.

The Agents view provides several key insights:

**Real-time agent registry**: See all agents currently registered and active in your system, giving you immediate visibility into system availability and health.

**Agent capabilities and descriptions**: Review what each agent can do, including their specific skills and the types of requests they can handle, helping you understand how work gets distributed across your mesh.

**Hierarchical topology visualization**: Understand the relationships between agents and how they're organized within your system architecture, which is crucial for troubleshooting and optimization.

To access this comprehensive overview, open the web interface in your browser and switch to the **Agents** tab.

## Monitoring Event Broker Activity

The Solace event broker serves as the central nervous system of your agent mesh, handling all communication between components. Monitoring Solace event broker activity provides deep insights into system behavior and helps identify communication issues before they impact users.

Understanding message flows at the event broker level is essential because it reveals the actual communication patterns between your agents, regardless of how they're configured. This low-level visibility complements the higher-level views provided by the workflow viewer and agents dashboard.

Several specialized tools help you monitor and interact with the Solace event broker:

**Solace Broker Manager**: This web-based interface provides comprehensive event broker management capabilities. The *Try Me!* tab is particularly useful for interactive message testing, allowing you to send and receive messages manually to verify system behavior.

**[Solace Try Me VSCode Extension](https://marketplace.visualstudio.com/items?itemName=solace-tools.solace-try-me-vsc-extension)**: Integrates message testing directly into your development environment, making it convenient to test message flows without leaving Visual Studio Code.

**[Solace Try Me (STM) CLI Tool](https://github.com/SolaceLabs/solace-tryme-cli)**: Provides command-line access to message testing capabilities, ideal for scripting and automation scenarios.

### Monitoring Message Flows

To observe comprehensive message activity within your agent mesh, subscribe to the following topic pattern:

```
[NAME_SPACES]a2a/v1/>
```

Replace `[NAME_SPACES]` with the namespace you are using. If you're not using namespaces, omit the `[NAME_SPACES]` part entirely.

This subscription captures all agent-to-agent communication, providing complete visibility into your mesh's message flows.

:::tip Filtering Registration Messages
Agents periodically send registration messages to announce their availability. These messages can clutter your monitoring interface when using tools like the STM VSCode extension. To focus on actual request/response traffic, add the following topic to your ignore list:

```
[NAME_SPACES]/a2a/v1/discovery/agentcards
```

This filter removes routine registration messages while preserving visibility into meaningful agent interactions.
:::


## Examining Stimulus Logs

Stimulus logs provide the most detailed level of observability in your Agent Mesh system. While the workflow viewer gives you visual representations and the Solace event broker tools show real-time message flows, stimulus logs create permanent, comprehensive records of every request that flows through your system.

These logs serve as your system's memory, capturing complete traces that you can analyze long after events occur. This persistent record becomes invaluable for performance analysis, debugging complex issues, and understanding usage patterns over time.

Agent Mesh includes a default monitor that automatically records each request (stimulus) lifecycle without requiring additional configuration. These detailed traces are stored as `.stim` files, creating a comprehensive audit trail of system activity.

### Understanding Stimulus Log Content

Each `.stim` file contains a complete trace of a single stimulus journey through your agent mesh:

**Component traversal paths**: Every agent, gateway, and service that handled the request, providing a complete map of the processing pipeline.

**Timing and sequencing details**: Precise timestamps showing when each component received, processed, and forwarded the request, enabling performance analysis and bottleneck identification.

**Contextual metadata**: Additional information about the request context, user session, and system state that influenced processing decisions.

These comprehensive logs create a valuable data source for advanced visualization tools, detailed troubleshooting sessions, and performance optimization efforts. Because they capture the complete picture of each request, they're particularly useful for understanding complex multi-agent interactions that might be difficult to trace through other observability tools.

### Storage Location

By default, `.stim` files are written to the `/tmp/solace-agent-mesh/` directory. This location provides fast access for analysis while keeping logs separate from your application data.
