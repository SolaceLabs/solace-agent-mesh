---
title: OpenAPI Connectors
sidebar_position: 3
---

OpenAPI connectors allow agents to interact with REST APIs that use OpenAPI specifications.

## Overview

OpenAPI connectors generate callable tools from API endpoints. Agents use these tools to make authenticated HTTP requests to external services and integrate with any OpenAPI-compliant REST API through natural language.

The connector reads the OpenAPI specification to determine:
- API structure and available endpoints
- Parameter requirements (path, query, header, and body parameters)
- Authentication methods and security schemes
- Request and response formats
- Content types (such as `application/json` or `application/x-www-form-urlencoded`)
- Data schemas and validation rules

The connector converts API operations into tools that agents invoke. It derives all request details from the specification, including HTTP methods, headers like `Content-Type`, required parameters, and expected response structures. You cannot modify these settings in Agent Builder. To change how the connector constructs requests, you must update the OpenAPI specification file itself.

The connector supports OpenAPI 3.0+ specifications in JSON or YAML format and provides flexible authentication options to accommodate different API security models.

## Prerequisites

Before you create an OpenAPI connector, ensure you have the following:

### OpenAPI Specification File

You need an OpenAPI specification file in JSON or YAML format that describes the REST API you want to integrate. Only OpenAPI 3.0+ specifications are supported. If you have an older OpenAPI 2.0 (Swagger) specification, you can use online converters such as [Swagger Converter](https://converter.swagger.io/) to upgrade it to OpenAPI 3.0 format.

### Public Storage Bucket Configuration

Your platform administrator must configure the platform service with a publicly accessible storage bucket where OpenAPI specification files are stored. This bucket requires public read access so agents can download specification files during startup without authentication.

If you are unsure whether the storage bucket is configured, contact your platform administrator. Without this configuration, you will not be able to create OpenAPI connectors.

For platform administrators: See [Infrastructure Setup: S3 Buckets for OpenAPI Connector Specs](../installation.md#infrastructure-setup-s3-buckets-for-openapi-connector-specs) in the enterprise installation guide for detailed setup instructions. Kubernetes deployments handle this configuration automatically via Helm charts.

### API Credentials (if required)

Depending on the API's authentication requirements, you may need:

- API keys for APIs using API key authentication
- Username and password for APIs using basic authentication
- Bearer tokens for APIs using token-based authentication
- OAuth2/OIDC credentials (client ID, client secret, and token endpoint URLs) for APIs using OAuth 2.0 or OpenID Connect authentication
- No credentials for public APIs without authentication

### Network Access

Ensure your Agent Mesh Enterprise deployment can reach the API endpoints over the network. Verify that firewalls and security groups allow outbound HTTPS traffic to the API server.

## Creating an OpenAPI Connector

You create OpenAPI connectors through the Connectors section in the Agent Mesh Enterprise web interface. Navigate to Connectors and click the Create Connector button to begin.

### Configuration Fields

The OpenAPI connector creation form requires the following information:

**Connector Name**

A unique identifier for this connector within your Agent Mesh deployment. The name can contain letters, numbers, spaces, hyphens, and underscores. Choose a descriptive name that indicates the API or service, such as `Stripe API`, `GitHub API`, or `CRM API`.

The connector name must be unique across all connectors in your deployment, regardless of type. You cannot change the name after creation, so choose carefully.

**OpenAPI Specification File**

Upload your OpenAPI specification file using the file picker or drag and drop. The file must be in JSON or YAML format and conform to OpenAPI 3.0 or later. The system stores the uploaded file in the configured public storage bucket where the platform service and agent can retrieve it.

**Authentication Type**

Select the authentication method that matches your API requirements. The available options are:

- None: The API does not require authentication
- API Key: The API requires an API key sent in a header or query parameter
- HTTP: The API uses HTTP authentication (Basic Auth or Bearer Token)
- OAuth2/OIDC: The API uses OAuth 2.0 or OpenID Connect authentication with client credentials

The authentication configuration fields that appear depend on the type you select.

### Authentication Configuration

#### None

Select this option for public APIs that do not require authentication. No additional configuration is needed.

#### API Key

Configure API key authentication by providing:

**Location:** Select where the connector should send the API key:
- Header: Send the API key in an HTTP header
- Query Parameter: Send the API key as a URL query parameter

**Parameter Name:** Enter the name of the header or query parameter that should contain the API key. Common examples include `X-API-Key`, `api_key`, or `apikey`.

**API Key Value:** Enter the API key value.

**Example Configuration (Header):**
- Location: Header
- Parameter Name: `X-API-Key`
- API Key Value: `your-api-key-here`

**Example Configuration (Query Parameter):**
- Location: Query Parameter
- Parameter Name: `apikey`
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

#### OAuth2/OIDC Authentication

Configure OAuth2 or OpenID Connect authentication by specifying the OAuth2 endpoints and configuration explicitly. Use this authentication type when the API requires OAuth2 client credentials for access.

Configure the following fields:

**Authorization Endpoint:** The URL where users authorize the application.

**Token Endpoint:** The URL where access tokens are obtained.

**Client ID:** Your OAuth2 client identifier.

**Client Secret:** Your OAuth2 client secret.

**Scopes:** Space-separated list of OAuth2 scopes to request (optional). Common examples include `read`, `write`, `admin`, or API-specific scopes like `users:read` or `data:write`.

**Token Endpoint Auth Method:** Select how the connector authenticates at the token endpoint:
- Client Secret Post: Send credentials in the request body
- Client Secret Basic: Send credentials in the Authorization header using Basic authentication

The connector uses these credentials to obtain access tokens and automatically refreshes them when they expire.

**Example Configuration:**
- Authorization Endpoint: `https://auth.example.com/oauth/authorize`
- Token Endpoint: `https://auth.example.com/oauth/token`
- Client ID: `your-client-id`
- Client Secret: `your-client-secret`
- Scopes: `read write`
- Token Endpoint Auth Method: Client Secret Post

## After Creating the Connector

After you successfully create the connector, the system redirects you to the Connectors list where you can see your new connector. The connector is now available for assignment to agents.

To assign the connector to an agent, navigate to Agent Builder, create a new agent or edit an existing one, and select the connector from the available connectors list during agent configuration. You can assign the same connector to multiple agents.

For detailed information about creating and configuring agents, see [Agent Builder](../agent-builder.md).

## Security Considerations

OpenAPI connectors implement a shared credential model where all agents assigned to a connector use the same API credentials and have identical access permissions to the API.

If you assign an OpenAPI connector to multiple agents, those agents can all invoke any API operations the connector's credentials permit. You cannot restrict one agent to read-only operations and another agent to write operations if they share the same connector. Security boundaries exist at the API credential level, not at the connector assignment level.

To implement different access levels for different agents, create multiple connectors with different API credentials if the API supports multiple credential sets with different permissions.

Users can potentially invoke any API operation the connector allows by phrasing requests appropriately. Using read-only API credentials when possible helps mitigate these risks.

## Troubleshooting

### Specification Loading Failures

If the connector fails to load the OpenAPI specification:

1. Ensure the specification file uses valid JSON or YAML format
2. Validate the specification using an online tool such as Swagger Editor or the OpenAPI CLI
3. Check that the file upload completed successfully
4. Verify the specification conforms to OpenAPI 3.0 or later schema requirements

### Authentication Failures

If API calls fail with 401 or 403 errors:

1. Verify the API credentials are correct by testing them directly with curl or Postman
2. Check that credentials have not expired
3. Confirm the authentication type matches what the API expects (API Key vs HTTP Basic vs Bearer vs OAuth2/OIDC)
4. Verify the parameter name or header name is correct
5. Ensure credentials have sufficient permissions for the operations agents attempt to invoke
6. For OAuth2/OIDC, verify the authorization endpoint, token endpoint, client ID, and client secret are correct
7. For OAuth2/OIDC, ensure the requested scopes are valid and permitted for your client credentials

### Operations Not Available

If agents report that operations are not available:

1. Verify the specification contains paths with operations defined
2. Check that operations have operationId fields. Operations without operationId are skipped and will not be available as tools
3. Review connector logs for tool loading messages
4. Confirm the specification was successfully uploaded and processed
