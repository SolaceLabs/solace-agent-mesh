---
title: Secure User Delegated Access
sidebar_position: 15
---

This guide walks you through configuring Secure User Delegated Access for Agent Mesh Enterprise. You will learn how to enable users to authenticate with remote MCP tools using their own credentials through OAuth2, providing enhanced security and user-specific access control.

## Table of Contents

- [Overview](#overview)
- [Understanding Secure User Delegated Access](#understanding-secure-user-delegated-access)
- [Prerequisites](#prerequisites)
- [Configuration Steps](#configuration-steps)
- [Security Considerations](#security-considerations)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Secure User Delegated Access allows users to interact with remote MCP (Model Context Protocol) tools using their own credentials rather than shared service credentials. When a user needs to access a remote MCP tool configured in an agent, they complete an OAuth2 authentication flow with the MCP provider's authorization server. This provides user-specific credentials that are securely stored and managed by Agent Mesh Enterprise.

### Why Use Secure User Delegated Access

This feature provides several important benefits for enterprise deployments:

**Enhanced Security**: Each user authenticates with their own credentials, eliminating shared service accounts and reducing the blast radius of compromised credentials. All API calls to remote services are made in the context of the authenticated user.

**Audit and Compliance**: User-specific credentials create clear audit trails showing exactly which user performed which actions. This is essential for compliance requirements and security investigations.

**Fine-Grained Access Control**: MCP providers can enforce their own access policies based on the authenticated user's permissions. Users only access resources they are authorized to use within the remote service.

**Credential Lifecycle Management**: User credentials can be individually revoked at the MCP provider level without affecting other users. This simplifies offboarding and incident response.

### Supported MCP Providers

Agent Mesh Enterprise supports remote MCP servers that implement the OAuth2.1 authentication flow. The following providers have been tested and validated:

- **Atlassian MCP Server**: Access Jira, Confluence, and other Atlassian services
- **Stripe MCP Server**: Interact with Stripe payment and billing APIs
- **Cloudflare MCP Server**: Manage Cloudflare resources and configurations
- **Canva MCP Server**: Access Canva design and content APIs

The feature works with both SSE (Server-Sent Events) and HTTP streaming remote MCP server types.

## Understanding Secure User Delegated Access

Before you configure this feature, you need to understand how it works and how credentials flow through the system.

### How the OAuth2 Flow Works

When a user attempts to use an MCP tool that requires OAuth2 authentication, Agent Mesh Enterprise initiates the following flow:

1. **Authentication Challenge**: The user's request triggers an authentication check. If no valid credentials exist for this user and MCP tool combination, the system prompts the user to authenticate.

2. **OAuth2 Authorization**: The user is redirected to the MCP provider's authorization server (for example, Atlassian or Stripe). The user logs in using their credentials for that service and grants permission for Agent Mesh Enterprise to access their resources.

3. **Authorization Code Exchange**: After successful authentication, the provider redirects back to Agent Mesh Enterprise with an authorization code. The system exchanges this code for access tokens at the provider's token endpoint.

4. **Credential Storage**: Agent Mesh Enterprise stores the access token (and refresh token if provided) in the credential service. Credentials are encrypted at rest (when using a database) and isolated per agent, user, and MCP tool.

5. **Authenticated Requests**: Subsequent requests to the MCP tool use the stored credentials automatically. The user does not need to re-authenticate unless credentials expire or are revoked.

6. **Token Refresh**: If the MCP provider supports refresh tokens and an access token expires, Agent Mesh Enterprise automatically obtains a new access token without requiring user interaction.

From an administrator's perspective, this flow is transparent once configured. Users experience a one-time authentication prompt per MCP tool, after which their access works seamlessly.

### Credential Storage

Agent Mesh Enterprise manages user credentials through a dedicated credential service with several important characteristics:

**Encryption at Rest**: When using database persistence, all stored credentials are automatically encrypted using the agent's unique identifier as the encryption key. This ensures that credentials cannot be used if extracted from database storage. Memory-based storage does not persist credentials to disk.

**Multi-Tenant Isolation**: Credentials are scoped to the combination of agent ID, user identity, and MCP tool. Credentials for one agent cannot be accessed by another agent, even for the same user and tool. This provides strong isolation in multi-tenant deployments.

**Configurable Expiration**: You can configure a time-to-live (TTL) for stored credentials. After the TTL expires, Agent Mesh Enterprise removes credentials from storage, requiring users to re-authenticate. This reduces the risk of long-lived credential compromise.

**Persistence Options**: Credentials can be stored in memory (for development or ephemeral deployments) or in a database (for production deployments where credentials should survive agent restarts).

### Credential Lifecycle

Understanding the credential lifecycle helps you plan operational procedures:

1. **Acquisition**: Credentials are acquired when a user first authenticates with an MCP provider through the OAuth2 flow.

2. **Active Use**: Stored credentials are used automatically for all subsequent requests to that MCP tool by that user.

3. **Expiration**: Credentials expire either through TTL timeout (configured by you) or token expiration (set by the MCP provider). Agent Mesh Enterprise attempts to refresh expired tokens if refresh tokens are available.

4. **Revocation**: Users or administrators can revoke credentials at the MCP provider level. When Agent Mesh Enterprise attempts to use revoked credentials, the request fails and the user must re-authenticate.

5. **Deletion**: Credentials are marked as deleted when they expire (TTL timeout), but are retained in the persistence layer for audit purposes. With memory storage, credentials are removed from storage when the agent is restarted.

## Prerequisites

Before you configure Secure User Delegated Access, ensure you have the following in place:

### MCP Provider Access

Some MCP providers require administrative access to authorize Agent Mesh Enterprise before users can authenticate. The requirements vary by provider:

**Example providers requiring domain authorization** (Atlassian, Stripe, Canva):

- Administrative access to the MCP provider's admin console
- Ability to add your Agent Mesh Enterprise domain to the provider's authorized domains list

**Example providers without administrative requirements** (Cloudflare):

- No administrative setup required
- Users can authenticate directly through the OAuth2 flow

Check the specific requirements for your chosen MCP provider.

### Callback URI Configuration

Your Agent Mesh Enterprise deployment must be accessible via a stable URL for OAuth2 callbacks. During the OAuth2 flow, users are redirected to the MCP provider for authentication, then redirected back to this callback URI.

You will configure this callback URI as an environment variable (see [Configure OAuth2 Callback URI](#configure-oauth2-callback-uri)). For providers requiring domain authorization (for example: Atlassian, Stripe, Canva), you will also register this domain in the provider's admin console.

### Database Setup (For Production)

For production deployments, you should use SQL persistence to ensure credentials survive agent restarts. You need:

- A supported SQL database (SQLite, PostgreSQL, MySQL, or other SQL database supported by SQLAlchemy)
- Appropriate database credentials and connection information
- Sufficient storage for credential data

See [Configure Session Service Type](#configure-session-service-type) for details on setting up persistence. For development or testing, you can use memory storage, but credentials will be lost when the agent restarts.

## Configuration Steps

Configuring Secure User Delegated Access involves several steps: configuring credential storage and lifecycle, optionally configuring the trust manager for enhanced security, and configuring your MCP tools with OAuth2 authentication.

### Step 1: Configure Credential Storage and Lifecycle

The credential service is automatically created and manages storage, retrieval, and lifecycle of user credentials. You configure it through environment variables and your session service configuration.

#### Configure Credential Time-to-Live

Set the credential TTL to control how long credentials remain valid in storage:

```bash
export SECRETS_TTL_SECONDS=86400  # 24 hours
```

The TTL value is specified in seconds. Common values include:

- `3600` - 1 hour (high security, frequent re-authentication)
- `86400` - 24 hours (balance of security and convenience)
- `604800` - 7 days (low security, infrequent re-authentication)
- `2592000` - 30 days (default if not specified)

Choose a TTL based on your security requirements and user experience considerations. Shorter TTLs require users to re-authenticate more frequently but reduce the window of exposure for compromised credentials.

#### Configure OAuth2 Callback URI

Set the callback URI where MCP providers will redirect users after authentication:

```bash
export OAUTH_TOOL_REDIRECT_URI=https://my.domain.com/api/v1/auth/tool/callback
```

Replace `https://my.domain.com` with your actual Agent Mesh Enterprise domain.

**Important**: The path `/api/v1/auth/tool/callback` must not be changed. This is the required callback endpoint path.

This URL must:

- Match exactly what you register with your MCP provider (for providers requiring domain authorization)
- Use HTTPS in production (HTTP is only acceptable for local development)
- Be accessible from users' browsers

#### Configure Session Service Type

User credentials are stored in the same database configured for session storage. For details on configuring session storage, see the [Session Storage documentation](../installing-and-configuring/session-storage.md).

Memory storage does not persist credentials across agent restarts. Use this only for development and testing.

**Important**: Ensure each agent has its own database to maintain proper credential isolation between agents.

### Step 2: Configure Trust Manager (Recommended)

The trust manager provides critical security for Secure User Delegated Access by cryptographically verifying user identities throughout the system. It ensures that credentials can only be accessed by the user who created them, preventing unauthorized access even if agent communication is compromised.

**Enabling the trust manager is strongly recommended for production deployments.**

#### Understanding Trust Manager

The trust manager uses public/private key cryptography to verify user identity:

1. **Gateway Authentication**: The WebUI Gateway verifies the user's identity during login (via SSO or other authentication)
2. **Cryptographic Signing**: The gateway cryptographically signs each user's identity using its private key
3. **Agent Verification**: When an agent receives a request, it uses the gateway's public key to verify the signed identity
4. **Credential Access Control**: The agent only grants access to credentials if the verified identity matches the credential owner

This cryptographic verification ensures that:

- User identities cannot be forged or tampered with in transit
- Each user can only access their own credentials
- Compromised agents cannot access other users' credentials
- All credential operations have verifiable audit trails

**The trust manager must be enabled on both the WebUI Gateway and all agents** to function correctly.

#### Enable Trust Manager on SSE Gateway

Add the trust manager configuration to your SSE Gateway configuration:

```yaml
# In your gateway configuration
trust_manager:
  enabled: true
```

#### Enable Trust Manager on Agents

Add the same trust manager configuration to each agent's configuration:

```yaml
# In each agent's configuration YAML
trust_manager:
  enabled: true
```

#### Example Configuration

Here is an example showing the trust manager full configuration (default values) on the gateway:

```yaml
# webui_gateway.yaml
apps:
  - name: a2a_webui_app
    app_config:
      # ... other configuration ...

      trust_manager:
        enabled: true
        card_publish_interval_seconds: 10
        card_expiration_days: 7
        verification_mode: "permissive"  # or "strict" for production
        clock_skew_tolerance_seconds: 300
        enable_time_validation: true
        jwt_default_ttl_seconds: 3600
        jwt_max_ttl_seconds: 86400
```

#### Secure Solace Broker Provisioning for Trust Manager

When using the trust manager, you should configure the Solace broker with proper credentials and ACLs to ensure secure trust card publishing. This prevents components from impersonating each other.

**Distinct Credentials Per Component**

Each gateway and agent instance should have its own unique broker credentials:

- Each gateway instance requires unique `client_username` and `client_password`
- Each agent instance requires unique `client_username` and `client_password`
- Never share credentials between different component instances

**ACL Configuration for Trust Card Publishing**

Configure Access Control Lists (ACLs) on your Solace broker to restrict which topics each component can publish to:

**For Gateway instances:**

Only the specific gateway instance is allowed to publish on its trust card topic:

```
Topic: {namespace}/a2a/v1/trust/gateway/{gateway_broker_client_username}
Permission: Publish (allow only for this gateway's client username)
```

**For Agent instances:**

Only the specific agent instance is allowed to publish on its trust card topic:

```
Topic: {namespace}/a2a/v1/trust/agent/{agent_broker_client_username}
Permission: Publish (allow only for this agent's client username)
```

Where:
- `{namespace}` is your configured namespace (e.g., `a2a/dev` or `a2a/prod`)
- `{gateway_broker_client_username}` is the unique broker username for the gateway
- `{agent_broker_client_username}` is the unique broker username for each agent

**Example ACL Configuration:**

If your namespace is `a2a/prod`, gateway username is `webui-gateway-01`, and agent username is `employee-agent-01`:

```
# Gateway ACL
Topic: a2a/prod/a2a/v1/trust/gateway/webui-gateway-01
Client Username: webui-gateway-01
Permission: Publish

# Agent ACL
Topic: a2a/prod/a2a/v1/trust/agent/employee-agent-01
Client Username: employee-agent-01
Permission: Publish
```

These ACLs ensure that:
- Components cannot publish trust cards pretending to be other components
- Trust card verification remains cryptographically secure
- Compromised credentials for one component cannot affect other components

### Step 3: Configure MCP Tools with OAuth2 Authentication

To use Secure User Delegated Access, you must configure your MCP tools to use OAuth2 authentication and provide a manifest of available tools.

#### Basic MCP Tool Structure

An MCP tool configuration with OAuth2 authentication follows this structure:

```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: sse  # or streamable-http
      url: "https://mcp.example.com/v1/sse"
    auth:
      type: oauth2
    manifest:
      - name: exampleTool
        description: Example tool description
        inputSchema:
          type: object
          properties: {}
          additionalProperties: false
          $schema: http://json-schema.org/draft-07/schema#
```

The key components are:

**`tool_type: mcp`**: Identifies this as an MCP tool configuration.

**`connection_params`**: Specifies how to connect to the remote MCP server:
- `type`: Either `sse` (Server-Sent Events) or `streamable-http`
- `url`: The endpoint URL for the MCP server

**`auth`**: Specifies the authentication type:
- `type: oauth2`: Enables OAuth2 user delegated access for this tool

**`manifest`**: Defines the tools available from this MCP server (explained below).

#### Understanding the Manifest Requirement

Due to limitations in the MCP protocol, Agent Mesh Enterprise cannot automatically discover available tools from OAuth2-protected MCP servers. The OAuth2 flow requires user interaction, which prevents the automatic tool discovery process from working.

To work around this limitation, you must provide a manifest that lists the tools available from the MCP server. This manifest is identical to what the MCP server would return from its tools list command.

#### Obtaining the Manifest

You can obtain the manifest in several ways:

**Method 1: Use MCP Provider Documentation**

Many MCP providers document their available tools. Check the provider's documentation for a list of tools and their schemas.

**Method 2: Use MCP Inspector**

Use a tool like [MCP Inspector](https://github.com/modelcontextprotocol/inspector) to connect to the MCP server and retrieve the output of the tools list command. You can then use this output directly as your manifest configuration.

#### Manifest Format

Each tool in the manifest follows this format:

```yaml
- name: toolName
  description: Tool description explaining what it does
  inputSchema:
    type: object
    properties:
      parameterName:
        type: string
        description: Parameter description
    required:
      - parameterName
    additionalProperties: false
    $schema: http://json-schema.org/draft-07/schema#
```

The `inputSchema` is a standard JSON Schema (draft-07) that defines what parameters the tool accepts. This schema is used for validation and to help the AI model understand how to call the tool.

**Note**: Complete sample MCP configurations are available in the [examples/agents/remote-mcp directory](https://github.com/SolaceLabs/solace-agent-mesh/tree/main/examples/agents/remote-mcp) for each of the tested remote MCP providers (Atlassian, Stripe, Cloudflare, Canva) to simplify setup.

### Step 4: Deploy Configuration

After configuring credential storage, trust manager, and MCP tools, deploy these configurations to your Agent Mesh Enterprise installation. Ensure that:

- Configuration files with MCP tool definitions are accessible to the agents
- Environment variables (`SECRETS_TTL_SECONDS`, `OAUTH_TOOL_REDIRECT_URI`) are set
- Database URLs are configured if using SQL persistence
- The installation is restarted to load the new configuration

After deployment, test the OAuth2 flow by attempting to use an OAuth2-enabled MCP tool. Users should be prompted to authenticate with the MCP provider.

## Security Considerations

Secure User Delegated Access involves storing and managing user credentials, which requires careful attention to security. This section outlines the security features built into the system and additional measures you should implement.

### Encryption at Rest

When using SQL persistence, all stored credentials are automatically encrypted before being written to the database. Agent Mesh Enterprise uses the agent's unique identifier as the encryption key, ensuring that credentials cannot be used if extracted from storage.

This encryption is automatic and requires no configuration. However, it means that:

- Credentials encrypted by one agent cannot be decrypted by another agent
- If an agent's unique identifier changes, existing credentials become inaccessible
- Database backups contain encrypted credentials that are useless without the agent

For additional security, ensure your database is stored on encrypted storage volumes provided by your infrastructure (for example, encrypted EBS volumes in AWS, encrypted persistent disks in GCP).

**Note**: Memory-based storage does not persist credentials to disk, so encryption at rest does not apply. Memory storage should only be used for development and testing.

### Trust Manager for Identity Verification

The trust manager provides defense-in-depth by verifying user identity on every credential operation. This prevents several attack scenarios:

**Credential Theft via Agent Compromise**: If an attacker compromises an agent and attempts to retrieve another user's credentials, the trust manager validates the user's identity token and denies access.

**Man-in-the-Middle Attacks**: The trust manager validates that identity tokens are signed by a trusted issuer, preventing token forgery.

**Replay Attacks**: Identity tokens include expiration times, limiting the window for replay attacks.

To maximize trust manager security:

- Always enable trust manager (`enabled: true`) in production
- Monitor trust manager logs for denied access attempts

### Credential Aging and Expiration

The `SECRETS_TTL_SECONDS` configuration provides defense against long-lived credential compromise. By setting an appropriate TTL, you ensure that:

- Stolen credentials have a limited lifetime
- Terminated users' credentials expire automatically
- Users periodically re-authenticate, allowing detection of account compromise

The default TTL is 30 days (2592000 seconds) if not specified.

### Provider-Side Revocation

MCP providers can revoke user credentials at any time through their own admin consoles. This provides an additional security control:

**User Offboarding**: When a user leaves the organization, revoke their access at the MCP provider level (Atlassian, Stripe, etc.) in addition to removing their access to Agent Mesh Enterprise.

**Incident Response**: If you suspect credential compromise, immediately revoke access at the MCP provider level. This blocks credential use even before they expire in Agent Mesh Enterprise.

**Audit Compliance**: Provider-side revocation creates audit logs in the provider's system, which may be required for compliance purposes.

Document your incident response procedures to include MCP provider credential revocation as a standard step.

### Network Security

Secure User Delegated Access involves network communication between users, Agent Mesh Enterprise, and MCP providers. Implement these network security measures:

**Use HTTPS Everywhere**: All communication must use HTTPS in production:
- User to Agent Mesh Enterprise: HTTPS
- Agent Mesh Enterprise to MCP providers: HTTPS
- MCP provider redirects back to Agent Mesh Enterprise: HTTPS

**Internal Communication Security**: If using the trust manager, ensure communication between agents and the SSE gateway is encrypted and authenticated.

### Logging and Monitoring

Enable comprehensive logging to detect and respond to security issues.

**Anomalous Patterns**: Monitor for unusual patterns such as:
- Multiple failed authentication attempts from a single user
- Credential access from unusual IP addresses or locations
- Rapid credential creation/deletion cycles

Integrate these logs with your SIEM (Security Information and Event Management) system for centralized monitoring and alerting.

## Best Practices

Following these best practices helps you deploy Secure User Delegated Access securely and reliably.

### Always Enable Trust Manager in Production

The trust manager provides critical defense-in-depth security. Always enable it in production deployments:

```yaml
trust_manager:
  enabled: true
```

Only disable the trust manager in development or testing environments where security is not a concern.

### Use SQL Persistence in Production

Memory persistence is only suitable for development and testing. Production deployments must use SQL persistence:

```yaml
session_service:
  type: "sql"
  database_url: ${AGENT_DATABASE_URL}
  default_behavior: "PERSISTENT"
```

### Set Appropriate TTL Values

Choose TTL values based on your security requirements and user experience considerations.

Never exceed 30 days (2592000 seconds). Document your TTL policy and rationale in your security documentation.

### Configure Separate Session Storage Per Agent

Each agent should have its own session storage database, which will automatically be used for credential storage as well.

This isolation provides defense-in-depth and simplifies multi-tenant deployments. See the [Session Storage documentation](../installing-and-configuring/session-storage.md) for more details on configuring session storage.

### Use HTTPS in Production

Configure HTTPS for all endpoints in production:

- Set `OAUTH_TOOL_REDIRECT_URI` to an HTTPS URL
- Configure SSL certificates for Agent Mesh Enterprise
- Verify that MCP providers use HTTPS endpoints
- Never use HTTP in production (only acceptable for local development)

## Troubleshooting

This section addresses common issues you may encounter when configuring or operating Secure User Delegated Access.

### OAuth2 Authentication Flow Fails

**Symptoms**: Users report that they are redirected to the MCP provider but never redirected back to Agent Mesh Enterprise, or they see an error after attempting to authenticate.

**Possible Causes and Solutions**:

1. **Incorrect Callback URI**:
   - **Verify**: Check that `OAUTH_TOOL_REDIRECT_URI` exactly matches the redirect URI registered with the MCP provider.
   - **Common mistake**: Mismatched protocols (HTTP vs HTTPS), missing ports, trailing slashes.
   - **Solution**: Update either the environment variable or the MCP provider configuration to match exactly.

2. **Domain Not Authorized** (For providers requiring domain authorization):
   - **Verify**: Check that your domain is listed in the MCP provider's authorized domains for MCP access.
   - **Solution**: Add your domain to the provider's authorized domain list following their documentation.

### Credentials Not Persisting Across Restarts

**Symptoms**: Users must re-authenticate every time the agent restarts, even though SQL persistence is configured.

**Possible Causes and Solutions**:

1. **Memory Storage Configured Instead of SQL**:
   - **Verify**: Check the agent configuration to ensure `session_service.type` is set to `"sql"`, not `"memory"`.
   - **Solution**: Update the configuration and restart the agent.

### Trust Manager Denying Access

**Symptoms**: Users receive "Access Denied" errors when attempting to use MCP tools, or logs show trust manager access denials.

**Possible Causes and Solutions**:

1. **Trust Manager Not Configured on All Components**:
   - **Verify**: Ensure trust manager is enabled on both the SSE Gateway and all agents.
   - **Solution**: Add trust manager configuration to all component configurations and restart.

### Credentials Expire Too Quickly or Too Slowly

**Symptoms**: Users report that they need to re-authenticate too frequently, or credentials remain valid longer than expected.

**Possible Causes and Solutions**:

1. **TTL Not Set Correctly**:
   - **Verify**: Check the `SECRETS_TTL_SECONDS` environment variable value.
   - **Solution**: Update the environment variable to the desired TTL and restart the agent.

2. **MCP Provider Token Expiration**:
   - **Note**: Even if your TTL is long, MCP providers may issue short-lived tokens.
   - **Verify**: Check the MCP provider's token expiration policy.
   - **Solution**: This is controlled by the MCP provider and cannot be changed. Ensure refresh tokens are working correctly to automatically renew expired tokens.

3. **Refresh Tokens Not Working**:
   - **Verify**: Check that the MCP provider issues refresh tokens and that Agent Mesh Enterprise is configured to use them.
   - **Diagnostic**: Look for token refresh attempts in the logs.
   - **Solution**: Ensure the OAuth2 scope includes `offline_access` or equivalent for the provider.

### Manifest Configuration Errors

**Symptoms**: MCP tools are not available, or the AI model reports that tools are missing or incorrectly defined.

**Possible Causes and Solutions**:

1. **Manifest Missing or Empty**:
   - **Verify**: Check that the `manifest` section in your MCP tool configuration is populated.
   - **Solution**: Add the manifest with tool definitions as described in the Configuration Steps section.

2. **Manifest Format Errors**:
   - **Verify**: Ensure the manifest follows the correct YAML structure and JSON Schema format.
   - **Common mistakes**: Missing required fields (`name`, `description`, `inputSchema`), invalid JSON Schema.
   - **Solution**: Validate your manifest structure against the examples in this document.

3. **JSON Schema Version Issues**:
   - **Note**: Manifests typically use the `http://json-schema.org/draft-07/schema#` standard. However, some LLM providers may require the newer `https://json-schema.org/specification-links#2020-12` specification, which can lead to errors at inference time.
   - **Solution**: Check your LLM provider's requirements and adjust the `$schema` field in your manifest accordingly.

If you encounter issues, check the latest Agent Mesh Enterprise documentation or enable debug logging to review detailed error information:

```yaml
log:
  stdout_log_level: DEBUG
  log_file_level: DEBUG
```

## Conclusion

Secure User Delegated Access provides enhanced security and user-specific access control for Agent Mesh Enterprise deployments using remote MCP tools. By following the configuration steps, security considerations, and best practices in this guide, you can deploy this feature securely and reliably.

Key takeaways:

- Always enable the trust manager in production for defense-in-depth security
- Use SQL persistence to ensure credentials survive agent restarts
- Set appropriate TTL values balancing security and user experience
- Configure database-per-agent isolation for multi-tenant security
- Follow provider-specific setup instructions carefully
- Implement comprehensive monitoring and logging
- Maintain regular security reviews of your configuration

Remember to keep your configuration updated as MCP providers evolve their APIs and authentication requirements, and regularly review your security posture to ensure continued protection of user credentials.
