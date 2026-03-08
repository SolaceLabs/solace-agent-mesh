---
title: Developing with Agent Mesh
sidebar_position: 400
---

# Developing with Agent Mesh

Agent Mesh provides a framework for creating distributed AI applications using an event-driven architecture. You can build agents that communicate through the A2A (Agent-to-Agent) protocol, extend them with custom tools, integrate external systems through gateways, and create reusable components as plugins.

:::tip
Vibe coding is recommended for faster development of agents, plugins, tools, and gateways. For more details, see the [Vibe Coding guide](../vibe_coding.md).
:::

## Understanding the Project Structure

The framework uses YAML configuration files to define agents, gateways, and plugins, although you can extend functionality with custom Python components when needed. For a complete overview of project organization and component relationships, see [Project Structure](structure.md).

## Building Intelligent Agents

Agents are LLM-powered components that use tools to accomplish tasks and communicate with other agents through the A2A protocol. You can define tools as Python functions, configure agent behavior through YAML, and manage agent lifecycles effectively. For comprehensive guidance on agent development, see [Creating Agents](create-agents.md).

The [Build Your Own Agent](tutorials/custom-agent.md) tutorial demonstrates creating a weather agent with external API integration, resource management, and artifact creation.

## Orchestrating Agents with Workflows

Workflows let you coordinate multiple agents through YAML configuration rather than AI-driven orchestration. You define the execution sequence, conditional branches, and data flow between agents explicitly. Workflows are useful when you need predictable execution paths, auditability, or control over exactly which agents run and in what order. The UI visualizes workflow progress in real time. For step-by-step guidance, see [Creating Workflows](creating-workflows.md).

## Extending Agent Capabilities

You can create custom Python tools using three patterns: simple function-based tools, advanced single-class tools, or tool providers that generate multiple related tools dynamically. The framework handles tool discovery, parameter validation, and lifecycle management automatically. For detailed information on all patterns, see [Creating Python Tools](creating-python-tools.md).

## Connecting External Systems

Gateways bridge external systems and the A2A ecosystem by translating external events into standardized A2A tasks and responses back to external formats. Whether you're integrating chat systems, web applications, IoT devices, or file systems, gateways provide the necessary translation layer. For complete guidance on gateway development, see [Create Gateways](create-gateways.md).

## Integrating Enterprise Data Sources

Service providers offer a standardized way to integrate backend systems like HR platforms or CRMs through well-defined interfaces. You can create providers that handle both identity enrichment and directory queries, reducing code duplication while maintaining clean separation of concerns. For implementation guidance, see [Creating Service Providers](creating-service-providers.md).

## Practical Integration Examples

The tutorials provide hands-on examples for common scenarios: [Slack Integration](tutorials/slack-integration.md) for workspace connectivity, [REST Gateway](tutorials/rest-gateway.md) for RESTful APIs, and [MCP Integration](tutorials/mcp-integration.md) for Model Context Protocol servers. Additional tutorials cover database integration, RAG implementations, and cloud service connections.

## Development Patterns

The framework supports both direct component creation and plugin-based development. Plugins offer better reusability and distribution, while direct components provide simpler project-specific implementations. The configuration-driven approach uses YAML files to define behavior and Python code for core logic, enabling flexible deployment scenarios and easier management of complex distributed systems.

## Evaluating Agents

The framework includes an evaluation system that helps you test your agents' behavior in a structured way. You can define test suites, run them against your agents, and generate detailed reports to analyze the results. When running evaluations locally, you can also benchmark different language models to see how they affect your agents' responses. For more information, see [Evaluating Agents](evaluations.md).
