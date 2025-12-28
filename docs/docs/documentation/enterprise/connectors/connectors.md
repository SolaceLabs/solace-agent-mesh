---
title: Connectors
sidebar_position: 10
---

# Connectors

Connectors link agents to external data sources and services. Each connector type provides access to different systems using configured credentials and connection details. Agents use connectors to retrieve information, execute queries, and interact with external platforms through natural language conversations.

## SQL Connectors

SQL connectors enable agents to query and analyze database information using natural language. These connectors convert user questions into SQL queries, execute them against configured databases, and return results in a conversational format. This capability makes database information accessible through agent interactions without requiring users to write SQL code.

### Supported Databases

SQL connectors support three database types:

- MySQL
- PostgreSQL
- MariaDB

Each database type follows the same configuration process but may have specific connection string requirements or authentication methods.

### Creating SQL Connectors

You create SQL connectors in the Connectors section of the Enterprise web interface. This process must be completed before you can assign connectors to agents.

Each SQL connector configuration includes the database type selection, connection details (host address, port number, and database name), and authentication credentials (username and password). The connection configuration establishes a persistent connection pool that agents use to execute queries. You should verify that the database server allows connections from the Agent Mesh deployment and that any required firewall rules permit access.

Once you create a connector, it becomes available for assignment to any agent in your deployment. This reusability means you can connect multiple agents to the same database without duplicating connection configuration. All agents assigned to a connector share the same database connection pool and credentials.

### Security Considerations

The framework implements a shared credential model that has significant implications for access control when planning your deployment architecture.

#### Shared Credential Architecture

The framework does not sandbox database access at the agent level. All agents assigned to a connector share the same database credentials and permissions. This design means that any agent with the connector can access all data the connector's credentials permit. Security boundaries exist at the database level, not between agents.

#### Implementing Database-Level Security

Database-level access control is your primary security mechanism. You should create database users with minimal necessary privileges, use database views or restricted schemas to limit what agents can access, and audit database queries to monitor what agents are accessing.

For example, if you have agents that should only read customer data and other agents that need full database access, you must create separate connectors with different database users. Each database user has appropriate permissions configured at the database level. You cannot restrict access by assigning the same connector to different agents because all agents sharing a connector have identical database permissions.

#### Natural Language Query Risks

The natural language to SQL conversion capability makes databases accessible through conversation, but this also means users can potentially request any data the connector can access. You should plan your database permissions accordingly and consider what information should be available through agent interactions.

Users might phrase questions in ways that expose data you intended to restrict, or they might discover table and column names through exploratory questions. Database views that present only approved data columns, user accounts with read-only permissions on specific tables, and query result size limits all help mitigate these risks.

#### Best Practices

Create separate connectors for different security boundaries. If agents require different levels of database access, configure multiple connectors with appropriately scoped database users rather than sharing a single connector across all agents.

Use read-only database accounts whenever possible. Many agent use cases only require reading data, and read-only permissions prevent accidental or malicious data modification.

Implement database views to present filtered data. Views can hide sensitive columns, join tables to present aggregated information, or implement row-level security logic at the database level.

Enable query logging and monitoring to track what agents access. Database audit logs help you detect suspicious query patterns or unauthorized data access attempts.

### Assigning Connectors to Agents

You assign connectors to agents through Agent Builder. When creating or editing an agent, you select connectors from a list during agent configuration. You can assign connectors before or after deployment, and changes to connector assignments take effect when you deploy or update the agent.

### Managing Connectors

Connector management operations require specific RBAC capabilities and follow particular patterns to prevent service disruptions.

#### Editing Connectors

You can modify connector configurations at any time. Changes to connection details or credentials take effect immediately for new database connections. Existing connections in the pool may continue using previous credentials until they expire and reconnect.

If agents are actively using a connector when you modify it, query failures may occur during the transition period. You should plan connector updates during maintenance windows or coordinate with agent users to minimize disruptions.

#### Testing Connections

The Connectors interface provides connection testing functionality that validates credentials and connectivity before you save the connector configuration. This testing helps identify configuration errors before agents attempt to use the connector.

#### Deleting Connectors

You can delete connectors, but the system enforces restrictions to prevent breaking deployed agents. If any agents are assigned to a connector, you must first remove the connector from those agents or undeploy them before deletion succeeds.

The deletion process removes the connector configuration but does not affect the database itself. Database users and permissions remain in place, requiring separate cleanup if you no longer need them.

### Troubleshooting

When connecting SAM to a PostgreSQL databases hosted on Supabase, you may encounter network errors like:

`{ "detail": "Invalid token", "error_type": "invalid_token" }`

This is because Supabase's direct connection endpoint uses IPv6, however most Kubernetes clusters are IPv4 by default.
The solution is to use the Session Pooler endpoint as it is IPv4 compatible.

## Access Control

Connector operations require specific RBAC capabilities. The table below shows the capabilities and what they control:

| Capability              | Purpose                                                     |
| ----------------------- | ----------------------------------------------------------- |
| `sam:connectors:create` | Create new connectors in the Connectors section             |
| `sam:connectors:read`   | View connector configurations and list available connectors |
| `sam:connectors:update` | Modify connector configurations and credentials             |
| `sam:connectors:delete` | Remove connectors from the system                           |

For detailed information about configuring role-based access control, see [Setting Up RBAC](../rbac-setup-guide.md).
