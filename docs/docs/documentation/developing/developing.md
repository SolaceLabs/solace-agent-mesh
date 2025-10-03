---
title: Developing with Solace Agent Mesh
sidebar_position: 400
---

# Developing with Solace Agent Mesh

Solace Agent Mesh provides a powerful framework for creating distributed AI applications using an event-driven architecture. The platform enables you to build agents that communicate seamlessly through the A2A (Agent-to-Agent) protocol, powered by Solace's robust messaging infrastructure. You can extend these agents with custom tools, integrate external systems through gateways, and create reusable components as plugins.

## Understanding the Architecture

Before diving into development, you'll want to understand how Solace Agent Mesh organizes projects and manages configurations. The framework uses a structured approach where YAML configuration files define your agents, gateways, and plugins, although you can extend functionality with custom Python components when needed. For a complete overview of how projects are organized and how the various components work together, see [Project Structure](structure.md).

## Building Intelligent Agents

Agents are the core intelligence units in Solace Agent Mesh. These LLM-powered components use tools to accomplish tasks and can communicate with other agents through the A2A protocol. You'll learn how to define tools as Python functions, configure agent behavior through YAML, and manage agent lifecycles effectively. The framework provides both simple function-based tools and advanced dynamic tool patterns to suit different complexity requirements. For comprehensive guidance on agent development, see [Creating Agents](create-agents.md).

If you prefer hands-on learning, the [Build Your Own Agent](tutorials/custom-agent.md) tutorial walks you through creating a sophisticated weather agent that demonstrates external API integration, proper resource management, and artifact creation.

## Extending Agent Capabilities

The real power of Solace Agent Mesh agents comes from their tools. You can create custom Python tools using three different patterns, from simple function-based tools to advanced tool providers that generate multiple related tools dynamically. The framework handles tool discovery, parameter validation, and lifecycle management automatically. For detailed information on all tool creation patterns, including configuration validation and resource management, see [Creating Python Tools](creating-python-tools.md).

## Connecting External Systems

Gateways serve as bridges between external systems and the A2A ecosystem. They translate external events and data into standardized A2A tasks, submit these to appropriate agents, and translate responses back to external formats. Whether you're integrating chat systems, web applications, IoT devices, or file systems, gateways provide the translation layer you need. For complete guidance on gateway development, including architecture patterns and implementation details, see [Create Gateways](create-gateways.md).

## Integrating Enterprise Data Sources

When building enterprise applications, you often need to connect agents and gateways to backend systems like HR platforms or CRMs. Service providers offer a standardized way to integrate these data sources through well-defined interfaces. You can create providers that handle both identity enrichment and general directory queries, reducing code duplication while maintaining clean separation of concerns. For step-by-step implementation guidance, see [Creating Service Providers](creating-service-providers.md).

## Practical Integration Examples

The tutorials section provides hands-on examples for common integration scenarios. You can learn how to integrate with Slack workspaces through [Slack Integration](tutorials/slack-integration.md), create RESTful APIs for external system access with [REST Gateway](tutorials/rest-gateway.md), or connect to Model Context Protocol servers using [MCP Integration](tutorials/mcp-integration.md). Additional tutorials cover database integration, RAG implementations, and cloud service connections.

## Development Patterns and Best Practices

Throughout your development journey, you'll encounter various patterns and architectural decisions. The framework supports both direct component creation and plugin-based development, each with distinct advantages. Plugins offer better reusability and distribution, while direct components provide simpler project-specific implementations. The documentation guides you through these choices and helps you select the most appropriate approach for your specific requirements.

The framework also emphasizes configuration-driven development, where YAML files define behavior and Python code implements the core logic. This separation enables flexible deployment scenarios and makes it easier to manage complex distributed systems. Environment variables and shared configuration patterns help maintain consistency across different deployment environments.

As you explore these capabilities, you'll discover that Solace Agent Mesh provides both the flexibility to create simple solutions quickly and the power to build sophisticated, enterprise-grade applications. The event-driven architecture ensures your components can scale and evolve as your requirements grow.