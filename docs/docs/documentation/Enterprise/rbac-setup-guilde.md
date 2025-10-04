---
title: RBAC Setup Guide
sidebar_position: 10
---
This guide provides detailed instructions for configuring Role-Based Access Control (RBAC) in a Solace Agent Mesh (SAM) Enterprise Docker installation. RBAC allows you to control access to SAM Enterprise features and resources based on user roles and permissions.

## Table of Contents

- [Introduction to RBAC in SAM Enterprise](#introduction-to-rbac-in-sam-enterprise)
- [Docker Installation with RBAC](#docker-installation-with-rbac)
- [Configuration File Structure](#configuration-file-structure)
- [Example Configurations](#example-configurations)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Introduction to RBAC in SAM Enterprise

Role-Based Access Control (RBAC) in SAM Enterprise provides a flexible and secure way to manage user permissions. The RBAC system consists of:

- **Roles**: Collections of permissions (scopes) that define what actions can be performed
- **Scopes**: Specific permissions that grant access to features or resources
- **Users**: Identities that are assigned one or more roles

Key benefits of using RBAC in SAM Enterprise:

- **Granular Access Control**: Define precise permissions for different user types
- **Simplified Administration**: Manage permissions through roles rather than individual user assignments
- **Enhanced Security**: Implement the principle of least privilege
- **Audit Trail**: Clearly see which users have which permissions

## Docker Installation with RBAC

### Prerequisites

- Docker installed on your system
- SAM Enterprise Docker image (`solace-agent-mesh-enterprise`)
- Basic understanding of Docker volumes and configuration

### Step 1: Create RBAC Configuration Files

Create a directory on your host system to store the RBAC configuration files:

```bash
mkdir -p sam-enterprise/configs/auth
```

Create the following files in the `sam-enterprise/configs/auth` directory:

1. `role-to-scope-definitions.yaml`: Defines roles and their associated permissions
2. `user-to-role-assignments.yaml`: Maps users to roles

### Step 2: Configure Role Definitions

Create the `role-to-scope-definitions.yaml` file with your role definitions:

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

### Step 3: Configure User Assignments

Create the `user-to-role-assignments.yaml` file with your user assignments:

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

### Step 4: Create Enterprise Configuration

Create a file named `enterprise_config.yaml` in the `sam-enterprise/configs` directory:

```yaml
# enterprise_config.yaml
authorization_service:
  type: "default_rbac"
  role_to_scope_definitions_path: "configs/auth/role-to-scope-definitions.yaml"
  user_to_role_assignments_path: "configs/auth/user-to-role-assignments.yaml"

namespace: "enterprise_prod"
gateway_id: "enterprise_gateway"
```

### Step 5: Run the Docker Container with Mounted Configurations

Run the SAM Enterprise Docker container with the configuration files mounted:

```bash
cd sam-enterprise

docker run -d \
  --name sam-enterprise \
  -p 8000:8000 \
  -p 5002:5002 \
  -v "$(pwd)/configs:/app/configs" \
  -e SAM_AUTHORIZATION_CONFIG="/app/configs/enterprise_config.yaml" 
  -e NAMESPACE=enterprise_prod \
  -e WEBUI_GATEWAY_ID=enterprise_gateway \
  -e ... list here all other necessary env vars ...
  solace-agent-mesh-enterprise:<tagname> run configs
```

This command:
- Maps ports 8000 and 5002 to the host
- Mounts your local configuration directory to `/app/config` in the container
- Sets environment variables for the namespace and gateway ID
- Runs the container in detached mode

### Step 6: Verify RBAC Configuration

To verify that your RBAC configuration is working correctly:

1. Access the SAM Enterprise web interface at `http://localhost:5002`
2. Log in with one of the user identities defined in your `user-to-role-assignments.yaml` file
3. Confirm that the user has access to the appropriate features based on their assigned roles

## Configuration File Structure

### Role-to-Scope Definitions

The `role-to-scope-definitions.yaml` file defines roles and their associated permissions:

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

### User-to-Role Assignments

The `user-to-role-assignments.yaml` file maps users to roles:

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

### Enterprise Configuration

The enterprise configuration file references the RBAC configuration files:

```yaml
authorization_service:
  type: "default_rbac"
  role_to_scope_definitions_path: "path/to/role-to-scope-definitions.yaml"
  user_to_role_assignments_path: "path/to/user-to-role-assignments.yaml"
```

## Example Configurations

### Basic Production Configuration

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

### Using MS Graph for User Role Assignments

For enterprise environments that use Microsoft Graph for user management:

```yaml
# enterprise_config.yaml
authorization_service:
  type: "default_rbac"
  role_to_scope_definitions_path: "configs/auth/role-to-scope-definitions.yaml"
  user_to_role_provider: "ms_graph"
  
  ms_graph_config:
    ms_graph_tenant_id: ${MS_GRAPH_TENANT_ID}
    ms_graph_client_id: ${MS_GRAPH_CLIENT_ID}
    ms_graph_client_secret: ${MS_GRAPH_CLIENT_SECRET}
```

When using this configuration, set the environment variables in your Docker run command:

```bash
docker run -d \
  --name sam-enterprise \
  -p 8000:8000 \
  -p 5002:5002 \
  -v "$(pwd)/config:/app/configs" \
  -e MS_GRAPH_TENANT_ID=your-tenant-id \
  -e MS_GRAPH_CLIENT_ID=your-client-id \
  -e MS_GRAPH_CLIENT_SECRET=your-client-secret \
  -e NAMESPACE=enterprise_prod \
  -e WEBUI_GATEWAY_ID=enterprise_gateway \
  solace-agent-mesh-enterprise:<tag>
```

## Best Practices

### Security Recommendations

1. **Principle of Least Privilege**: Assign users the minimum permissions necessary for their tasks
2. **Regular Audits**: Periodically review role assignments and permissions
3. **Secure Configuration Files**: Protect your RBAC configuration files with appropriate file permissions
4. **Use Environment Variables**: Store sensitive information like MS Graph credentials as environment variables
5. **Avoid Development Configurations**: Never use development configurations in production environments

### Role Design Principles

1. **Role Granularity**: Create roles that align with job functions
2. **Role Hierarchy**: Use role inheritance to build a logical hierarchy
3. **Descriptive Names**: Use clear, descriptive names for roles
4. **Documentation**: Document the purpose and scope of each role
5. **Minimize Wildcard Usage**: Avoid using wildcards (`*`) except for admin roles

### Docker-Specific Recommendations

1. **Persistent Volumes**: Use Docker volumes for persistent configuration storage
2. **Environment-Specific Configs**: Create separate configuration files for different environments
3. **Health Checks**: Implement health checks to verify RBAC is functioning correctly
4. **Backup Configurations**: Regularly backup your RBAC configuration files
5. **Container Security**: Follow Docker security best practices (non-root user, read-only filesystem where possible)

## Troubleshooting

### Common Issues and Solutions

#### Issue: Authorization Denied for Valid User

**Symptoms**:
- User cannot access features they should have permission to use
- Authorization denied messages in logs

**Solutions**:
1. Verify the user identity matches exactly what's in `user-to-role-assignments.yaml`
2. Check that the role has the necessary scopes
3. Ensure configuration files are correctly mounted in the Docker container
4. Check logs for authorization service errors
   ex:
```bash
INFO:solace_ai_connector:[ConfigurableRbacAuthSvc] Successfully loaded role-to-scope definitions from: /app/configs/auth/role-to-scope-definitions1.yaml
DEBUG:solace_ai_connector:[ConfigurableRbacAuthSvc] Role 'enterprise_admin' loaded with 1 direct scopes, 1 resolved scopes.
DEBUG:solace_ai_connector:[ConfigurableRbacAuthSvc] Role 'data_analyst' loaded with 4 direct scopes, 4 resolved scopes.
DEBUG:solace_ai_connector:[ConfigurableRbacAuthSvc] Role 'standard_user' loaded with 1 direct scopes, 1 resolved scopes.
```

#### Issue: Configuration Files Not Found

**Symptoms**:
- Error messages about missing configuration files
- Default/fallback authorization behavior

**Solutions**:
1. Verify the file paths in your enterprise configuration
2. Check that the volume mount is correct in your Docker run command
3. Ensure file permissions allow the container user to read the files
4. Check for typos in file names or paths

#### Issue: MS Graph Integration Not Working

**Symptoms**:
- Users cannot authenticate
- Error messages related to MS Graph in logs

**Solutions**:
1. Verify MS Graph credentials are correct
2. Check that environment variables are properly set
3. Ensure the MS Graph application has the necessary permissions
4. Check network connectivity from the container to MS Graph endpoints

### Debugging Authorization

To debug authorization issues:

1. **Enable Debug Logging**:
   ```yaml
   # Add to your enterprise_config.yaml
   log_level: "DEBUG"
   ```

2. **Check Container Logs**:
   ```bash
   docker logs sam-enterprise
   ```

3. **Verify Configuration Loading**:
   Look for log messages with `[EnterpriseConfigResolverImpl]` or `[ConfigurableRbacAuthSvc]` prefixes

4. **Test with Admin User**:
   Temporarily assign the user to an admin role to verify if it's a permission issue

5. **Inspect Mounted Files**:
   ```bash
   docker exec -it sam-enterprise ls -la /app/configs/auth
   docker exec -it sam-enterprise cat /app/configs/auth/role-to-scope-definitions.yaml
   ```

### Getting Help

If you continue to experience issues:

1. Check the SAM Enterprise documentation
2. Review the logs for specific error messages
3. Contact Solace support with details of your configuration and the issues you're experiencing

## Conclusion

Setting up Role-Based Access Control in your SAM Enterprise Docker installation provides enhanced security and granular access control. By following this guide, you can configure RBAC to meet your organization's specific requirements while maintaining a secure and manageable environment.

Remember to regularly review and update your RBAC configuration as your organization's needs evolve, and always follow security best practices when managing access control.
