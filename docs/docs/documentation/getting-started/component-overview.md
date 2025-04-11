---
title: Component Overview
sidebar_position: 50
---

# Component Overview

The Solace Agent Mesh (SAM) is built on event-driven architecture principles, with all components communicating via events flowing through a central event broker. This architectural choice enables loose coupling between components, making the system highly flexible and scalable.

Each component in SAM is designed to perform specific roles while working together seamlessly through event-based communication. This approach allows the system to handle everything from simple AI tasks to complex workflows that combine multiple AI and conventional processing steps.

The key components that make up SAM are:

1. **PubSub+ Event Broker or Event Mesh**: The central nervous system of the framework, facilitating pub/sub communication between all components. [more 🔗](https://solace.com/products/event-broker/)

2. **Orchestrator**: A specialized agent responsible for breaking down requests into tasks and managing the overall workflow. [more 🔗](../concepts/orchestrator.md)

3. **Gateway**: The entry and exit points for the system, providing a custom interface for each use case. [more 🔗](../concepts/gateways.md)

4. **Agents**: Specialized processing units, which can be AI-enabled or conventional, that subscribe to and process specific tasks. [more 🔗](../concepts/agents.md)

5. **Monitors**: Passive components that observe system behavior, enforce policies, collect analytics, and raise notifications when needed. They subscribe to events flowing through the system to ensure compliance, gather metrics, and detect issues requiring attention. [more 🔗](../concepts/monitors.md)

6. **Services**: Additional services that support the core components, such as LLMs, temporary file storage, and logging/monitoring. [more 🔗](../concepts/services.md)

7. **Real-time Monitoring and Debugging Component**: Enables real-time monitoring of system activities and provides interactive debugging capabilities for administrators. [more 🔗](../deployment/observability.md)
