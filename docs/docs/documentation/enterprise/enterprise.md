---
title: Agent Mesh Enterprise
sidebar_position: 700
---

# Agent Mesh Enterprise

Agent Mesh Enterprise extends the open-source framework with production-ready features that enterprise environments require. This version provides enhanced security through single sign-on integration, granular access control through role-based permissions, intelligent data management for cost optimization, and comprehensive observability tools for monitoring agent workflows and system performance.

Enterprise is available as a self-managed container image that you can deploy in your own infrastructure. You can obtain access by joining the pilot program at [solace.com/solace-agent-mesh-pilot-registration](https://solace.com/solace-agent-mesh-pilot-registration/).

## Enterprise Features

The Enterprise version delivers several capabilities that distinguish it from the Community edition.

Authentication and authorization integrate with your existing identity systems through SSO, eliminating the need for separate credentials while maintaining security standards. You can configure role-based access control to implement granular authorization policies that determine which agents and resources each user can access through the Agent Mesh Gateways.

Data management features help you optimize costs and improve accuracy. Smart filtering capabilities reduce unnecessary compute expenses while precise data governance helps prevent hallucinations by controlling what information reaches your language models.

Observability tools provide complete visibility into your agent ecosystem. The built-in workflow viewer tracks LLM interactions and agent communications in real time, giving you the insights needed to monitor performance, diagnose issues, and understand system behavior.

## Getting Started with Enterprise

Setting up Agent Mesh Enterprise involves installation, security configuration, and authentication setup.

### Installation

The Docker-based installation process downloads the enterprise image from the Solace Product Portal, loads it into your container environment, and launches it with the appropriate configuration for your deployment scenario. You can run Enterprise in development mode with an embedded broker for testing, or connect it to an external Solace broker for production deployments. For complete installation instructions, see [Installing Agent Mesh Enterprise](installation.md).

### Access Control

Role-based access control lets you define who can access which agents and features in your deployment. You create roles that represent job functions, assign permissions to those roles through scopes, and then assign roles to users. This three-tier model implements the principle of least privilege while simplifying administration. For guidance on planning and implementing RBAC, see [Setting Up RBAC](rbac-setup-guide.md).

### Single Sign-On

SSO integration connects Agent Mesh Enterprise with your organization's identity provider, whether you use Azure, Google, Auth0, Okta, Keycloak, or another OAuth2-compliant system. The configuration process involves creating YAML files that define the authentication service and provider settings, then launching the container with the appropriate environment variables. For step-by-step configuration instructions, see [Enabling SSO](single-sign-on.md).

### Connectors

Connectors link agents to external data sources such as databases and APIs, enabling agents to retrieve and analyze information through natural language interactions. The Enterprise version supports SQL connectors for MySQL, PostgreSQL, and MariaDB databases. You create connectors in the Connectors section of the web interface, where they become available for assignment to any agent in your deployment. All agents assigned to a connector share the same credentials, requiring careful planning of data source permissions to maintain appropriate access control. For information about creating and managing connectors, see [Connectors](connectors/connectors.md).

### Agent Builder

The Enterprise version includes Agent Builder, a visual interface for creating and managing agents without writing configuration files directly. Agent Builder supports both AI-assisted generation from natural language descriptions and manual configuration for precise control over agent capabilities. You can create agents, assign toolsets and connectors, and deploy them dynamically through the Deployer component without restarting services. The Deployer handles deployment operations asynchronously, enabling scalable agent creation through the web interface. You can also download agent configurations as YAML files for version control or infrastructure-as-code deployments. For comprehensive information about creating and managing agents, see [Agent Builder](agent-builder.md).

## What's Next

After you complete the initial setup and create agents using Agent Builder, you can begin deploying them to make them available for user interactions. The Enterprise features operate transparently—your agents and tools work the same way, but with the added security, governance, and observability that production environments demand.