---
title: Configuration Settings for LLMs
sidebar_position: 340
---

Large Language Models serve as the intelligence foundation for Agent Mesh, powering everything from natural language understanding to complex reasoning and decision-making. The system provides flexible configuration options that allow you to connect with various LLM providers through a unified interface, making it easy to switch between providers or use multiple models for different purposes.

You can configure LLM settings in two locations within your Agent Mesh deployment. The `apps.app_config.model` field allows you to specify model settings for individual agents or gateways, providing fine-grained control over which models specific components use. Alternatively, you can define models globally in the `shared_config.yaml` file under the `models` section, creating reusable configurations that multiple components can reference. For detailed information about the overall configuration structure and shared configuration management, see the [Configuring Agent Mesh](./configurations.md).

## Understanding LiteLLM Integration

Agent Mesh leverages [LiteLLM](https://docs.litellm.ai/docs/providers) to provide seamless integration with numerous LLM providers. This integration layer abstracts the differences between various provider APIs, allowing you to use a consistent configuration format regardless of whether you're connecting to OpenAI, Anthropic, Google, Amazon, or other supported providers.

The configuration system passes all fields from the `models` section directly to LiteLLM, giving you access to the full range of provider-specific options and features. This approach ensures that you can take advantage of advanced capabilities offered by different providers although maintaining a consistent configuration experience across your deployment.

Environment variables provide a secure and flexible way to manage sensitive information such as API keys and endpoint URLs. The configuration system supports environment variable substitution using the format `${ENV_VAR_NAME, default_value}`, allowing you to keep secrets out of your configuration files although providing sensible defaults for development environments.

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

LiteLLM supports numerous other providers including Cohere, Hugging Face, Together AI, and many more. Each provider may have specific configuration requirements and capabilities, although the general pattern of specifying model names, endpoints, and authentication credentials remains consistent.

For a complete list of supported providers and their specific configuration requirements, see the [LiteLLM providers documentation](https://docs.litellm.ai/docs/providers).

## Security and SSL/TLS Configuration

Agent Mesh provides comprehensive security controls for connections to LLM endpoints, allowing you to fine-tune SSL/TLS behavior to meet your organization's security requirements. These settings help ensure secure communication with LLM providers although providing flexibility for various network environments and security policies.

The SSL verification setting controls whether the system validates SSL certificates when connecting to LLM endpoints. Although disabling verification can resolve connectivity issues in development environments, production deployments should always use proper SSL verification to maintain security.

SSL security levels determine the cryptographic standards required for connections. Higher security levels enforce stricter requirements although may cause compatibility issues with older endpoints. The default level provides a good balance between security and compatibility for most deployments.

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

This example demonstrates how to configure SSL settings through environment variables, providing a secure foundation for LLM communications although maintaining flexibility for different deployment scenarios. The certificate content should be replaced with your actual certificate data, and file paths should point to your specific certificate locations.