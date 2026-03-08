---
title: OpenAPI Tools
sidebar_position: 16
---

This guide walks you through configuring OpenAPI-based tools for Agent Mesh Enterprise. You will learn how to integrate REST APIs into your agents using OpenAPI specifications, enabling them to interact with any OpenAPI-compliant service.

## Table of Contents

- [Overview](#overview)
- [Understanding OpenAPI Tools](#understanding-openapi-tools)
- [Prerequisites](#prerequisites)
- [Configuration Steps](#configuration-steps)
- [Tool Filtering](#tool-filtering)
- [Authentication](#authentication)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

OpenAPI Tools allow agents to interact with REST APIs by automatically generating tool definitions from OpenAPI (Swagger) specifications. This enables agents to call API endpoints as if they were native tools, with proper parameter validation, type checking, and documentation.

### Why Use OpenAPI Tools

OpenAPI tools provide several important benefits for agent development:

**Automatic Tool Generation**: Define REST API integrations declaratively using existing OpenAPI specifications. No manual tool implementation required.

**Type Safety**: Parameter types, validation, and required fields are automatically enforced based on the OpenAPI schema.

**Documentation**: Tool descriptions and parameter documentation are extracted from the OpenAPI spec, helping the AI model understand how to use each tool effectively.

**Flexibility**: Support for multiple OpenAPI spec sources (files, URLs, inline), server URL overrides, and authentication methods.

### Supported Features

Agent Mesh Enterprise's OpenAPI tool integration supports:

- **OpenAPI 3.0+ specifications** in JSON or YAML format
- **Multiple specification sources**: local files, remote URLs, or inline specs
- **Server URL overrides**: Point specs to different environments (development, staging, production)
- **Tool filtering**: Include or exclude specific API operations using allow/deny lists
- **Authentication**: API key, HTTP (bearer token and basic auth), OAuth2/OIDC, and service account authentication
- **Automatic name conversion**: Handles camelCase operation IDs correctly

## Understanding OpenAPI Tools

Before you configure OpenAPI tools, you need to understand how they work and how API operations become callable tools.

### How OpenAPI Tools Work

When you configure an OpenAPI tool, Agent Mesh Enterprise performs the following steps:

1. **Specification Loading**: The system loads the OpenAPI specification from the configured source (file, URL, or inline).

2. **Operation Discovery**: Each path and HTTP method combination in the spec becomes a potential tool. The operation's `operationId` becomes the tool name.

3. **Schema Conversion**: OpenAPI parameter schemas are converted to the format expected by the AI model, including type information, validation rules, and descriptions.

4. **Tool Registration**: Each operation is registered as a callable tool with the agent. The AI model can then invoke these tools by name.

5. **Request Execution**: When the agent calls a tool, Agent Mesh Enterprise constructs the appropriate HTTP request based on the OpenAPI spec and executes it against the target API.

6. **Response Handling**: API responses are returned to the agent and can be used in subsequent tool calls or included in the agent's response to the user.

## Prerequisites

Before you configure OpenAPI tools, ensure you have the following:

### OpenAPI Specification

You need access to an OpenAPI specification for the API you want to integrate. This can be:

- A local OpenAPI spec file (JSON or YAML)
- A URL to a remote OpenAPI spec
- An inline OpenAPI spec defined in your configuration

Most modern REST APIs provide OpenAPI specifications. Check the API provider's documentation for:

- Swagger/OpenAPI spec download links
- API documentation pages (often generated from the spec)
- Developer portals that provide spec access

### API Access

Depending on the API's authentication requirements, you may need:

- **API Keys**: For APIs using API key authentication
- **Bearer Tokens**: For APIs using HTTP bearer token authentication
- **Username and Password**: For APIs using HTTP basic authentication
- **OAuth2/OIDC Credentials**: Client ID, client secret, and token endpoint URLs for OAuth2/OIDC authentication
- **Service Account**: For Google Cloud and similar services
- **Network Access**: Ensure your Agent Mesh Enterprise deployment can reach the API endpoints

### Target Server URL

If the OpenAPI spec's server URLs don't match your target environment, you'll need the correct base URL for the API. For example:

- Spec may contain: `https://api.production.com`
- You may want to use: `http://localhost:8080` (local development)

## Configuration Steps

Configuring OpenAPI tools involves specifying the spec source, optional server URL override, authentication, and tool filtering.

### Basic Configuration Structure

An OpenAPI tool configuration follows this structure:

```yaml
tools:
  - tool_type: openapi
    specification_url: "https://petstore3.swagger.io/api/v3/openapi.json"
    base_url: "http://localhost:8080"
    auth:
      type: apikey
      in: header
      name: api_key
      value: ${API_KEY}
```

### Configuration Parameters

#### tool_type

**Required**: Yes

Identifies this as an OpenAPI tool configuration.

```yaml
tool_type: openapi
```

#### Specification Source (Mutually Exclusive)

You must provide exactly one of the following specification sources:

**specification_file** - Path to a local OpenAPI spec file:

```yaml
specification_file: "examples/petstore_openapi.json"
```

**specification_url** - URL to fetch the OpenAPI spec from:

```yaml
specification_url: "https://petstore3.swagger.io/api/v3/openapi.json"
```

**specification** - Inline OpenAPI spec as a string:

```yaml
specification: |
  {
    "openapi": "3.0.0",
    "info": {
      "title": "My API",
      "version": "1.0.0"
    },
    "paths": {}
  }
specification_format: "json" # Optional: "json" or "yaml"
```

When using inline `specification`, you can optionally provide `specification_format` to hint at the format. The system auto-detects the format if not specified. Provide this only if auto-detection fails.

#### base_url

**Required**: No

Override the server URLs in the OpenAPI specification. This is useful when:

- The spec contains only a path (e.g., `/api/v3`) without a base URL
- You want to point to a different environment (development, staging, production)
- You're using a spec from one source but targeting a different server

```yaml
base_url: "http://localhost:8080"
```

**How it works**:

- If the original spec URL is `/api/v3` and `base_url` is `http://localhost:8080`, the result is `http://localhost:8080/api/v3`
- If the original spec URL is `https://petstore.swagger.io/api/v3` and `base_url` is `http://localhost:8080`, the result is `http://localhost:8080/api/v3` (path is preserved, base is replaced)
- Duplicate slashes are automatically handled

### Complete Example

Here's a complete agent configuration using an OpenAPI tool:

```yaml
apps:
  - name: pet_store_agent
    app_config:
      agent_name: "PetStoreAgent"
      display_name: "Pet Store API Agent"

      model: gemini-2.5-pro

      instruction: |
        You are a Pet Store API agent that can manage pets, orders, and users.
        Always provide the required fields when creating or updating resources.

      tools:
        - tool_type: openapi
          specification_url: "https://petstore3.swagger.io/api/v3/openapi.json"
          base_url: "http://localhost:8080"
          auth:
            type: apikey
            in: header
            name: api_key
            value: ${PET_STORE_API_KEY}

      session_service:
        type: "sql"
        database_url: "${DATABASE_URL}"
        default_behavior: "PERSISTENT"
```

## Tool Filtering

OpenAPI specifications often include many operations, but you may only want to expose a subset to your agent. Tool filtering allows you to control which operations are available.

### Why Filter Tools

Filtering tools provides several benefits:

**Security**: Exclude dangerous or administrative operations from agent access.

**Focused Agents**: Create specialized agents that only access relevant operations.

**Performance**: Reduce the number of tools the AI model must consider, improving response time and accuracy.

**Cost Control**: Fewer tools mean less token usage when the AI model selects tools.

### Filter Types

You can use two mutually exclusive filter types:

#### allow_list

Include only specific operations. All other operations are excluded.

```yaml
tools:
  - tool_type: openapi
    specification_url: "https://petstore3.swagger.io/api/v3/openapi.json"
    allow_list:
      - "getPetById"
      - "findPetsByStatus"
      - "updatePet"
```

**Use when**: You want explicit control over allowed operations, typically for security-sensitive APIs.

#### deny_list

Exclude specific operations. All other operations are included.

```yaml
tools:
  - tool_type: openapi
    specification_url: "https://petstore3.swagger.io/api/v3/openapi.json"
    deny_list:
      - "deletePet"
      - "deleteOrder"
      - "deleteUser"
```

**Use when**: You want most operations available but need to exclude a few dangerous or unnecessary ones.

### Filter Configuration

**Specifying Operation IDs**: Use the `operationId` as they appear in the OpenAPI spec.

**Finding Operation IDs**: Look in the OpenAPI spec under `paths[path][method].operationId`:

```json
{
  "paths": {
    "/pet/{petId}": {
      "get": {
        "operationId": "getPetById",
        "summary": "Find pet by ID"
      }
    }
  }
}
```

**Mutual Exclusivity**: You cannot specify both `allow_list` and `deny_list`. The system will reject the configuration with a validation error.

### Filtering Examples

**Read-Only Agent**:

```yaml
tools:
  - tool_type: openapi
    specification_url: "https://petstore3.swagger.io/api/v3/openapi.json"
    allow_list:
      - "getPetById"
      - "findPetsByStatus"
      - "findPetsByTags"
      - "getInventory"
      - "getOrderById"
      - "getUserByName"
```

**Full Access Except Deletes**:

```yaml
tools:
  - tool_type: openapi
    specification_url: "https://petstore3.swagger.io/api/v3/openapi.json"
    deny_list:
      - "deletePet"
      - "deleteOrder"
      - "deleteUser"
```

## Authentication

OpenAPI tools support multiple authentication methods: API key, HTTP authentication (bearer token and basic auth), OAuth2/OIDC, and service account authentication.

### API Key Authentication

API key authentication sends a key in either the request header or query parameter.

```yaml
auth:
  type: apikey
  in: header # or "query"
  name: api_key
  value: ${API_KEY}
```

**Parameters**:

- `type`: Must be `"apikey"`
- `in`: Where to send the key - `"header"` or `"query"`
- `name`: The name of the header or query parameter
- `value`: The API key value (use environment variables for security)

**Example** (header-based):

```yaml
auth:
  type: apikey
  in: header
  name: X-API-Key
  value: ${MY_API_KEY}
```

**Example** (query-based):

```yaml
auth:
  type: apikey
  in: query
  name: apikey
  value: ${MY_API_KEY}
```

### HTTP Authentication

HTTP authentication supports two schemes: bearer token and basic authentication.

#### Bearer Token Authentication

Bearer token authentication sends a token in the `Authorization` header using the Bearer scheme.

```yaml
auth:
  type: bearer
  token: ${BEARER_TOKEN}
```

**Parameters**:

- `type`: Must be `"bearer"`
- `token`: The bearer token value (use environment variables for security)

**Example**:

```yaml
tools:
  - tool_type: openapi
    specification_url: "https://api.example.com/openapi.json"
    base_url: "https://api.example.com"
    auth:
      type: bearer
      token: ${API_BEARER_TOKEN}
```

#### Basic Authentication

Basic authentication sends credentials in the `Authorization` header using the Basic scheme (base64-encoded username and password).

```yaml
auth:
  type: basic
  username: ${USERNAME}
  password: ${PASSWORD}
```

**Parameters**:

- `type`: Must be `"basic"`
- `username`: The username for authentication (use environment variables for security)
- `password`: The password for authentication (use environment variables for security)

**Example**:

```yaml
tools:
  - tool_type: openapi
    specification_url: "https://api.example.com/openapi.json"
    base_url: "https://api.example.com"
    auth:
      type: basic
      username: ${API_USERNAME}
      password: ${API_PASSWORD}
```

### OAuth2/OIDC Authentication

OAuth2/OIDC authentication obtains access tokens using the OAuth 2.0 or OpenID Connect protocol. This method supports the client credentials flow.

```yaml
auth:
  type: oauth2
  authorization_url: "https://auth.example.com/oauth/authorize"
  token_url: "https://auth.example.com/oauth/token"
  client_id: ${OAUTH_CLIENT_ID}
  client_secret: ${OAUTH_CLIENT_SECRET}
  scopes:
    - "read"
    - "write"
  token_endpoint_auth_method: "client_secret_post"
```

**Parameters**:

- `type`: Must be `"oauth2"`
- `authorization_url`: The OAuth2 authorization endpoint URL
- `token_url`: The OAuth2 token endpoint URL
- `client_id`: The OAuth2 client ID (use environment variables for security)
- `client_secret`: The OAuth2 client secret (use environment variables for security)
- `scopes`: List of OAuth2 scopes to request
- `token_endpoint_auth_method`: Method for authenticating at the token endpoint. Options include `"client_secret_post"` (credentials in request body) or `"client_secret_basic"` (credentials in Authorization header)

**Example**:

```yaml
tools:
  - tool_type: openapi
    specification_url: "https://api.example.com/openapi.json"
    base_url: "https://api.example.com"
    auth:
      type: oauth2
      authorization_url: "https://api.example.com/oauth/authorize"
      token_url: "https://api.example.com/oauth/token"
      scopes:
        - "employees:read"
        - "employees:write"
        - "departments:read"
      token_endpoint_auth_method: "client_secret_post"
      client_id: ${OAUTH_CLIENT_ID}
      client_secret: ${OAUTH_CLIENT_SECRET}
```

### Service Account Authentication

Service account authentication uses Google Cloud service account credentials.

```yaml
auth:
  type: serviceaccount
  service_account_json: ${SERVICE_ACCOUNT_JSON}
  scopes:
    - "https://www.googleapis.com/auth/cloud-platform"
```

**Parameters**:

- `type`: Must be `"serviceaccount"`
- `service_account_json`: JSON string containing the service account credentials
- `scopes`: List of API scopes to request

## Best Practices

Following these best practices helps you deploy OpenAPI tools effectively.

### Use Environment Variables for Secrets

Never hardcode API keys or other credentials in configuration files:

```yaml
# Good - use environment variables
auth:
  type: apikey
  in: header
  name: api_key
  value: ${API_KEY}

# Bad - hardcoded credentials
auth:
  type: apikey
  in: header
  name: api_key
  value: "sk-1234567890abcdef"  # Don't do this!
```

### Fetch Specs from URLs When Possible

Fetching specs from URLs ensures you always use the latest version:

```yaml
# Good - fetches latest spec
specification_url: "https://api.example.com/openapi.json"

# Less ideal - may become outdated
specification_file: "examples/api_spec.json"
```

Use local files only when:

- The API doesn't provide a public spec URL
- You need to use a modified or customized spec
- You want to lock to a specific API version

### Use allow_list for Security-Sensitive APIs

For APIs with dangerous operations (delete, administrative functions), use `allow_list` to explicitly control access:

```yaml
allow_list:
  - "getResource"
  - "listResources"
  - "updateResource"
# Deliberately exclude "deleteResource"
```

Use `deny_list` only when you're confident about the safety of unlisted operations.

### Provide Clear Agent Instructions

Include guidance in your agent's instructions about the API and required parameters:

```yaml
instruction: |
  You are a Pet Store API agent.

  When creating pets:
  - name (required): The pet's name
  - photoUrls (required): Array of photo URLs
  - id (required): Unique integer ID
  - category: Optional object with id and name
  - status: "available", "pending", or "sold"

  Always validate required fields before making requests.
```

### Test with Local APIs First

Test your configuration against local or development API instances before connecting to production:

```yaml
# Development
base_url: "http://localhost:8080"

# Production (after testing)
base_url: "https://api.production.com"
```

## Troubleshooting

This section addresses common issues when configuring OpenAPI tools.

### Specification Loading Fails

**Symptoms**: Agent fails to start with errors about loading or parsing the OpenAPI specification.

**Possible Causes and Solutions**:

1. **Invalid Specification Format**:

   - Verify the spec is valid JSON or YAML
   - Validate using online tools (Swagger Editor, OpenAPI Validator)
   - Check for syntax errors (missing commas, quotes, etc.)

2. **URL Not Accessible**:

   - Verify the `specification_url` is accessible from your deployment
   - Check network connectivity and firewall rules
   - Ensure HTTPS certificates are valid

3. **File Not Found**:
   - Verify the `specification_file` path is correct relative to the working directory
   - Check file permissions
   - Use absolute paths if relative paths fail

### Tools Not Available to Agent

**Symptoms**: The AI model reports that tools are not available or cannot be found.

**Possible Causes and Solutions**:

1. **Filtering Excluded All Tools**:

   - Review your `allow_list` or `deny_list` configuration
   - Verify operation IDs match those in the spec (case-sensitive)
   - Check agent logs for tool loading messages

2. **Empty Specification**:

   - Verify the OpenAPI spec contains `paths` with operations
   - Check that operations have `operationId` fields

### Authentication Errors

**Symptoms**: API calls fail with 401 or 403 errors.

**Possible Causes and Solutions**:

1. **Invalid or Missing Credentials**:

   - Verify environment variables are set correctly
   - Check that credentials haven't expired
   - Test credentials directly with the API using curl or Postman

2. **Wrong Authentication Location**:

   - Verify `in: header` vs `in: query` matches API requirements
   - Check the `name` parameter matches what the API expects
   - Review API documentation for exact auth requirements

### API Calls Fail or Return Errors

**Symptoms**: Tools execute but API returns errors or unexpected responses.

**Possible Causes and Solutions**:

1. **Wrong Server URL**:

   - Verify `base_url` points to the correct environment
   - Check that paths are correctly combined with base URL
   - Review server URL in agent logs

2. **Missing Required Parameters**:

   - Review API error messages for missing parameters
   - Update agent instructions to include required parameter guidance
   - Check OpenAPI spec for parameter requirements

3. **Type Mismatches**:
   - Verify parameter types match spec (string vs integer, etc.)
   - Check that enum values are valid
   - Review validation errors in API responses

## Conclusion

OpenAPI tools provide a powerful way to integrate REST APIs into your agents without manual tool implementation. By following the configuration steps, authentication methods, and best practices in this guide, you can quickly enable agents to interact with any OpenAPI-compliant service.

Key takeaways:

- Use `specification_url` to fetch specs from URLs when possible
- Override server URLs with `base_url` for environment-specific deployments
- Filter tools using `allow_list` (security-sensitive) or `deny_list` (convenience)
- Always use environment variables for credentials
- Use camelCase operation IDs in filter configurations
- Test with local/development APIs before production deployment
- Monitor tool usage and API errors through logging
