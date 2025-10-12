---
title: What is Agent Mesh?
sidebar_position: 14
---

Modern AI development faces a fundamental challenge: powerful AI models are readily available, but it's complicated to connect them to the data and systems where they can provide value. Because the data that drives these AI models often exists in isolated silos (databases, SaaS platforms, APIs, and legacy systems), it can be difficult to build AI applications that work across these boundaries.

Agent Mesh is an open-source framework that tackles this challenge head-on by focusing on being an excellent integration layer. Built on Solace's proven event-driven architecture and integrated with Google Agent Development Kit (ADK), Agent Mesh brings together specialized agents—whether they're using local databases, accessing cloud APIs, or interfacing with enterprise systems—and helps them collaborate using standardized A2A communication to solve complex problems.

![Agent Mesh Overview](../../../static/img/Solace_AI_Framework_With_Broker.png)

Agent Mesh is built on:

- **Event-Driven Architecture at the Core:**
  The beating heart of Agent Mesh is its event mesh—a neural network for your AI components that creates a fluid, asynchronous communication layer where messages flow naturally between agents, gateways, and external systems. By decoupling senders from receivers, the mesh dramatically simplifies agent interactions, ensures message delivery even during component failures, and lets you add, remove, or restart components on-the-fly without disrupting workflows.

- **Unified AI Collaboration:**
  Agent Mesh breaks down AI silos by enabling specialized agents to operate independently yet collaborate effortlessly. The framework blends diverse AI models, custom tools (such as Python functions and MCP tools), and enterprise data sources into a cohesive ecosystem.

- **Complex Workflow Orchestration:**
  Agent Mesh creates sophisticated multi-agent processes where tasks flow naturally between specialists, executing in sequence or parallel based on dynamic needs through standardized A2A communication.

- **Seamless System Integration:**
  Purpose-built gateways bridge the gap between Agent Mesh and your existing systems—web interfaces, Slack workspaces, APIs, and event streams.

- **Exponential Capability Growth:**
  Each new agent enhances all other agents through collaboration, creating exponential rather than additive capability increases. Each new gateway opens entirely new use cases for the system.

- **Enterprise-Grade Reliability:**
  Built on Solace Event Broker, Agent Mesh delivers high-throughput, fault-tolerant messaging that scales with your needs. Engineered from the ground up for production deployments, Agent Mesh leverages expertise from Solace in building mission-critical distributed systems.

- **Developer-Friendly Design:**
  YAML-based configuration provides precise control without code changes. Modular components can be reused, replaced, or enhanced independently with built-in security and authorization frameworks.

- **Extensibility:**
  Agent Mesh grows with your needs. Organizations typically start with basic agents and continuously expand capabilities by adding specialized integrations, multiple interface options, and diverse AI model integrations. Plug-and-play extensibility means new agents automatically publish capabilities with no manual configuration or downtime.


## Real-World Applications

Agent Mesh is already solving real problems across industries:

- **Intelligent Enterprise Automation:** Customer service systems that route inquiries to specialized agents and data processing pipelines that transform, analyze, and enrich information from multiple sources.

- **AI Task Specialization:** Image analysis workflows with visual processing and text generation specialists, and document processing systems that extract, summarize, and translate content through coordinated agents.

- **Human-AI Collaboration:** Complex task execution that keeps humans in the loop for approvals, clarifications, or expert guidance via web or chat interfaces.

- **Data-Driven Intelligence:** Agents that query databases, transform results, and generate visualizations based on natural language requests or system events.

## For Developers

Agent Mesh is an agentic framework that provides several key technical advantages:

- **Complete Observability**: Because all communication flows through the event broker, you can monitor and debug the entire system in real-time
- **Flexible Integration**: Built-in support for common enterprise systems and AI frameworks
- **Plugin Architecture**: Easily extend the system with custom agents and gateways
- **Developer Tools**: Comprehensive CLI and debugging utilities

## Getting Started

Whether you're building a proof-of-concept or planning a production deployment, Agent Mesh provides the foundation you need. For more information, see:

- [Getting Started](../getting-started/getting-started.md): For an overview of Agent Mesh and what you can find in this documentation.
- [Installation](../installing-and-configuring/installation.md): For installing and setting up Agent Mesh.
- [Quick Start](./try-agent-mesh.md): For creating a project, building, and running Agent Mesh.
- [Component Overview](../components/components.md): Understanding the parts of Agent Mesh.
