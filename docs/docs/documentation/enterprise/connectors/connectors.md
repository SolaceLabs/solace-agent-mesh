---
title: Connectors
sidebar_position: 10
---

# Connectors

Connectors allow your agents to access external data sources and services. You configure each connector with credentials and connection details for a specific system. Agents use connectors to retrieve information, execute queries, and interact with external platforms through natural language conversations.

## Connector Types

Agent Mesh Enterprise provides multiple connector types. Each type integrates with different external systems.

### Knowledge Base Connectors

Knowledge Base connectors allow agents to retrieve context from enterprise documentation stored in cloud-based knowledge repositories. The connectors retrieve information from knowledge bases that can contain both unstructured documents and structured data, returning relevant results to ground agent responses in organizational knowledge. For detailed information about creating and configuring Knowledge Base connectors, see [Knowledge Base Connectors](knowledgebase-connectors.md).

### MCP Connectors

Model Context Protocol (MCP) connectors allow agents to communicate with MCP-compliant servers. The connectors provide access to external tools and data sources that implement the MCP standard. For detailed information about creating and configuring MCP connectors, see [MCP Connectors](mcp-connectors.md).

### OpenAPI Connectors

OpenAPI connectors allow agents to interact with REST APIs that use OpenAPI specifications. The connectors automatically generate callable tools from API endpoints. Agents use these tools to make authenticated HTTP requests to external services. For detailed information about creating and configuring OpenAPI connectors, see [OpenAPI Connectors](openapi-connectors.md).

### SQL Connectors

SQL connectors allow agents to query relational databases using natural language. The connectors convert user questions into SQL queries and execute them against MySQL, PostgreSQL, or MariaDB databases. For detailed information about creating and configuring SQL connectors, see [SQL Connectors](sql-connectors.md).

## Creating Connectors

You create connectors through the Connectors section of the Agent Mesh Enterprise web interface. Navigate to the Connectors page and click the Create Connector button to begin the creation process. The creation process varies depending on the connector type. All connectors require a unique name and connection credentials appropriate for the target system.

Once you create a connector, it becomes available for assignment to any agent in your deployment. This reusability means you can connect multiple agents to the same external system without duplicating connection configuration.

## Shared Credential Model

All connector types in Agent Mesh Enterprise implement a shared credential model. When you create a connector, you configure it with specific credentials (database passwords, API keys, service account tokens, etc.). All agents assigned to that connector use the connector's credentials and have identical access permissions to the external system.

This design has important security implications. You cannot restrict one agent to read-only access and another agent to write access if they share the same connector. Security boundaries exist at the external system level (database permissions, API scopes, etc.), not at the connector assignment level within Agent Mesh Enterprise.

If different agents require different levels of access to the same system, you must create multiple connectors with different credentials, each having appropriate permissions configured in the external system.

## Assigning Connectors to Agents

You assign connectors to agents through Agent Builder. When creating or editing an agent, you select connectors from the available connectors list. You can assign multiple connectors to a single agent if it needs to access multiple external systems.

Changes to connector assignments take effect when you deploy or update the agent. If you remove a connector assignment from a deployed agent, that agent loses access to the connector's capabilities immediately after you deploy the update.

## Managing Connectors

### Editing Connectors

You can modify connector configurations at any time through the Connectors interface. The connector applies changes to connection details or credentials when you deploy a new agent. Existing agents continue to use the previous configuration until you redeploy them.

If agents are actively using a connector when you modify it, temporary failures may occur during the transition period. You should plan connector updates during maintenance windows or coordinate with agent users to minimize disruptions.

### Deleting Connectors

You can delete a connector only if no agents are assigned to it. The system enforces this restriction to prevent breaking deployed agents. If agents have the connector assigned, you must first undeploy those agents, remove the connector assignment from the agent configuration, and then delete the connector.

The deletion process removes the connector configuration from Agent Mesh Enterprise but does not affect the external system. Database users, API keys, and other external credentials remain in place, requiring separate cleanup if you no longer need them.

## Access Control

Connector operations require specific RBAC capabilities. The table below shows the capabilities and what they control:

| Capability              | Purpose                                                     |
| ----------------------- | ----------------------------------------------------------- |
| `sam:connectors:create` | Create new connectors in the Connectors section             |
| `sam:connectors:read`   | View connector configurations and list available connectors |
| `sam:connectors:update` | Modify connector configurations and credentials             |
| `sam:connectors:delete` | Remove connectors from the system                           |

For detailed information about configuring role-based access control and assigning capabilities to users, see [Setting Up RBAC](../rbac-setup-guide.md).
