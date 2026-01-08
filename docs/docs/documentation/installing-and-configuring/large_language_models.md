---
title: Configuring LLMs
sidebar_position: 340
---

Large Language Models (LLMs) serve as the intelligence foundation for Agent Mesh, powering everything from natural language understanding to complex reasoning and decision-making. The system provides flexible configuration options that allow you to connect with various LLM providers through a unified interface, making it easy to switch between providers or use multiple models for different purposes.

You can configure LLM settings in two locations within your Agent Mesh deployment. The `apps.app_config.model` field allows you to specify model settings for individual agents or gateways, providing fine-grained control over which models specific components use. Alternatively, you can define models globally in the `shared_config.yaml` file under the `models` section, creating reusable configurations that multiple components can reference. For detailed information about the overall configuration structure and shared configuration management, see the [Configuring Agent Mesh](./configurations.md).

## Understanding LiteLLM Integration

Agent Mesh leverages [LiteLLM](https://docs.litellm.ai/docs/providers) to provide seamless integration with numerous LLM providers. This integration layer abstracts the differences between various provider APIs, allowing you to use a consistent configuration format regardless of whether you're connecting to OpenAI, Anthropic, Google, Amazon, or other supported providers.

The configuration system passes all fields from the `models` section directly to LiteLLM, giving you access to the full range of provider-specific options and features. This approach ensures that you can take advantage of advanced capabilities offered by different providers while maintaining a consistent configuration experience across your deployment.

Environment variables provide a secure and flexible way to manage sensitive information such as API keys and endpoint URLs. The configuration system supports environment variable substitution using the format `${ENV_VAR_NAME, default_value}`, allowing you to keep secrets out of your configuration files while providing sensible defaults for development environments.

## Provider-Specific Configurations

### OpenAI

OpenAI provides some of the most widely-used language models, including the GPT series. The configuration requires minimal setup, needing only the model name and your API key. The system uses OpenAI's default endpoints automatically, simplifying the configuration process.

```yaml
model: gpt-5
api_key: ${OPENAI_API_KEY}
```

If your organization belongs to multiple OpenAI organizations, you can specify which organization to use by adding the `organization` parameter. This parameter helps ensure billing and usage tracking align with your organizational structure.

For comprehensive details about OpenAI-specific configuration options and advanced features, see the [OpenAI documentation](https://docs.litellm.ai/docs/providers/openai).

### Azure OpenAI

Azure OpenAI Service provides OpenAI models through Microsoft's cloud infrastructure, offering additional enterprise features such as private networking and enhanced security controls. The configuration requires specifying your custom Azure endpoint, API key, and API version.

```yaml
model: azure/gpt-5
api_base: ${AZURE_API_BASE,"https://your-custom-endpoint.openai.azure.com/"}
api_key: ${AZURE_API_KEY}
api_version: ${AZURE_API_VERSION,"2024-12-01-preview"}
```

The model name must include the `azure/` prefix to indicate you're using Azure OpenAI rather than the standard OpenAI service. The API base URL points to your specific Azure OpenAI resource, which you configure during the Azure setup process.

For detailed information about Azure-specific configuration options, deployment models, and enterprise features, see the [Azure OpenAI documentation](https://docs.litellm.ai/docs/providers/azure/).

### Google Vertex AI

Google Vertex AI provides access to both Google's own models and third-party models through a unified platform. This service offers enterprise-grade features including fine-tuning capabilities, model versioning, and integration with other Google Cloud services.

```yaml
model: vertex_ai/claude-sonnet-4@20250514
vertex_project: ${VERTEX_PROJECT}
vertex_location: ${VERTEX_LOCATION,"us-east5"}
vertex_credentials: ${VERTEX_CREDENTIALS}
```

The `vertex_credentials` parameter requires a JSON string containing your Google Cloud service account key. This credential provides the necessary authentication for accessing Vertex AI services. You can obtain this key from the Google Cloud Console by creating a service account with appropriate Vertex AI permissions.

An example of the credential structure follows this format:

```sh
export VERTEX_CREDENTIALS='{"type": "", "project_id": "", "private_key_id": "", "private_key": "", "client_email": "", "client_id": "", "auth_uri": "", "token_uri": "", "auth_provider_x509_cert_url": "", "client_x509_cert_url": "", "universe_domain": ""}'
```

For comprehensive information about Vertex AI configuration, available models, and advanced features, see the [Vertex AI documentation](https://docs.litellm.ai/docs/providers/vertex).

### Amazon Bedrock

Amazon Bedrock provides access to foundation models from various providers through AWS infrastructure. This service offers enterprise features such as private VPC connectivity, AWS IAM integration, and comprehensive logging through AWS CloudTrail.

```yaml
model: bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0
aws_region_name: ${AWS_REGION_NAME,"us-east-1"}
aws_access_key_id: ${AWS_ACCESS_KEY_ID}
aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}
```

The model name includes the `bedrock/` prefix followed by the specific model identifier as defined in the Bedrock service. AWS credentials follow standard AWS authentication patterns, allowing you to use IAM roles, environment variables, or credential files depending on your deployment environment.

For detailed information about Bedrock-specific configuration options, available models, and AWS integration features, see the [AWS Bedrock documentation](https://docs.litellm.ai/docs/providers/bedrock).

### Anthropic

Anthropic provides the Claude family of models, known for their strong reasoning capabilities and helpful, harmless, and honest behavior. The direct Anthropic API offers the most up-to-date model versions and features.

```yaml
model: claude-4
api_key: ${ANTHROPIC_API_KEY}
```

The configuration requires only the model name and your Anthropic API key, making it straightforward to integrate Claude models into your agent workflows. Anthropic regularly updates their models with improved capabilities, and the direct API typically provides access to the latest versions first.

For comprehensive details about Anthropic-specific configuration options and model capabilities, see the [Anthropic documentation](https://docs.litellm.ai/docs/providers/anthropic).

### Additional Providers

LiteLLM supports numerous other providers including Cohere, Hugging Face, Together AI, and many more. Each provider may have specific configuration requirements and capabilities, but the general pattern of specifying model names, endpoints, and authentication credentials remains consistent.

For a complete list of supported providers and their specific configuration requirements, see the [LiteLLM providers documentation](https://docs.litellm.ai/docs/providers).


## Prompt Caching

Agent Mesh supports prompt caching to significantly reduce costs and latency when using LLM providers that support this feature. Prompt caching allows frequently-used content such as system instructions and tool definitions to be cached by the LLM provider, reducing both processing time and token costs on subsequent requests.

### How Prompt Caching Works

When you configure prompt caching, the system marks specific portions of each request for caching by the LLM provider. These cached portions persist for a provider-defined duration (typically 5 minutes to 1 hour) and can be reused across multiple requests without re-processing. This approach provides substantial cost savings for agents with large system instructions or extensive tool definitions.

### Supported Providers

The caching mechanism operates transparently through LiteLLM's provider-agnostic interface. Prompt caching support varies by provider:

- **Anthropic Claude**: Full support with explicit cache control, 90% cost reduction on cache hits
- **OpenAI**: Automatic caching for content exceeding 1,024 tokens
- **Azure OpenAI**: Automatic caching following OpenAI behavior
- **AWS Bedrock**: Native caching support via LiteLLM translation
- **Deepseek**: Native caching support via LiteLLM translation

Providers without caching support safely ignore cache control markers, ensuring backward compatibility across all providers.

### Cache Strategy Configuration

Agent Mesh provides three cache strategies that you can configure per model to optimize costs based on usage patterns:

| Strategy | Description | Cache Duration | Best For |
|----------|-------------|----------------|----------|
| `"5m"` | 5-minute ephemeral cache | 5 minutes | High-frequency agents (10+ calls/hour) |
| `"1h"` | 1-hour extended cache | 1 hour | Burst patterns with gaps (3-10 calls/hour) |
| `"none"` | Disable caching | N/A | Rarely-used agents (less than 2 calls/hour) |

The default strategy is `"5m"` when not explicitly specified, providing optimal performance for most use cases without requiring configuration changes.

### Configuration Examples

Configure prompt caching in your model settings using the `cache_strategy` parameter:

```yaml
models:
  # High-frequency orchestrator with 5-minute cache
  planning:
    model: anthropic/claude-sonnet-4-5-20250929
    api_key: ${ANTHROPIC_API_KEY}
    cache_strategy: "5m"
    temperature: 0.1

  # Burst-pattern agent with 1-hour cache
  analysis:
    model: anthropic/claude-sonnet-4-5-20250929
    api_key: ${ANTHROPIC_API_KEY}
    cache_strategy: "1h"
    temperature: 0.7

  # Low-frequency agent with caching disabled
  maintenance:
    model: anthropic/claude-sonnet-4-5-20250929
    api_key: ${ANTHROPIC_API_KEY}
    cache_strategy: "none"
```


### Cache Strategy Selection Guidelines

Choose your cache strategy based on agent usage patterns:

**Use "5m" strategy** when:
- Agent receives 10 or more requests per hour
- Requests arrive in steady streams rather than isolated bursts
- Cache remains warm through continuous use
- Example: Primary orchestrator agents handling user interactions

**Use "1h" strategy** when:
- Agent receives 3-10 requests per hour in burst patterns
- Gaps between request bursts exceed 5 minutes
- Extended cache duration bridges usage gaps
- Example: Development and testing scenarios, periodic analysis agents

**Use "none" strategy** when:
- Agent receives fewer than 2 requests per hour
- Cache write premium exceeds potential savings
- System instructions change frequently
- Example: Maintenance agents, backup handlers, rarely-used specialized agents

### What Gets Cached

The caching system optimizes two primary components of LLM requests:

**System Instructions**: The complete agent system prompt, including capabilities, guidelines, and any static context. System instructions typically represent the largest cacheable content and provide the most significant cost savings.

**Tool Definitions**: All tool declarations available to the agent, including peer agent communication tools. Agent Mesh ensures tool order stability through alphabetical sorting, maintaining cache validity across requests.

Conversation history and user messages are never cached, as these components change with each request and represent the unique context for each interaction.

### Cache Invalidation

The system automatically handles cache invalidation, requiring no manual intervention. When the cache expires or invalidates, the next request writes new cache content, and subsequent requests benefit from the refreshed cache.

## OAuth 2.0 Authentication

Agent Mesh supports OAuth 2.0 Client Credentials authentication for LLM providers that require OAuth-based authentication instead of traditional API keys. This authentication method provides enhanced security through automatic token management, secure credential handling, and seamless integration with OAuth-enabled LLM endpoints.

### Overview

The OAuth 2.0 Client Credentials flow is a machine-to-machine authentication method defined in [RFC 6749](https://tools.ietf.org/html/rfc6749#section-4.4). Agent Mesh handles the complete OAuth lifecycle automatically, including token acquisition, caching, refresh, and injection into LLM requests. This implementation ensures secure and efficient authentication without requiring manual token management.

### Configuration Parameters

OAuth authentication requires several configuration parameters that you can specify through environment variables and YAML configuration:

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| `oauth_token_url` | Yes | OAuth token endpoint URL | - |
| `oauth_client_id` | Yes | OAuth client identifier | - |
| `oauth_client_secret` | Yes | OAuth client secret | - |
| `oauth_scope` | No | OAuth scope (space-separated) | None |
| `oauth_ca_cert` | No | Custom CA certificate path for OAuth endpoint | None |
| `oauth_token_refresh_buffer_seconds` | No | Seconds before expiration to refresh token | 300 |

### Environment Variables

Configure OAuth credentials securely using environment variables in your `.env` file:

```bash
# Required OAuth Configuration
OAUTH_TOKEN_URL="https://auth.example.com/oauth/token"
OAUTH_CLIENT_ID="your_client_id"
OAUTH_CLIENT_SECRET="your_client_secret"

# Optional OAuth Configuration
OAUTH_SCOPE="llm.read llm.write"
OAUTH_CA_CERT_PATH="/path/to/ca.crt"
OAUTH_TOKEN_REFRESH_BUFFER_SECONDS="300"

# LLM Endpoint Configuration
OAUTH_LLM_API_BASE="https://api.example.com/v1"
```

### YAML Configuration

Configure OAuth-authenticated models in your `shared_config.yaml` file:

```yaml
models:
  # OAuth-authenticated planning model
  planning:
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
  general:
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

### Error Handling and Fallback

The OAuth system implements robust error handling:

- **4xx Errors**: Client configuration errors result in no retries, as these indicate credential or configuration issues
- **5xx Errors**: Server errors trigger exponential backoff with jitter for up to 3 retry attempts
- **Network Errors**: Connection issues trigger exponential backoff with jitter for up to 3 retry attempts

If OAuth authentication fails and an `api_key` is configured in the model settings, the system automatically falls back to API key authentication and logs the OAuth failure. If no fallback is available, the request fails with the OAuth error.

### Security Considerations

When implementing OAuth authentication, follow these security best practices:

1. **Credential Storage**: Always store OAuth credentials securely using environment variables, never hardcode them in configuration files
2. **Token Caching**: Tokens are cached in memory only and never persisted to disk
3. **SSL/TLS**: Always use HTTPS for OAuth endpoints to protect credentials in transit
4. **Custom CA Certificates**: Use the `oauth_ca_cert` parameter for private or internal OAuth servers with custom certificate authorities
5. **Scope Limitation**: Request only the minimal OAuth scopes required for your LLM operations

### Troubleshooting OAuth Issues

Common OAuth authentication issues and their solutions:

**Invalid Client Credentials**
```
ERROR: OAuth token request failed with status 401: Invalid client credentials
```
Verify that `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` are correct and properly URL-encoded if they contain special characters.

**Invalid Scope**
```
ERROR: OAuth token request failed with status 400: Invalid scope
```
Verify that `OAUTH_SCOPE` matches your provider's requirements and that scope values are space-separated.

**SSL Certificate Issues**
```
ERROR: OAuth token request failed: SSL certificate verification failed
```
Set `OAUTH_CA_CERT_PATH` to point to your custom CA certificate file and verify the certificate chain is complete.

**Token Refresh Issues**
```
WARNING: OAuth token request failed (attempt 1/4): Connection timeout
```
Check network connectivity to the OAuth endpoint, verify the OAuth endpoint URL is correct, and consider increasing timeout values if needed.

### Supported Providers

This OAuth implementation works with any LLM provider that supports OAuth 2.0 Client Credentials flow, accepts Bearer tokens in the `Authorization` header, and is compatible with LiteLLM's request format. Examples include Azure OpenAI with OAuth-enabled endpoints, custom enterprise LLM deployments, and third-party LLM services with OAuth support.


## Security and SSL/TLS Configuration

Agent Mesh provides comprehensive security controls for connections to LLM endpoints, allowing you to fine-tune SSL/TLS behavior to meet your organization's security requirements. These settings help ensure secure communication with LLM providers while providing flexibility for various network environments and security policies.

The SSL verification setting controls whether the system validates SSL certificates when connecting to LLM endpoints. Although disabling verification can resolve connectivity issues in development environments, production deployments should always use proper SSL verification to maintain security.

SSL security levels determine the cryptographic standards required for connections. Higher security levels enforce stricter requirements but may cause compatibility issues with older endpoints. The default level provides a good balance between security and compatibility for most deployments.

Custom SSL certificates allow you to specify additional trusted certificate authorities or use self-signed certificates in controlled environments. You can provide certificates either as file paths or as direct certificate content in PEM format.

| Parameter                  | Type      | Description                                                        | Default   |
|----------------------------|-----------|--------------------------------------------------------------------|-----------|
| `SSL_VERIFY`               | `boolean` | Controls SSL certificate verification for outbound connections.    | `true`    |
| `SSL_SECURITY_LEVEL`       | `integer` | Sets the SSL security level (higher values enforce stricter checks). | `2`       |
| `SSL_CERT_FILE`            | `string`  | Path to a custom SSL certificate file to use for verification.     | (none)    |
| `SSL_CERTIFICATE`          | `string`  | Direct content of the SSL certificate (PEM format).                | (none)    |
| `DISABLE_AIOHTTP_TRANSPORT`| `boolean` | Flag to disable the use of aiohttp transport for HTTP requests.    | `false`   |
| `AIOHTTP_TRUST_ENV`        | `boolean` | Flag to enable aiohttp to trust environment proxy settings.        | `false`   |

The HTTP transport settings control how the system makes network requests to LLM endpoints. The aiohttp transport provides efficient asynchronous HTTP handling, although some environments may require disabling it for compatibility reasons. The trust environment setting allows the HTTP client to use proxy settings from environment variables, which can be useful in corporate networks.

For detailed information about each security setting and specific use cases, see the [LiteLLM security documentation](https://docs.litellm.ai/docs/guides/security_settings).

### Example Environment Configuration

```bash
# SSL Configuration
SSL_VERIFY=true
SSL_SECURITY_LEVEL=2
SSL_CERT_FILE=/path/to/your/certificate.pem
SSL_CERTIFICATE="-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAg...T2u3V4w5X6y7Z8
-----END CERTIFICATE-----"

# HTTP Transport Configuration
DISABLE_AIOHTTP_TRANSPORT=false
AIOHTTP_TRUST_ENV=false
```

This example demonstrates how to configure SSL settings through environment variables, providing a secure foundation for LLM communications while maintaining flexibility for different deployment scenarios. The certificate content should be replaced with your actual certificate data, and file paths should point to your specific certificate locations.