---
title: LLM Models
sidebar_position: 12
---

# LLM Models

## Configuring Different LLM Providers

The `apps.app_config.model` field which can also be configured globally in `shared_config.yaml` under the `models` section, allows you to specify the connection details for different Large Language Model (LLM) providers. Solace Agent Mesh leverages [LiteLLM](https://docs.litellm.ai/docs/providers) to support a variety of LLM providers seamlessly. All fields provided in the `models` section are directly passed to LiteLLM, allowing you to configure any supported model.

Use the following provided YAML snippets for the model section in your YAML configuration files. You can use environment variables to manage sensitive information like API keys as well using the format `${ENV_VAR_NAME, default_value}`.

### OpenAI

```yaml
model: gpt-5
api_key: ${OPENAI_API_KEY}
```

Optionally, you can pass the parameter `organization` if you are part of multiple organizations.

More details at [OpenAI documentation](https://docs.litellm.ai/docs/providers/openai).

### Azure OpenAI

```yaml
model: azure/gpt-5
api_base: ${AZURE_API_BASE,"https://your-custom-endpoint.openai.azure.com/"}
api_key: ${AZURE_API_KEY}
api_version: ${AZURE_API_VERSION,"2024-12-01-preview"}
```

More details at [Azure OpenAI documentation](https://docs.litellm.ai/docs/providers/azure/).

### Vertex AI


```yaml
model: vertex_ai/claude-sonnet-4@20250514
vertex_project: ${VERTEX_PROJECT}
vertex_location: ${VERTEX_LOCATION,"us-east5"}
vertex_credentials: ${VERTEX_CREDENTIALS}
```

- `vertex_credentials` is a JSON string of the service account key.
  An example of the content is as follows:
  ```sh
  export VERTEX_CREDENTIALS='{"type": "", "project_id": "", "private_key_id": "", "private_key": "", "client_email": "", "client_id": "", "auth_uri": "", "token_uri": "", "auth_provider_x509_cert_url": "", "client_x509_cert_url": "", "universe_domain": ""}'
  ```

More details at [Vertex AI documentation](https://docs.litellm.ai/docs/providers/vertex).

### Bedrock


```yaml
model: bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0
aws_region_name: ${AWS_REGION_NAME,"us-east-1"}
aws_access_key_id: ${AWS_ACCESS_KEY_ID}
aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}
```

More details at [AWS Bedrock documentation](https://docs.litellm.ai/docs/providers/bedrock).

### Anthropic


```yaml
model: claude-4
api_key: ${ANTHROPIC_API_KEY}
```

More details at [Anthropic documentation](https://docs.litellm.ai/docs/providers/anthropic).



### Others

For a complete list of supported models and their configuration options, refer to LiteLlM's official documentation [here](https://docs.litellm.ai/docs/providers).

## SSL/TLS Configuration 

Solace Agent Mesh allows for fine tuning the security parameters on connections to your LLM endpoints through environment variables. The connection parameters are described in the following table:

| Parameter                  | Type      | Description                                                        | Default   |
|----------------------------|-----------|--------------------------------------------------------------------|-----------|
| `SSL_VERIFY`               | `boolean` | Controls SSL certificate verification for outbound connections.    | `true`    |
| `SSL_SECURITY_LEVEL`       | `integer` | Sets the SSL security level (higher values enforce stricter checks). | `2`       |
| `SSL_CERT_FILE`            | `string`  | Path to a custom SSL certificate file to use for verification.     | (none)    |
| `SSL_CERTIFICATE`          | `string`  | Direct content of the SSL certificate (PEM format).                | (none)    |
| `DISABLE_AIOHTTP_TRANSPORT`| `boolean` | Flag to disable the use of aiohttp transport for HTTP requests.    | `false`   |
| `AIOHTTP_TRUST_ENV`        | `boolean` | Flag to enable aiohttp to trust environment proxy settings.        | `false`   |

More information about each setting and it's use case can be found in the [LiteLLM docs](https://docs.litellm.ai/docs/guides/security_settings) 

##### Example `.env` file
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