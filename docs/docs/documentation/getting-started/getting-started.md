---
title: Getting Started
sidebar_position: 12
---

# Get Started with Agent Mesh

Agent Mesh is an open-source framework for building event-driven multi-agent AI systems that solve complex problems through intelligent collaboration. You can use it to create teams of specialized AI agents that work together seamlessly, each bringing unique capabilities while communicating through Solace's proven event-driven architecture.

Whether you're building intelligent automation systems, creating sophisticated AI workflows, or integrating AI capabilities across your enterprise, Agent Mesh provides the foundation you need. The framework handles agent communication automatically, so you can focus on building powerful AI experiences that scale with your needs.

:::info
Agent Mesh is built for modern development workflows. Whether you're using Claude, GitHub Copilot, or another AI coding assistant, our documentation is optimized to help you quickly understand the framework and build your projects faster. See our [Vibe Coding guide](../vibe_coding.md) to learn more.
:::

## Understanding Agent Mesh

Before diving into implementation, it's helpful to understand what makes Agent Mesh unique. The framework combines the power of Google's Agent Development Kit with Solace's event-driven messaging platform, creating a robust foundation for multi-agent AI systems. To learn about the core concepts and architectural principles that drive the framework's design, see [What is Agent Mesh?](./introduction.md)

The system's event-driven architecture enables true scalability and reliability, allowing agents to communicate asynchronously while maintaining loose coupling between components. For detailed insights into how these components work together to create a cohesive AI ecosystem, see [Architecture Overview](./architecture.md)

To see how all the pieces fit together, you can explore the key building blocks that make up every Agent Mesh deployment. For more information, see [Components Overview](../components/components.md)

## Getting Started Quickly

The fastest way to experience Agent Mesh is through our pre-configured Docker setup that gets you up and running with a working system in minutes. This approach lets you explore the framework's capabilities immediately without any installation or complex configuration. To get started right away, see [Try Agent Mesh](./try-agent-mesh.md)

Once you've explored the basic functionality and want to set up your own development environment, you'll need to install the CLI and framework tools. The installation process supports multiple approaches including pip, uv, and Docker, making it easy to integrate with your existing workflow. For complete setup instructions, see [Installation](../installing-and-configuring/installation.md)

For those ready to build their own projects from scratch, comprehensive guidance is available for creating and configuring custom deployments with full control over your agent mesh. This approach provides the flexibility needed for serious development work and production environments. To learn about project creation and configuration, see [Creating and Running an Agent Mesh Project](../installing-and-configuring/run-project.md)

## Building with Agent Mesh

Creating effective AI systems requires understanding how to design and implement the right components for your use case. The framework provides several key building blocks that you can combine and customize to meet your specific needs.

Specialized AI components can perform specific tasks, access particular data sources, or integrate with external systems, with each agent bringing its own capabilities while participating in the larger collaborative ecosystem. To learn how to build these components, see [Creating Agents](../developing/create-agents.md)

Interfaces that connect your agent mesh to the outside world enable integration through REST APIs, web interfaces, chat platforms, or custom integrations. For guidance on building these connection points, see [Creating Gateways](../developing/create-gateways.md)

Custom tools extend functionality beyond the built-in capabilities, allowing agents to interact with databases, APIs, file systems, or any other resources your applications require. To understand how to add these extensions, see [Creating Python Tools](../developing/creating-python-tools.md)

## Core Components

Agent Mesh is built around several fundamental components that work together to create intelligent, collaborative systems. Understanding these components helps you design effective solutions and troubleshoot issues when they arise.

The intelligent workers of your system are powered by AI models and equipped with specialized tools, capable of analyzing data, generating content, making decisions, and delegating tasks to other agents when needed. For more information, see [Agents](../components/agents.md)

Bridges between your agent mesh and external systems translate requests from users, applications, or other systems into the standardized communication protocol that agents understand. To learn about these interface components, see [Gateways](../components/gateways.md)

The conductor of your agent symphony breaks down complex requests into manageable tasks and coordinates the work of multiple agents to achieve sophisticated outcomes. For details about this coordination system, see [Orchestrator](../components/orchestrator.md)

A powerful extension mechanism lets you add new capabilities to your system without modifying core components, making it easy to integrate with existing tools and services. To understand how to extend your system, see [Plugins](../components/plugins.md)

Comprehensive command-line tools manage your projects from initial setup through deployment and ongoing maintenance. For information about these development tools, see [CLI](../components/cli.md)

## Advanced Capabilities

As your AI systems grow in complexity and scale, Agent Mesh provides advanced features to support enterprise deployments and sophisticated use cases.

Various approaches for running Agent Mesh in production range from single-machine setups to distributed enterprise deployments across multiple environments. To explore your deployment options, see [Deployment Options](../deploying/deployment-options.md).

For comprehensive guidance on deploying to Kubernetes with Helm charts and enterprise configurations, see [Kubernetes](../deploying/kubernetes/kubernetes.md).

Real-time monitoring capabilities help you track performance metrics and debug issues when they occur, with the framework's event-driven architecture providing natural visibility into all system interactions. For guidance on system monitoring, see [Observability](../deploying/observability.md)

Organizations with specific security and governance requirements can leverage advanced capabilities including role-based access control, single sign-on integration, and enterprise-grade security features. To learn about these advanced features, see [Enterprise Features](../enterprise/enterprise.md)

## Learning Through Examples

Practical tutorials help you understand how to apply Agent Mesh to real-world scenarios. These hands-on guides walk you through building complete solutions that demonstrate the framework's capabilities.

Creating agents that can query databases and provide intelligent responses based on your organization's data demonstrates how to integrate with existing data sources. For a complete walkthrough, see [SQL Database Integration](../developing/tutorials/sql-database.md)

Building a gateway that lets users interact with your agent mesh directly through Slack brings AI capabilities into existing workflows and communication platforms. To learn how to set this up, see [Slack Integration](../developing/tutorials/slack-integration.md)

Creating a specialized agent from scratch, including tool integration and configuration, shows you the complete development process for custom components. For step-by-step guidance, see [Custom Agent Tutorial](../developing/tutorials/custom-agent.md)

Incorporating Model Context Protocol servers into your agent mesh extends capabilities through standardized integrations with external tools and services. To understand this integration approach, see [MCP Integration](../developing/tutorials/mcp-integration.md)

## Additional Resources

Beyond the core documentation, several resources can help you get the most out of Agent Mesh. The latest source code, example configurations, and community discussions are available in the [GitHub repository](https://github.com/SolaceLabs/solace-agent-mesh)

Pre-built functionality for common use cases provides tested integrations that you can incorporate into your own projects. You can find these extensions in the [official plugins repository](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins)

Participating in the project's development is possible through reporting issues, suggesting improvements, or contributing code. To learn how you can get involved, see the [Contributing Guide](https://github.com/SolaceLabs/solace-agent-mesh/blob/main/CONTRIBUTING.md)