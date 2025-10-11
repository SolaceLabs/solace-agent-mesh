# OAuth 2.0 Client Credentials Authentication

This document describes how to configure and use OAuth 2.0 Client Credentials authentication with Solace Agent Mesh for LLM providers that require OAuth authentication.

## Overview

OAuth 2.0 Client Credentials is a machine-to-machine authentication flow defined in [RFC 6749](https://tools.ietf.org/html/rfc6749#section-4.4). This implementation allows Solace Agent Mesh to authenticate with LLM providers using OAuth 2.0 instead of API keys.

## Features

- **Automatic Token Management**: Tokens are automatically fetched, cached, and refreshed
- **Thread-Safe**: Concurrent requests safely share cached tokens
- **Retry Logic**: Exponential backoff for transient failures
- **SSL/TLS Support**: Custom CA certificates for secure connections
- **Graceful Fallback**: Falls back to API key authentication if OAuth fails
- **Configurable Refresh**: Proactive token refresh before expiration

## Configuration

### Environment Variables

Add the following environment variables to your `.env` file:

```bash
# Required OAuth Configuration
OAUTH_TOKEN_URL="https://auth.example.com/oauth/token"
OAUTH_CLIENT_ID="your_client_id"
OAUTH_CLIENT_SECRET="your_client_secret"

# Optional OAuth Configuration
OAUTH_SCOPE="llm.read llm.write"
OAUTH_CA_CERT_PATH="/path/to/ca.crt"
OAUTH_TOKEN_REFRESH_BUFFER_SECONDS="300"

# LLM Configuration
OAUTH_LLM_PLANNING_MODEL_NAME="your-planning-model"
OAUTH_LLM_GENERAL_MODEL_NAME="your-general-model"
OAUTH_LLM_API_BASE="https://api.example.com/v1"
```

### YAML Configuration

Configure OAuth authentication in your `shared_config.yaml`:

```yaml
models:
  # OAuth-authenticated planning model
  planning: &oauth_planning_model
    model: ${OAUTH_LLM_PLANNING_MODEL_NAME}
    api_base: ${OAUTH_LLM_API_BASE}
    
    # OAuth 2.0 Client Credentials configuration
    oauth_token_url: ${OAUTH_TOKEN_URL}
    oauth_client_id: ${OAUTH_CLIENT_ID}
    oauth_client_secret: ${OAUTH_CLIENT_SECRET}
    oauth_scope: ${OAUTH_SCOPE}
    oauth_ca_cert: ${OAUTH_CA_CERT_PATH}
    oauth_token_refresh_buffer_seconds: ${OAUTH_TOKEN_REFRESH_BUFFER_SECONDS, 300}
    
    parallel_tool_calls: true
    temperature: 0.1

  # OAuth-authenticated general model
  general: &oauth_general_model
    model: ${OAUTH_LLM_GENERAL_MODEL_NAME}
    api_base: ${OAUTH_LLM_API_BASE}
    
    # OAuth 2.0 Client Credentials configuration
    oauth_token_url: ${OAUTH_TOKEN_URL}
    oauth_client_id: ${OAUTH_CLIENT_ID}
    oauth_client_secret: ${OAUTH_CLIENT_SECRET}
    oauth_scope: ${OAUTH_SCOPE}
    oauth_ca_cert: ${OAUTH_CA_CERT_PATH}
    oauth_token_refresh_buffer_seconds: ${OAUTH_TOKEN_REFRESH_BUFFER_SECONDS, 300}
```

## Configuration Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| `oauth_token_url` | Yes | OAuth token endpoint URL | - |
| `oauth_client_id` | Yes | OAuth client identifier | - |
| `oauth_client_secret` | Yes | OAuth client secret | - |
| `oauth_scope` | No | OAuth scope (space-separated) | None |
| `oauth_ca_cert` | No | Custom CA certificate path | None |
| `oauth_token_refresh_buffer_seconds` | No | Refresh buffer in seconds | 300 |

## How It Works

1. **Token Acquisition**: When the first LLM request is made, the system:
   - Sends a POST request to the OAuth token endpoint
   - Includes client credentials and scope in the request body
   - Receives an access token with expiration information

2. **Token Caching**: The access token is cached with TTL based on:
   - Token expiration time minus refresh buffer
   - Minimum cache time of 60 seconds

3. **Token Injection**: For each LLM request:
   - Checks if cached token is valid (not expired or near expiry)
   - Fetches new token if needed
   - Injects Bearer token into request headers: `Authorization: Bearer <token>`

4. **Token Refresh**: Tokens are proactively refreshed when:
   - Current time + refresh buffer >= token expiration time
   - This prevents requests from failing due to expired tokens

## Error Handling

### OAuth Failures
- **4xx Errors**: No retries (client configuration errors)
- **5xx Errors**: Exponential backoff with jitter (up to 3 retries)
- **Network Errors**: Exponential backoff with jitter (up to 3 retries)

### Fallback Behavior
If OAuth authentication fails and an `api_key` is configured, the system will:
1. Log the OAuth failure
2. Fall back to API key authentication
3. Continue with the LLM request

If no fallback is available, the request will fail with the OAuth error.

## Security Considerations

1. **Credential Storage**: Store OAuth credentials securely using environment variables
2. **Token Caching**: Tokens are cached in memory only (not persisted to disk)
3. **SSL/TLS**: Always use HTTPS for OAuth endpoints
4. **Custom CA**: Use `oauth_ca_cert` for private/internal OAuth servers
5. **Scope Limitation**: Use minimal required OAuth scopes

## Troubleshooting

### Common Issues

1. **Invalid Client Credentials**
   ```
   ERROR: OAuth token request failed with status 401: Invalid client credentials
   ```
   - Verify `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET`
   - Check if credentials are properly URL-encoded

2. **Invalid Scope**
   ```
   ERROR: OAuth token request failed with status 400: Invalid scope
   ```
   - Verify `OAUTH_SCOPE` matches provider requirements
   - Check if scope values are space-separated

3. **SSL Certificate Issues**
   ```
   ERROR: OAuth token request failed: SSL certificate verification failed
   ```
   - Set `OAUTH_CA_CERT_PATH` for custom CA certificates
   - Verify certificate chain is complete

4. **Token Refresh Issues**
   ```
   WARNING: OAuth token request failed (attempt 1/4): Connection timeout
   ```
   - Check network connectivity to OAuth endpoint
   - Verify OAuth endpoint URL is correct
   - Consider increasing timeout values

### Debug Logging

Enable debug logging to troubleshoot OAuth issues:

```python
import logging
logging.getLogger("solace_agent_mesh.agent.adk.models.oauth2_token_manager").setLevel(logging.DEBUG)
```

## Testing

Run the OAuth authentication tests:

```bash
# Unit tests
pytest tests/unit/agent/adk/models/test_oauth2_token_manager.py -v

# Integration tests
pytest tests/integration/agent/test_oauth_llm_integration.py -v
```

## Migration from API Key Authentication

To migrate from API key to OAuth authentication:

1. **Add OAuth Configuration**: Add OAuth environment variables and YAML config
2. **Test Configuration**: Verify OAuth authentication works with your provider
3. **Update Models**: Change model configurations to use OAuth parameters
4. **Remove API Keys**: Optionally remove API key configuration (or keep as fallback)

## Supported LLM Providers

This OAuth implementation works with any LLM provider that:
- Supports OAuth 2.0 Client Credentials flow
- Accepts Bearer tokens in the `Authorization` header
- Is compatible with LiteLLM's request format

Examples of compatible providers:
- Azure OpenAI (with OAuth-enabled endpoints)
- Custom enterprise LLM deployments
- Third-party LLM services with OAuth support
