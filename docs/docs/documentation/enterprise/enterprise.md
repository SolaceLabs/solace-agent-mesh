---
title: Agent Mesh Enterprise
sidebar_position: 700
---

# Agent Mesh Enterprise

Agent Mesh Enterprise extends the open-source framework with production-ready features that enterprise environments require. This version provides enhanced security through single sign-on integration, granular access control through role-based permissions, intelligent data management for cost optimization, and comprehensive observability tools for monitoring agent workflows and system performance.

Enterprise is available as a self-managed container image that you can deploy in your own infrastructure. You can obtain access by joining the pilot program at [solace.com/solace-agent-mesh-pilot-registration](https://solace.com/solace-agent-mesh-pilot-registration/).

## Enterprise Features

The Enterprise version delivers several key capabilities that distinguish it from the Community edition.

Authentication and authorization integrate with your existing identity systems through SSO, eliminating the need for separate credentials while maintaining security standards. You can configure role-based access control to implement granular authorization policies that determine which agents and resources each user can access through the Agent Mesh Gateways.

Data management features help you optimize costs and improve accuracy. Smart filtering capabilities reduce unnecessary compute expenses while precise data governance helps prevent hallucinations by controlling what information reaches your language models.

Observability tools provide complete visibility into your agent ecosystem. The built-in workflow viewer tracks LLM interactions and agent communications in real time, giving you the insights needed to monitor performance, diagnose issues, and understand system behavior.

## Getting Started with Enterprise

Setting up Agent Mesh Enterprise involves three main areas: installation, security configuration, and authentication setup.

### Installation

The Docker-based installation process downloads the enterprise image from the Solace Product Portal, loads it into your container environment, and launches it with the appropriate configuration for your deployment scenario. You can run Enterprise in development mode with an embedded broker for testing, or connect it to an external Solace broker for production deployments. For complete installation instructions, see [Installing Agent Mesh Enterprise](installation.md).

### Access Control

Role-based access control lets you define who can access which agents and features in your deployment. You create roles that represent job functions, assign permissions to those roles through scopes, and then assign roles to users. This three-tier model implements the principle of least privilege while simplifying administration. For guidance on planning and implementing RBAC, see [Setting Up RBAC](rbac-setup-guide.md).

### Single Sign-On

SSO integration connects Agent Mesh Enterprise with your organization's identity provider, whether you use Azure, Google, Auth0, Okta, Keycloak, or another OAuth2-compliant system. The configuration process involves creating YAML files that define the authentication service and provider settings, then launching the container with the appropriate environment variables. For step-by-step configuration instructions, see [Enabling SSO](single-sign-on.md).

## What's Next

After you complete the initial setup, you can begin developing agents and gateways using the same patterns and tools available in the Community edition. The Enterprise features operate transparently—your agents and tools work the same way, but with the added security, governance, and observability that production environments demand. 