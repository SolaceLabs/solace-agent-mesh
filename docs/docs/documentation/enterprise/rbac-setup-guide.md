---
title: Role-Based Access Control (RBAC)
sidebar_position: 10
---

:::warning Security Notice
**Agent Mesh Enterprise now uses secure-by-default authorization.** If you do not configure an authorization service, the system will **deny all access** by default. You must explicitly configure RBAC or another authorization type to grant access to users.
:::

This guide walks you through configuring Role-Based Access Control (RBAC) for Agent Mesh Enterprise. You will learn how to control access to Agent Mesh Enterprise features and resources based on user roles and permissions. This guide covers RBAC configuration for both Docker and Helm deployments.


## Overview

Before you configure RBAC, you need to understand how the system works. Agent Mesh Enterprise uses a three-tier authorization model that separates identity, roles, and permissions.

### RBAC Concepts

RBAC in Agent Mesh Enterprise uses three connected concepts:

**Users** represent identities in your system. Each user has a unique identifier, typically an email address. When a user attempts to access a feature or resource, Agent Mesh Enterprise checks their assigned roles to determine what they can do.

**Roles** are collections of permissions that you assign to users. Instead of granting permissions directly to individual users, you create roles that represent job functions or responsibilities. For example, you might create a "data_analyst" role for users who need to work with data tools and artifacts. This approach simplifies administration because you can modify a role's permissions once and affect all users assigned to that role.

**Scopes** are the actual permissions that grant access to specific features or resources. Each scope follows a pattern that identifies what it controls. For example, the scope `tool:data:read` grants permission to read data tools, while `artifact:create` allows creating artifacts. Scopes use wildcards to grant broader permissions. For example, the scope `tool:data:*` grants all permissions for data tools.

### How Authorization Works

When a user attempts an action in Agent Mesh Enterprise, the system follows this authorization flow:

1. The system identifies the user based on their authentication credentials
2. It retrieves all roles assigned to that user
3. For each role, it collects all associated scopes (permissions)
4. It checks if any of the user's scopes match the permission required for the requested action
5. If a matching scope exists, the system allows the action; otherwise, it denies access

This model implements the principle of least privilege: users receive only the permissions they need to perform their job functions.


### Authorization Types

Agent Mesh Enterprise supports multiple authorization types, each suited for different use cases:

**`deny_all` (Default)** - The secure default that denies all access. This type is automatically used when:
- No `authorization_service` configuration block is present
- The `authorization_service` block is empty
- The `type` field is explicitly set to `deny_all`

When this type is active, all user requests are denied and logged with WARNING messages. This ensures maximum security by default.

**`default_rbac`** - Role-Based Access Control using configuration files. This type is the recommended type for production deployments where you need fine-grained control over user permissions. It requires both role definitions and user assignments files.

**`custom`** - Custom authorization service implementation. Use this when you need to integrate with external authorization systems or implement custom authorization logic.

**`none`** - Disables authorization entirely, granting wildcard `*` scope to all users. This type must be explicitly configured and should **only be used in development environments**. The system logs prominent security warnings when this type is active.

:::danger Development Only
The `type: none` authorization configuration grants full access to all users and should **never** be used in production environments. It is intended only for local development and testing.
:::

## Planning Your RBAC Configuration

Before you create configuration files, you should plan your RBAC structure. This planning phase helps you design a system that meets your organization's needs while remaining maintainable.

### Identifying User Types

Start by identifying the different types of users in your organization. Consider their job functions and what they need to accomplish with Agent Mesh Enterprise. Common user types include:

Administrators need full access to all features and resources. They manage the system, configure settings, and troubleshoot issues. You typically assign these users a role with wildcard permissions.

Operators perform day-to-day tasks such as running tools, creating artifacts, and monitoring system activity. They need broad access to operational features but not administrative capabilities.

Analysts work with data and reports. They need access to data tools, artifact creation, and monitoring capabilities, but they do not need access to system configuration or advanced tools.

Viewers need read-only access to monitor system activity and view artifacts. They cannot create, modify, or delete resources.

### Designing Roles

Once you identify user types, design roles that match their needs. Each role should represent a specific job function and include only the scopes necessary for that function.

Consider creating a role hierarchy where some roles inherit permissions from others. For example, an "operator" role might inherit all permissions from a "viewer" role and add additional capabilities. This approach reduces duplication and makes your configuration easier to maintain.

### Mapping Scopes to Features

Understanding available scopes helps you design effective roles. Agent Mesh Enterprise uses a hierarchical scope naming convention. This section describes the different types of scopes and how they control access to specific features.

#### Tool Scopes

Tool scopes control access to tools and follow the pattern `tool:<category>:<action>`. The `<category>` identifies the type of tool, and the `<action>` specifies what operation is permitted (e.g., `read`, `execute`, `create`, `delete`).

Common tool scopes include:
- `tool:basic:read` - Permission to read/view basic tools
- `tool:basic:*` - All permissions for basic tools
- `tool:data:*` - All permissions for data-related tools
- `tool:advanced:read` - Permission to read advanced tools

**Custom Tool Scopes with `required_scope`:**

When you create a custom tool in Agent Mesh Enterprise, you can specify a `required_scope` field in the tool's configuration that defines what permission a user needs to access that tool. This allows you to create fine-grained access controls for specific tools.

For example, if you create a custom database query tool in your agent configuration, you would set the `required_scope` in the tool's component definition:

```yaml
# In your agent flow configuration (e.g., flows_config.yaml)
components:
  - component_name: query_customer_database
    component_module: my_custom_tools
    component_config:
      tool_name: "customer_database_query"
      description: "Query the customer database for analysis"
      required_scope: "tool:database:query"  # RBAC scope required to use this tool
      # ... other tool configuration ...
      database_connection:
        host: "db.example.com"
        port: 5432
```

Alternatively, if you're defining tools in a tool registry or catalog file:

```yaml
# In a tool catalog/registry configuration
tools:
  - name: "customer_database_query"
    description: "Query the customer database for analysis"
    required_scope: "tool:database:query"  # RBAC scope required to use this tool
    implementation: "my_custom_tools.DatabaseQueryTool"
    parameters:
      database_connection:
        host: "db.example.com"
        port: 5432
```

Then, in your role configuration, you would grant access to users who need this tool:

```yaml
# In role-to-scope-definitions.yaml
roles:
  data_analyst:
    description: "Analyst with database access"
    scopes:
      - "tool:database:query"  # Grants access to the customer_database_query tool
      - "artifact:read"
      - "artifact:create"
```

Only users with the `data_analyst` role (or any role containing the `tool:database:query` scope) can access the `customer_database_query` tool. Users without this scope receive an authorization error when attempting to use the tool.

You can use wildcards in role scopes to grant broader access:

```yaml
roles:
  database_admin:
    description: "Database administrator with full database tool access"
    scopes:
      - "tool:database:*"  # Grants access to all tools with required_scope starting with "tool:database:"
```

This role would have access to any tool with `required_scope` set to `tool:database:query`, `tool:database:admin`, `tool:database:backup`, etc.

#### Agent Scopes

Agent scopes control access to specific agents and follow the pattern `agent:<agent_name>:delegate`. These scopes allow you to control which users can interact with which agents in your Agent Mesh Enterprise deployment.

**How Agent Scopes Work:**

Unlike tools (which use an explicit `required_scopes` field), agent scopes are **automatically derived from the agent's `agent_name` configuration field**. When you define an agent, the system automatically enforces the scope `agent:<agent_name>:delegate` for access control.

For example, if you configure an agent like this:

```yaml
# In your agent configuration file (e.g., customer_support_agent.yaml)
apps:
  - name: customer_support_app
    app_config:
      agent_name: "customer_support_agent"  # This determines the required scope
      display_name: "Customer Support"
      instruction: |
        You are a customer support agent...
      # ... other agent configuration ...
```

The system automatically requires users to have the scope `agent:customer_support_agent:delegate` to interact with this agent. You don't need to explicitly configure this scope on the agent itself—it's derived from the `agent_name` field.

When a user attempts to send a message to an agent or invoke an agent's capabilities, the system checks whether the user has the appropriate agent scope. The `<agent_name>` in the scope must match the name of the agent being accessed.

**Example: Controlling Access to Specific Agents**

Suppose you have three agents in your system:
- `customer_support_agent` - Handles customer inquiries
- `data_analysis_agent` - Performs data analytics
- `admin_agent` - Performs administrative tasks

You can create roles that grant access to specific agents:

```yaml
# In role-to-scope-definitions.yaml
roles:
  customer_support_rep:
    description: "Customer support representative"
    scopes:
      - "agent:customer_support_agent:delegate"  # Can only access customer support agent
      - "artifact:read"

  data_analyst:
    description: "Data analyst"
    scopes:
      - "agent:data_analysis_agent:delegate"  # Can only access data analysis agent
      - "tool:data:*"
      - "artifact:read"
      - "artifact:create"

  system_admin:
    description: "System administrator"
    scopes:
      - "agent:*:delegate"  # Can access all agents (wildcard)
      - "*"  # Full access to all features
```

With this configuration:
- A user with the `customer_support_rep` role can only interact with `customer_support_agent`
- A user with the `data_analyst` role can only interact with `data_analysis_agent`
- A user with the `system_admin` role can interact with any agent

**Using Wildcards for Agent Access:**

You can use wildcards to grant access to multiple agents:

```yaml
roles:
  agent_operator:
    description: "Can access all non-admin agents"
    scopes:
      - "agent:customer_*:delegate"  # Access to all agents starting with "customer_"
      - "agent:data_*:delegate"      # Access to all agents starting with "data_"
      - "artifact:read"
```

This role would grant access to agents like `customer_support_agent`, `customer_feedback_agent`, `data_analysis_agent`, `data_processing_agent`, etc., but not `admin_agent`.

#### Artifact Scopes

Artifact scopes control access to files and data created by agents during task execution, using the pattern `artifact:<action>`:

- `artifact:read` - Permission to view and download artifacts
- `artifact:create` - Permission to create new artifacts
- `artifact:delete` - Permission to delete artifacts
- `artifact:update` - Permission to modify existing artifacts
- `artifact:*` - All artifact permissions

Example role configuration:
```yaml
roles:
  data_analyst:
    description: "Data analyst with artifact access"
    scopes:
      - "artifact:read"
      - "artifact:create"
      - "tool:data:*"
```

#### Monitoring Scopes

Monitoring scopes control access to system monitoring features and follow the pattern `monitor/namespace/<namespace>:a2a_messages:subscribe`. These scopes allow users to observe message traffic in specific namespaces.

Examples:
- `monitor/namespace/production:a2a_messages:subscribe` - Monitor the "production" namespace
- `monitor/namespace/*:a2a_messages:subscribe` - Monitor all namespaces (wildcard)

#### The Wildcard Scope

The wildcard scope `*` grants all permissions and should only be used for administrator roles. This scope provides unrestricted access to all features, tools, agents, and resources in the system.

## Setting Up RBAC in Docker

Now that you understand RBAC concepts and have planned your configuration, you can set up RBAC in your Docker environment. This process involves creating configuration files, setting up the Docker container, and verifying that everything works correctly.

### Prerequisites

Before you begin, ensure you have:

- Docker installed and running on your system
- The Agent Mesh Enterprise Docker image (`solace-agent-mesh-enterprise`)
- A text editor for creating configuration files
- Basic familiarity with YAML file format

### Creating the Configuration Directory Structure

You need to create a directory structure on your host system to store RBAC configuration files. The Docker container will mount this directory to access your configurations.

Create the directory structure as follows (note that `sam-enterprise` is just an example directory name - you can use any name you prefer):

```bash
mkdir -p sam-enterprise/config/auth
```

This command creates a `sam-enterprise` directory with a nested `config/auth` subdirectory. The `auth` subdirectory will contain your RBAC configuration files.

### Defining Roles and Permissions

Create a file named `role-to-scope-definitions.yaml` in the `sam-enterprise/config/auth` directory. 
This file defines all roles in your system and the scopes (permissions) associated with each role.

Here is an example configuration that defines three roles:

```yaml
# role-to-scope-definitions.yaml
roles:
  enterprise_admin:
    description: "Full access for enterprise administrators"
    scopes:
      - "*"  # Wildcard grants all permissions
    
  data_analyst:
    description: "Data analysis and visualization specialist"
    scopes:
      - "tool:data:*"  # All data tools
      - "artifact:read"
      - "artifact:create"
      - "monitor/namespace/*:a2a_messages:subscribe"  # Can monitor any namespace
    
  standard_user:
    description: "Standard user with basic access"
    scopes:
      - "artifact:read"
      - "tool:basic:read"
      - "tool:basic:search"
```

This configuration creates three distinct roles:

The `enterprise_admin` role receives the wildcard scope `*`, which grants all permissions in the system. You should assign this role only to trusted administrators who need complete control over Agent Mesh Enterprise.

The `data_analyst` role receives permissions tailored for data analysis work. The scope `tool:data:*` grants all permissions for data-related tools (read, write, execute). The `artifact:read` and `artifact:create` scopes allow analysts to view existing artifacts and create new ones. The monitoring scope `monitor/namespace/*:a2a_messages:subscribe` enables analysts to observe message traffic across all namespaces, which helps them understand data flows.

The `standard_user` role provides minimal permissions for basic operations. Users with this role can read artifacts and perform basic tool operations but cannot create new artifacts or access advanced features.

### Assigning Users to Roles

Create a file named `user-to-role-assignments.yaml` in the `sam-enterprise/config/auth` directory. This file maps user identities to roles.

Here is an example configuration:

```yaml
# user-to-role-assignments.yaml
users:
  admin@example.com:
    roles: ["enterprise_admin"]
    description: "Enterprise Administrator Account"
    
  data.analyst@example.com:
    roles: ["data_analyst"]
    description: "Senior Data Analyst"
    
  user1@example.com:
    roles: ["standard_user"]
    description: "Standard Enterprise User"
```

Each entry in this file maps a user identity (typically an email address) to one or more roles. The user identity must match exactly what your authentication system provides because Agent Mesh Enterprise performs case-sensitive matching.

You can assign multiple roles to a single user by listing them in the `roles` array. When a user has multiple roles, they receive the combined permissions from all assigned roles. For example, if you assign both `data_analyst` and `standard_user` roles to a user, they receive all scopes from both roles.

The `description` field is optional but recommended. It helps you document the purpose of each user account, which is valuable when reviewing or auditing your RBAC configuration.

### Creating the Enterprise Configuration

Create a file named `enterprise_config.yaml` in the `sam-enterprise/config` directory (not in the `auth` subdirectory). This file tells Agent Mesh Enterprise where to find your RBAC configuration files and how to use them.

:::tip Optional Configuration
The `authorization_service` configuration block is **optional**. If omitted, the system defaults to `deny_all` (secure by default) and logs a WARNING message. You must explicitly configure authorization to grant access to users.
:::

```yaml
# enterprise_config.yaml
authorization_service:
  type: "default_rbac"
  role_to_scope_definitions_path: "config/auth/role-to-scope-definitions.yaml"
  user_to_role_assignments_path: "config/auth/user-to-role-assignments.yaml"

namespace: "enterprise_prod"
```

The `authorization_service` section configures the RBAC system. The `type` field specifies `default_rbac`, which tells Agent Mesh Enterprise to use the file-based RBAC system. The two path fields point to your RBAC configuration files—these paths are relative to the container's working directory, not your host system.

**Important:** When using `type: default_rbac`, `role_to_scope_definitions_path` is **required**. The system fails to start if these files are missing or invalid.

The `namespace` field configures the Agent Mesh Enterprise instance. The namespace isolates this instance from others.

#### Alternative: Development Mode (Permissive)

For local development and testing only, you can disable authorization:

```yaml
# enterprise_config.yaml - DEVELOPMENT ONLY
authorization_service:
  type: "none"  # Grants full access to all users

namespace: "enterprise_dev"
```

:::danger Security Warning
Using `type: none` disables all authorization checks and grants wildcard `*` scope to every user. This configuration should **never** be used in production environments. The system logs prominent security warnings when this type is active.
:::

#### Default Behavior (No Configuration)

If you omit the `authorization_service` block entirely, the system uses secure defaults:

```yaml
# enterprise_config.yaml - Secure by default
# No authorization_service block = deny_all

namespace: "enterprise_prod"
```

When no authorization configuration is present, the system:
1. Logs a WARNING message about missing configuration
2. Defaults to `deny_all` authorization type
3. Denies all user requests with WARNING logs
4. Requires explicit RBAC configuration to grant access

### Running the Docker Container

Now you can start the Docker container with your RBAC configuration. 
Navigate to your `sam-enterprise` directory and run:

```bash
cd sam-enterprise

docker run -d \
  --name sam-enterprise \
  -p 8001:8000 \
  -v "$(pwd):/app" \
  -e SAM_AUTHORIZATION_CONFIG="/app/config/enterprise_config.yaml" \
  -e NAMESPACE=enterprise_prod \
  -e ... list here all other necessary env vars ...
  solace-agent-mesh-enterprise:<tagname>
```

### Verifying Your Configuration

After starting the container, you should verify that RBAC is working correctly. Follow these steps:

1. Open your web browser and navigate to `http://localhost:8001`
2. Log in using one of the user identities defined in your `user-to-role-assignments.yaml` file
3. Attempt to access features that the user should have permission to use
4. Attempt to access features that the user should not have permission to use

If RBAC is configured correctly, the user can access permitted features and receives authorization errors when attempting to access restricted features.

You can also check the container logs to verify that Agent Mesh Enterprise loaded your configuration files:

```bash
docker logs sam-enterprise
```

Look for log messages that indicate successful configuration loading. You should see messages similar to:

```
INFO:solace_ai_connector:[ConfigurableRbacAuthSvc] Successfully loaded role-to-scope definitions from: /app/config/auth/role-to-scope-definitions.yaml
DEBUG:solace_ai_connector:[ConfigurableRbacAuthSvc] Role 'enterprise_admin' loaded with 1 direct scopes, 1 resolved scopes.
DEBUG:solace_ai_connector:[ConfigurableRbacAuthSvc] Role 'data_analyst' loaded with 4 direct scopes, 4 resolved scopes.
DEBUG:solace_ai_connector:[ConfigurableRbacAuthSvc] Role 'standard_user' loaded with 3 direct scopes, 3 resolved scopes.
```

These messages confirm that Agent Mesh Enterprise found and parsed your configuration files correctly.

## Setting Up RBAC with Helm

For production deployments, Solace recommends using Helm to deploy Agent Mesh Enterprise on Kubernetes. The RBAC concepts (roles, scopes, and user assignments) are identical to Docker deployments, but the configuration is managed through Kubernetes ConfigMaps.

For complete instructions on configuring RBAC in Helm deployments, including ConfigMap setup, role definitions, and user assignments, please refer to the [Solace Agent Mesh Helm Quickstart Guide - RBAC section](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs/#role-based-access-control-rbac).

## Understanding Configuration Files

Now that you have a working RBAC configuration, you should understand the full structure and capabilities of each configuration file. This knowledge helps you customize the configuration to meet your specific needs.

### Role-to-Scope Definitions Structure

The `role-to-scope-definitions.yaml` file supports several features beyond the basic examples shown earlier. Here is the complete structure:

```yaml
roles:
  role_name:
    description: "Role description"
    scopes:
      - "scope1"
      - "scope2"
    inherits:  # Optional - inherit scopes from other roles
      - "parent_role1"
      - "parent_role2"
```

The `inherits` field allows you to create role hierarchies. When a role inherits from another role, it receives all scopes from the parent role in addition to its own scopes. This feature reduces duplication and makes your configuration easier to maintain.

For example, you might create a base "viewer" role with read-only permissions, then create an "operator" role that inherits from "viewer" and adds write permissions:

```yaml
roles:
  viewer:
    description: "Read-only access"
    scopes:
      - "tool:basic:read"
      - "artifact:read"
  
  operator:
    description: "Operational access"
    inherits:
      - "viewer"
    scopes:
      - "tool:basic:*"
      - "artifact:create"
```

In this example, the "operator" role receives all scopes from "viewer" (`tool:basic:read` and `artifact:read`) plus its own scopes (`tool:basic:*` and `artifact:create`). Note that `tool:basic:*` includes `tool:basic:read`, so there is some overlap. Agent Mesh Enterprise handles this correctly by deduplicating scopes.

### User-to-Role Assignments Structure

The `user-to-role-assignments.yaml` file supports both global user identities and gateway-specific identities. Here is the complete structure:

```yaml
users:
  user_identity:
    roles: ["role1", "role2"]
    description: "User description"

# Optional: Gateway-specific user identities
gateway_specific_identities:
  gateway_id:user_identity:
    roles: ["role1", "role2"]
    description: "User with specific roles on this gateway"
```

The `users` section defines global user identities that apply across all gateways. Most configurations only need this section.

The `gateway_specific_identities` section allows you to assign different roles to the same user identity on different gateways. This feature is useful in multi-gateway deployments where you want to grant different permissions based on which gateway a user accesses. The key format is `gateway_id:user_identity`, where `gateway_id` matches the gateway ID in your configuration. The default gateway ID is `_default_enterprise_gateway`.

### Enterprise Configuration Structure

The enterprise configuration file supports multiple authorization service types. Here is the complete structure for the file-based RBAC system:

```yaml
authorization_service:
  type: "default_rbac"
  role_to_scope_definitions_path: "path/to/role-to-scope-definitions.yaml"
  user_to_role_assignments_path: "path/to/user-to-role-assignments.yaml"
```

## Advanced Configuration Options

After you have a basic RBAC configuration working, you might want to explore advanced options that provide additional flexibility and integration capabilities.

### Production-Ready Role Configuration

A production environment typically needs more sophisticated role definitions than the basic examples. Here is a comprehensive configuration that demonstrates best practices:

```yaml
# role-to-scope-definitions.yaml
roles:
  admin:
    description: "Administrator with full access"
    scopes:
      - "*"
  
  operator:
    description: "System operator"
    scopes:
      - "tool:basic:*"
      - "tool:advanced:read"
      - "artifact:read"
      - "artifact:create"
      - "monitor/namespace/*:a2a_messages:subscribe"
  
  viewer:
    description: "Read-only access"
    scopes:
      - "tool:basic:read"
      - "artifact:read"
      - "monitor/namespace/*:a2a_messages:subscribe"
```

```yaml
# user-to-role-assignments.yaml
users:
  admin@company.com:
    roles: ["admin"]
    description: "System Administrator"
  
  operator@company.com:
    roles: ["operator"]
    description: "System Operator"
  
  viewer@company.com:
    roles: ["viewer"]
    description: "Read-only User"
```

This configuration creates a clear hierarchy of access levels. The admin role has unrestricted access, the operator role can perform most operational tasks, and the viewer role provides read-only access for monitoring and auditing purposes.

### Integrating with Microsoft Graph

For enterprise environments that use Microsoft Entra ID (formerly Azure AD) for user management, you can integrate Agent Mesh Enterprise with Microsoft Graph. This integration allows you to manage user role assignments through Microsoft Graph instead of maintaining a separate YAML file.

To configure Microsoft Graph integration, modify your `enterprise_config.yaml`:

```yaml
# enterprise_config.yaml
authorization_service:
  type: "default_rbac"
  role_to_scope_definitions_path: "config/auth/role-to-scope-definitions.yaml"
  user_to_role_provider: "ms_graph"
  
  ms_graph_config:
    ms_graph_tenant_id: ${MS_GRAPH_TENANT_ID}
    ms_graph_client_id: ${MS_GRAPH_CLIENT_ID}
    ms_graph_client_secret: ${MS_GRAPH_CLIENT_SECRET}
```

This configuration tells Agent Mesh Enterprise to retrieve user role assignments from Microsoft Graph instead of reading them from a YAML file. The `${...}` syntax indicates that these values come from environment variables, which keeps sensitive credentials out of your configuration files.

When you use Microsoft Graph integration, you still define roles in the `role-to-scope-definitions.yaml` file, but you manage user-to-role assignments through Microsoft Graph groups or attributes.

Run the Docker container with the Microsoft Graph credentials:

```bash
docker run -d \
  --name sam-enterprise \
  -p 8000:8001 \
  -v "$(pwd):/app" \
  -e MS_GRAPH_TENANT_ID=your-tenant-id \
  -e MS_GRAPH_CLIENT_ID=your-client-id \
  -e MS_GRAPH_CLIENT_SECRET=your-client-secret \
  -e NAMESPACE=enterprise_prod \
  solace-agent-mesh-enterprise:<tag>
```

The Microsoft Graph integration requires that you configure an application registration in Microsoft Entra ID with appropriate permissions to read user and group information. The tenant ID identifies your Microsoft Entra ID tenant, the client ID identifies your application registration, and the client secret authenticates your application.

## Best Practices

Following best practices helps you create a secure, maintainable RBAC configuration that scales with your organization's needs.

### Security Recommendations

You should implement these security practices to protect your Agent Mesh Enterprise deployment:

Apply the principle of least privilege by assigning users only the minimum permissions necessary for their tasks. Start with restrictive permissions and add more as needed, rather than starting with broad permissions and removing them later. This approach reduces the risk of unauthorized access.

Conduct regular audits of your role assignments and permissions. Review who has access to what features and verify that access levels remain appropriate as job responsibilities change. Remove access for users who no longer need it.

Protect your RBAC configuration files with appropriate file permissions on your host system. These files control access to your entire Agent Mesh Enterprise deployment, so you should restrict read and write access to authorized administrators only.

Store sensitive information like Microsoft Graph credentials as environment variables rather than hardcoding them in configuration files. Environment variables provide better security because they do not appear in version control systems or configuration backups.

Never use development configurations in production environments. Development configurations often include test accounts with elevated permissions or relaxed security settings that are inappropriate for production use.

### Role Design Principles

Well-designed roles make your RBAC configuration easier to understand and maintain:

Create roles that align with job functions in your organization. Each role should represent a specific type of work that users perform. This alignment makes it easier to determine which role to assign to new users.

Use role inheritance to build a logical hierarchy. If one role needs all the permissions of another role plus additional permissions, use inheritance rather than duplicating scopes. This approach reduces configuration size and makes updates easier.

Use clear, descriptive names for roles that indicate their purpose. Names like "data_analyst" or "system_operator" are more meaningful than generic names like "role1" or "user_type_a".

Document the purpose and scope of each role in the description field. This documentation helps other administrators understand your RBAC configuration and makes it easier to maintain over time.

Minimize wildcard usage in scope definitions. While wildcards like `*` or `tool:*:*` are convenient, they grant broad permissions that might include features you did not intend to allow. Use specific scopes whenever possible, and reserve wildcards for administrator roles.

### Docker-Specific Recommendations

When you run Agent Mesh Enterprise in Docker, follow these recommendations:

Use Docker volumes for persistent configuration storage. The volume mount approach shown in this guide ensures that your configuration persists even if you remove and recreate the container.

Create separate configuration files for different environments (development, staging, production). This separation prevents accidental use of inappropriate configurations and makes it easier to maintain environment-specific settings.

Implement health checks to verify that RBAC is functioning correctly. You can add a health check to your Docker run command that periodically tests whether the container is responding correctly.

Regularly backup your RBAC configuration files. Store backups in a secure location separate from your Docker host. If you lose your configuration files, you lose control over who can access your Agent Mesh Enterprise deployment.

Follow Docker security best practices such as running containers as non-root users and using read-only filesystems where possible. These practices reduce the impact of potential security vulnerabilities.

## Troubleshooting

When you encounter issues with your RBAC configuration, systematic troubleshooting helps you identify and resolve problems quickly.

### Authorization Denied for Valid User

If a user cannot access features they should have permission to use, you might see authorization denied messages in the logs or user interface.

To resolve this issue, first verify that the user identity matches exactly what appears in your `user-to-role-assignments.yaml` file. Agent Mesh Enterprise performs case-sensitive matching, so `user@example.com` and `User@example.com` are different identities.

Next, check that the role assigned to the user has the necessary scopes. Review the `role-to-scope-definitions.yaml` file and verify that the role includes scopes for the features the user is trying to access.

Ensure that your configuration files are correctly mounted in the Docker container. You can verify the mount by running:

```bash
docker exec -it sam-enterprise ls -la /app/config/auth
```

This command lists the files in the mounted directory. You should see your `role-to-scope-definitions.yaml` and `user-to-role-assignments.yaml` files.

Check the container logs for authorization service errors:

```bash
docker logs sam-enterprise
```

Look for messages with the `[ConfigurableRbacAuthSvc]` prefix. These messages indicate whether Agent Mesh Enterprise successfully loaded your configuration files and how it resolved roles and scopes. You should see messages like:

```
INFO:solace_ai_connector:[ConfigurableRbacAuthSvc] Successfully loaded role-to-scope definitions from: /app/config/auth/role-to-scope-definitions.yaml
DEBUG:solace_ai_connector:[ConfigurableRbacAuthSvc] Role 'enterprise_admin' loaded with 1 direct scopes, 1 resolved scopes.
DEBUG:solace_ai_connector:[ConfigurableRbacAuthSvc] Role 'data_analyst' loaded with 4 direct scopes, 4 resolved scopes.
DEBUG:solace_ai_connector:[ConfigurableRbacAuthSvc] Role 'standard_user' loaded with 1 direct scopes, 1 resolved scopes.
```

### Configuration Files Not Found

If you see error messages about missing configuration files or the system uses default authorization behavior, the container cannot find your configuration files.

Check that the volume mount in your Docker run command is correct. The mount should map your host directory to `/app` in the container. Verify that you are using the correct path on your host system.

Ensure that file permissions allow the container user to read the files. On Linux systems, you might need to adjust file permissions:

```bash
chmod 644 sam-enterprise/config/auth/*.yaml
```

Check for typos in file names or paths. The file names are case-sensitive, and even small typos prevent Agent Mesh Enterprise from finding your configuration files.

### Microsoft Graph Integration Not Working

If users cannot authenticate when you use Microsoft Graph integration, or you see error messages related to Microsoft Graph in the logs, several issues might be causing the problem.

Verify that your Microsoft Graph credentials are correct. Double-check the tenant ID, client ID, and client secret against your Microsoft Entra ID application registration.

Check that environment variables are properly set in your Docker run command. You can verify environment variables inside the container:

```bash
docker exec -it sam-enterprise env | grep MS_GRAPH
```

Ensure that your Microsoft Graph application has the necessary permissions. The application needs permissions to read user and group information from Microsoft Entra ID.

Check network connectivity from the container to Microsoft Graph endpoints. The container must be able to reach `graph.microsoft.com` over HTTPS. Firewall rules or network policies might block this connectivity.

### Debugging Authorization Issues

When you need to investigate authorization problems in detail, follow these debugging steps:

Enable debug logging by adding a log level setting to your `enterprise_config.yaml`:

```yaml
# Add to your enterprise_config.yaml
log_level: "DEBUG"
```

Debug logging provides detailed information about authorization decisions, including which scopes the system checked and why it allowed or denied access.

Check the container logs for detailed information:

```bash
docker logs sam-enterprise
```

Look for log messages with the `[EnterpriseConfigResolverImpl]` or `[ConfigurableRbacAuthSvc]` prefixes. These messages show how Agent Mesh Enterprise loaded and processed your configuration.

Temporarily assign the user to an administrator role to verify whether the issue is permission-related. If the user can access features when assigned to an admin role, the problem is with the scopes assigned to their original role.

Inspect the mounted configuration files inside the container to verify that they contain the expected content:

```bash
docker exec -it sam-enterprise cat /app/config/auth/role-to-scope-definitions.yaml
docker exec -it sam-enterprise cat /app/config/auth/user-to-role-assignments.yaml
```

This verification ensures that the files inside the container match your host files and that the volume mount is working correctly.

### Getting Help

If you continue to experience issues after following these troubleshooting steps, you can get additional help:

Check the Agent Mesh Enterprise documentation for updates or additional information about RBAC configuration.

Review the container logs for specific error messages. Error messages often include details about what went wrong and how to fix it.

Contact Solace support with details of your configuration and the issues you are experiencing. Include relevant log excerpts and describe the steps you have already taken to troubleshoot the problem.

## Conclusion

Setting up Role-Based Access Control in your Agent Mesh Enterprise Docker installation provides enhanced security and granular access control. This guide has walked you through understanding RBAC concepts, planning your configuration, creating configuration files, and troubleshooting common issues.

You now have the knowledge to configure RBAC to meet your organization's specific requirements while maintaining a secure and manageable environment. Remember to regularly review and update your RBAC configuration as your organization's needs evolve, and always follow security best practices when managing access control.
