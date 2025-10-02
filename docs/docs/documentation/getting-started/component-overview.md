---
title: Component Overview
sidebar_position: 40
---

# Component Overview

Solace Agent Mesh is built on event-driven architecture principles using the A2A (Agent-to-Agent) protocol, with all components communicating through a standardized protocol over the Solace broker. This architectural choice enables loose coupling between components, making the system highly flexible and scalable.

Solace Agent Mesh integrates the Google Agent Development Kit (ADK) with a Solace event mesh to provide a "Universal A2A Agent Host" that enables distributed AI agent communication. Each component is designed to perform specific roles while working together seamlessly through the A2A protocol.

The key components that make up Solace Agent Mesh are:

1. **Solace Event Broker or Event Mesh**: The central nervous system of the framework, facilitating A2A protocol communication between all components. [more 🔗](https://solace.com/products/event-broker/)

2. **A2A Protocol & Agent Registry**: The standardized communication protocol that enables agent discovery, task delegation, and peer-to-peer communication.

3. **Orchestrator**: A specialized agent responsible for breaking down requests into tasks and managing the overall workflow. [more 🔗](../concepts/orchestrator.md)

4. **Gateways**: The entry and exit points for the system, providing various interfaces (REST, HTTP SSE, webhooks, event mesh) that translate external requests into A2A protocol messages. [more 🔗](../concepts/gateways.md)

5. **Agents**: ADK-powered processing units that communicate through the A2A protocol, each bringing specialized capabilities and tools. [more 🔗](../concepts/agents.md)

6. **ADK Runtime**: The Google Agent Development Kit provides the core intelligence layer with tool execution, session management, and artifact handling capabilities.

8. **Built-in Tools**: Comprehensive tool ecosystem including artifact management, data analysis, web tools, and peer agent delegation capabilities.

9.  **Real-time Monitoring and Debugging Component**: Enables real-time monitoring of system activities and provides interactive debugging capabilities for administrators. [more 🔗](../deployment/observability.md)
