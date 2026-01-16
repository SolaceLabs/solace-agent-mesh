---
title: Components
sidebar_position: 200
---

Agent Mesh provides a comprehensive set of components that work together to create a distributed AI agent ecosystem. Each component serves a specific purpose, from managing the command-line interface to orchestrating complex multi-agent workflows.

This section introduces you to the key components and tools that make up the system. You'll find detailed documentation for each component, along with configuration examples and best practices for implementation.

## Agents

Agents are the intelligent processing units that perform tasks within the mesh. Each agent combines the Google Agent Development Kit (ADK) with specialized instructions, LLM configurations, and toolsets to create focused AI capabilities. Agents can work independently or collaborate with other agents to solve complex problems. You can configure agents with different personalities, expertise areas, and access permissions to match your specific use cases. For comprehensive agent configuration and development guidance, see [Agents](./agents.md).

## Workflows

Workflows provide an alternative to the orchestrator for coordinating multiple agents. While the orchestrator uses AI to dynamically determine how to accomplish tasks, workflows follow explicit execution paths defined in YAML configuration. You specify which agents to call, in what order, and how data flows between them. Workflows support conditional branching, parallel iteration over collections, and polling loops. They're well-suited for business processes that require predictable, auditable execution—the same input always produces the same sequence of agent calls. The UI visualizes workflow execution in real time. For workflow configuration and node types, see [Workflows](./workflows.md).

## Gateways

Gateways serve as the entry and exit points for your agent mesh, translating between external protocols and the internal A2A communication standard. Whether you need REST APIs, webhooks, WebSocket connections, or integrations with platforms like Slack, gateways handle the protocol conversion and session management. They also manage authentication and authorization, ensuring that user permissions are properly enforced throughout the system. For gateway development and configuration details, see [Gateways](./gateways.md).

## Platform Service

The Platform Service is a backend microservice responsible for management operations in Solace Agent Mesh. For more details, see [Platform Service](./platform-service.md).

## Orchestrator

The orchestrator is a specialized agent that manages complex workflows by breaking down requests into smaller tasks and coordinating their execution across multiple agents. It understands dependencies between tasks, manages parallel execution, and aggregates results to provide comprehensive responses. The orchestrator is particularly valuable for scenarios that require multiple specialized agents to work together toward a common goal. For orchestrator configuration and workflow design patterns, see [Orchestrator](./orchestrator.md).

## Plugins

Plugins extend the capabilities of Agent Mesh by providing custom tools, integrations, and functionality. You can develop plugins to connect with proprietary systems, add domain-specific tools, or integrate with external services that aren't covered by the built-in toolset. The plugin system provides a standardized way to package and distribute custom functionality across your organization. For plugin development guidelines and examples, see [Plugins](./plugins.md).

## Built-in Tools

Agent Mesh includes a comprehensive set of built-in tools that provide essential capabilities for most AI agent scenarios. These tools handle common tasks like artifact management, data analysis, web interactions, and inter-agent communication. The built-in tools are designed to work seamlessly with the A2A protocol and provide consistent behavior across all agents in your mesh. For detailed documentation of available tools and their usage, see [Built-in Tools](./builtin-tools/builtin-tools.md).

## Command Line Interface

The CLI provides the primary interface for managing your Agent Mesh deployment. You can use it to start agents, configure gateways, monitor system health, and perform administrative tasks. The CLI simplifies complex operations and provides helpful feedback during development and deployment. For complete CLI documentation and command reference, see [CLI](./cli.md).
