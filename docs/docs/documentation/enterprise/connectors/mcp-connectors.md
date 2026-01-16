---
title: MCP Connectors
sidebar_position: 2
---

MCP connectors allow agents to communicate with remote MCP servers and access external tools.

## Overview

Model Context Protocol (MCP) is a standardized protocol that allows agents to interact with external data sources and services through a uniform interface. MCP connectors discover and invoke tools provided by MCP servers.

MCP connectors establish connections to remote MCP servers using one of two transport protocols: Server-Sent Events (SSE) or Streamable HTTP. The connector automatically discovers the tools that each server provides. Agents invoke these tools through natural language interactions. The connector handles protocol communication, authentication, and request formatting.

Agent Mesh Enterprise supports remote MCP servers only through the connector interface. The system does not support local MCP servers that use stdio (standard input/output) for communication. The connector requires network-accessible MCP servers using SSE or Streamable HTTP transport protocols. The connector supports multiple authentication methods and provides tool selection capabilities to control which MCP tools are available to agents.

## Prerequisites

Before you create an MCP connector, ensure you have the following:

### Remote MCP Server

You need a running remote MCP server that supports either Server-Sent Events (SSE) or Streamable HTTP transport. The server must be accessible over the network from your Agent Mesh Enterprise deployment.

### MCP Server URL

You need the URL endpoint of the MCP server. This is typically an HTTPS URL that implements the Model Context Protocol specification.

### Server Credentials (if required)

Depending on the MCP server's authentication requirements, you may need:

- API keys for servers using API key authentication
- Username and password for servers using basic authentication
- Bearer tokens for servers using token-based authentication
- OAuth2/OIDC credentials for servers using OAuth2 flows
- No credentials for public MCP servers without authentication

### Network Access

Ensure your Agent Mesh Enterprise deployment can reach the MCP server over the network. Verify that firewalls and security groups allow outbound HTTPS traffic to the server.

## Creating an MCP Connector

You create MCP connectors through the Connectors section in the Agent Mesh Enterprise web interface. Navigate to Connectors and click the Create Connector button to begin.

### Configuration Fields

The MCP connector creation form requires the following information:

**Connector Name**

A unique identifier for this connector within your Agent Mesh deployment. The name can contain letters, numbers, spaces, hyphens, and underscores. Choose a descriptive name that indicates the MCP server or service, such as `GitHub MCP`, `Atlassian MCP`, or `Canva MCP`.

The connector name must be unique across all connectors in your deployment, regardless of type. You cannot change the name after creation, so choose carefully.

**MCP Server URL**

Enter the URL endpoint of the remote MCP server. This must be a complete HTTPS URL that points to the MCP server's endpoint.

The server must support either Server-Sent Events (SSE) or Streamable HTTP transport protocol.

Example: `https://mcp.example.com/v1`

**Transport Protocol**

Select the transport protocol that the MCP server uses:
- SSE (Server-Sent Events): The server uses Server-Sent Events for streaming communication
- Streamable HTTP: The server uses HTTP streaming for communication

Verify with your MCP server administrator which transport protocol the server supports.

**Authentication Type**

Select the authentication method that matches your MCP server's requirements. The available options are:

- None: The MCP server does not require authentication
- API Key: The MCP server requires an API key sent in a header or query parameter
- HTTP: The MCP server uses HTTP authentication (Basic Auth or Bearer Token)
- OAuth2/OIDC: The MCP server uses OAuth2 or OpenID Connect flows

The authentication configuration fields that appear depend on the type you select.

**Tool Selection**

Specify which tools from the MCP server should be available to agents. You can select specific tools to expose or allow all discovered tools. See the Tool Selection section for details.

### Authentication Configuration

#### None

Select this option for public MCP servers that do not require authentication. No additional configuration is needed.

#### API Key

Configure API key authentication by providing:

**Location:** Select where the connector should send the API key:
- Header: Send the API key in an HTTP header
- Query Parameter: Send the API key as a URL query parameter

**Parameter Name:** Enter the name of the header or query parameter that should contain the API key.

**API Key Value:** Enter the API key value.

**Example Configuration (Header):**
- Location: Header
- Parameter Name: `X-API-Key`
- API Key Value: `your-api-key-here`

#### HTTP Authentication

Configure HTTP authentication by providing:

**HTTP Authentication Type:** Select the specific HTTP authentication method:
- Basic: Uses HTTP Basic Authentication with username and password
- Bearer: Uses Bearer token authentication

**For Basic Authentication:**

**Username:** Enter the username for Basic Authentication.

**Password:** Enter the password for Basic Authentication.

The connector automatically encodes the username and password in Base64 format and sends them in the `Authorization` header as required by the HTTP Basic Authentication specification.

**For Bearer Token:**

**Token:** Enter the bearer token value.

The connector sends the token in the `Authorization` header with the `Bearer` prefix as required by the Bearer token specification.

#### OAuth2/OIDC

Configure OAuth2 or OpenID Connect authentication using either discovery mode or manual mode.

**Discovery Mode**

In discovery mode, the connector automatically obtains OAuth2 configuration from the provider's discovery endpoint. This is the recommended approach for OAuth2 and OIDC-compliant providers.

No additional configuration is needed. The connector uses the MCP Server URL you provided earlier to discover the authorization endpoint, token endpoint, client credentials, and other OAuth2 configuration automatically.

**Manual Mode**

In manual mode, you specify the OAuth2 endpoints and configuration explicitly. Use this mode when the OAuth2 provider does not support standard discovery, when you need to override specific endpoints, or when the MCP server and OAuth2 provider are at different URLs.

Configure the following fields:

**Authorization Endpoint:** The URL where users authorize the application.

**Token Endpoint:** The URL where access tokens are obtained.

**Client ID:** Your OAuth2 client identifier.

**Client Secret:** Your OAuth2 client secret.

**Scopes:** Space-separated list of OAuth2 scopes to request (optional).

The connector uses these credentials to obtain access tokens and automatically refreshes them when they expire.

### Tool Selection

After you configure the connector settings and authentication, click Next to proceed to tool selection. The connector connects to the MCP server and retrieves the list of available tools. This retrieval process validates your configuration, verifying that the server URL is accessible, the transport protocol is correct, and the authentication credentials are valid.

You can then specify which tools should be available to agents by selecting specific tools or allowing all tools.

Tool selection helps you:
- Limit agents to relevant tools for their purpose
- Exclude potentially dangerous or administrative operations
- Reduce the number of tools agents must consider, improving response time and accuracy
- Control costs by limiting tool usage

If tool retrieval fails:

1. Verify the MCP server URL is correct and accessible
2. Check that the transport protocol selection matches what the server supports
3. Ensure authentication credentials are valid
4. Confirm network connectivity to the server

## After Creating the Connector

After you successfully create the connector, the system redirects you to the Connectors list where you can see your new connector. The connector is now available for assignment to agents.

To assign the connector to an agent, navigate to Agent Builder, create a new agent or edit an existing one, and select the connector from the available connectors list during agent configuration. You can assign the same connector to multiple agents.

For detailed information about creating and configuring agents, see [Agent Builder](../agent-builder.md).

## Security Considerations

MCP connectors implement a shared credential model where all agents assigned to a connector use the same credentials and have identical access to the MCP server's tools.

If you assign an MCP connector to multiple agents, those agents can all invoke any tools the connector exposes. You cannot restrict one agent to read-only tools and another agent to write tools if they share the same connector. Security boundaries exist at the authentication credential level and through tool selection, not at the connector assignment level.

To implement different access levels for different agents, create multiple connectors with different credentials (if the MCP server supports multiple credential sets with different permissions) or use tool selection to expose different tool subsets to different connectors.

Users can potentially invoke any tool the connector allows by phrasing requests appropriately. Tool selection and read-only credentials help mitigate these risks.

## Troubleshooting

### Connection Test Failures

If the connection test fails:

1. Verify the MCP server URL is correct and accessible
2. Check that the transport protocol selection (SSE or Streamable HTTP) matches what the server supports
3. Ensure authentication credentials are valid and not expired
4. Confirm the MCP server implements the Model Context Protocol correctly
5. Verify network connectivity and firewall rules allow access to the server

### Authentication Failures

If tool invocations fail with authentication errors:

1. Verify credentials are correct by testing them with the MCP server's documentation or API
2. Check that OAuth2 tokens have not expired. The connector should refresh them automatically
3. Confirm the authentication method matches the server's requirements
4. Ensure credentials have sufficient permissions for the tools agents attempt to invoke
5. For OAuth2 discovery mode, verify the issuer URL is correct and the discovery endpoint is accessible

### Tools Not Available

If agents report that tools are not available:

1. Verify the MCP server is running and responding to discovery requests
2. Check that tool selection is configured correctly
3. Review connector logs for tool discovery messages
4. Confirm the MCP server exposes the expected tools through the protocol

### Protocol Compatibility Issues

If you encounter protocol errors:

1. Verify the MCP server implements a compatible version of the Model Context Protocol
2. Confirm the server supports the selected transport protocol (SSE or Streamable HTTP)
3. Check server logs for protocol-level errors or incompatibilities
4. Ensure the server responds with valid protocol messages
5. Contact the MCP server administrator if the server implementation appears incompatible
