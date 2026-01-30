---
title: SQL Connectors
sidebar_position: 4
---

SQL connectors allow agents to query and analyze database information using natural language.

## Overview

SQL connectors convert user questions into SQL queries, execute them against your database, and return results in conversational format. This allows users to access database information through agent conversations without writing SQL code.

SQL connectors establish persistent connection pools to your database servers. Agents use these pooled connections to execute queries efficiently, with automatic connection management and reconnection handling.

The connector supports common relational database systems and handles the specifics of each database type automatically, including appropriate SQL dialect, connection protocols, and driver configurations.

## Supported Databases

Agent Mesh Enterprise supports three database types for SQL connectors:

- MySQL
- PostgreSQL
- MariaDB

Each database type uses the same configuration interface but requires connection parameters appropriate for that database system.

## Prerequisites

Before you create a SQL connector, ensure you have the following:

### Database Server Access

You need a running database server that Agent Mesh Enterprise can reach over the network. The database server must be configured to accept connections from the Agent Mesh deployment's network or IP address range.

### Database Credentials

You need a database username and password with appropriate permissions for the operations agents will perform. The specific permissions depend on your use case (read-only queries, data modification, schema access, etc.).

### Network Connectivity

Verify that network firewalls and security groups allow traffic from Agent Mesh Enterprise to your database server on the appropriate port. Default ports are 3306 for MySQL and MariaDB, and 5432 for PostgreSQL.

### Database Name

You need the specific database (schema) name within the database server that agents should access. This is the database you created or that your database administrator provisioned for agent access.

## Creating a SQL Connector

You create SQL connectors through the Connectors section in the Agent Mesh Enterprise web interface. Navigate to Connectors and click the Create Connector button to begin.

### Configuration Fields

The SQL connector creation form requires the following information:

**Connector Name**

A unique identifier for this connector within your Agent Mesh deployment. Choose a descriptive name that indicates the database purpose or contents, such as `Customer DB`, `Analytics DB`, or `Inventory DB`. This name appears in Agent Builder when you assign connectors to agents.

The connector name must be unique across all connectors in your deployment, regardless of type. You cannot change the name after creation, so choose carefully.

**Database Type**

Select the database system you are connecting to from the dropdown menu. The available options are MySQL, PostgreSQL, and MariaDB. This selection determines the appropriate driver and connection string format that Agent Mesh Enterprise uses.

If you select the wrong database type, connection tests will fail with errors about incompatible protocols or unsupported features.

**Host**

The hostname or IP address of your database server. This can be a DNS hostname like `db.example.com`, an IP address like `192.168.1.100`, or `localhost` if the database runs on the same machine as Agent Mesh Enterprise.

For cloud-hosted databases, use the hostname provided by your cloud provider. For Kubernetes deployments, you can use service names like `postgres-service.database.svc.cluster.local`.

**Port**

The port number where your database accepts connections. Default ports are:
- MySQL: `3306`
- PostgreSQL: `5432`
- MariaDB: `3306`

If your database administrator configured a custom port for security reasons or to avoid conflicts, enter that value instead of the default.

**Database Name**

The specific database within the database server that agents should access. This is the database name, not the server hostname. In PostgreSQL, this is the database name, not the schema name within a database. Agents will access the default schema (typically `public`) within the specified database.

For example, if your PostgreSQL server contains databases named `production`, `staging`, and `development`, you would enter the specific one agents should use, such as `production`.

**Username**

The database username that agents use to authenticate. This account determines what data agents can access and what operations they can perform through the database permission system.

You should create a dedicated database user for agent access rather than using administrative accounts or accounts shared with other applications. This allows you to control permissions precisely and audit agent database activity.

**Password**

The password for the database username. Agent Mesh Enterprise stores this credential securely in its configuration and uses it to establish database connections.

The password is encrypted at rest and transmitted securely to the database server. However, you should still follow password security best practices, such as using strong passwords and rotating them periodically.

### Connection Pooling

When you save the connector, Agent Mesh Enterprise creates a connection pool to your database. This pool maintains multiple persistent connections that agents reuse, improving performance by avoiding the overhead of creating new connections for each query.

The connection pool automatically manages connection lifecycle. It reconnects if connections drop due to network issues or database restarts, validates connections before use to ensure they are still active, and scales the number of connections based on agent demand.

Connection pool settings are automatically configured and cannot be customized. Agent Mesh Enterprise uses sensible defaults appropriate for most deployments.

## Database Permission Configuration

The database user you configure for the connector determines what agents can access and what operations they can perform. Configure database permissions before creating the connector to ensure appropriate access control.

### Read-Only Access

For most agent use cases, read-only database access provides sufficient capability while preventing accidental or malicious data modification.

**MySQL and MariaDB:**

```sql
CREATE USER 'agent_readonly'@'%' IDENTIFIED BY 'secure_password';
GRANT SELECT ON your_database.* TO 'agent_readonly'@'%';
FLUSH PRIVILEGES;
```

**PostgreSQL:**

```sql
CREATE USER agent_readonly WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE your_database TO agent_readonly;
GRANT USAGE ON SCHEMA public TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agent_readonly;
```

## After Creating the Connector

After you successfully create the connector, the system redirects you to the Connectors list where you can see your new connector. The connector is now available for assignment to agents.

To assign the connector to an agent, navigate to Agent Builder, create a new agent or edit an existing one, and select the connector from the available connectors list during agent configuration. You can assign the same connector to multiple agents.

For detailed information about creating and configuring agents, see [Agent Builder](../agent-builder.md).

## Security Considerations

SQL connectors implement a shared credential model where all agents assigned to a connector use the same database credentials and have identical access permissions.

If you assign a SQL connector to multiple agents, those agents can all access any data the connector's database user can reach. You cannot restrict one agent to the `customers` table and another agent to the `orders` table if they share the same connector. Security boundaries exist at the database permission level, not at the connector assignment level.

To implement different access levels for different agents, create multiple connectors with different database users, each having appropriate permissions configured at the database level.

Users can potentially request any data the connector can access by phrasing questions appropriately. Database views that present only approved columns and read-only permissions help mitigate these risks.

## Troubleshooting

### Database Connection Failures

If the database connection fails:

1. Verify network connectivity to the database host and port
2. Ensure firewall rules allow traffic from Agent Mesh Enterprise
3. Check that the username and password are correct
4. Confirm the database name exists
5. Verify the database type selection matches your server

### Supabase PostgreSQL Connectivity

When connecting to PostgreSQL databases hosted on Supabase, you may encounter network errors:

```
{ "detail": "Invalid token", "error_type": "invalid_token" }
```

This occurs because Supabase's direct connection endpoint uses IPv6 addressing, but most Kubernetes clusters default to IPv4 networking. Use the Session Pooler endpoint instead because it is IPv4 compatible.

In your Supabase project settings, navigate to Database then Connection Pooling to find the Session Pooler connection string. Use the host and port from this connection string when configuring your SQL connector. The database name, username, and password remain the same as your direct connection credentials.

### Query Performance Issues

If agents experience slow query responses:

1. Ensure frequently queried columns have appropriate indexes
2. Optimize database views if you use them for access control
3. Review query patterns in database logs to identify inefficient queries that agents generate
