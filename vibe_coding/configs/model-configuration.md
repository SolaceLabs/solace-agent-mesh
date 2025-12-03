# Model Configuration

Defines Large Language Model (LLM) configurations used by agents. Agent Mesh uses [LiteLLM](https://litellm.ai/) for unified access to multiple AI model providers.

## Overview

Model configuration enables:
- **Multi-Provider Support** - OpenAI, Anthropic, Google, AWS, Azure, and more
- **Unified Interface** - Consistent API across all providers
- **Flexible Deployment** - Switch providers without code changes
- **Cost Optimization** - Use different models for different tasks

## Configuration Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | String | Yes | - | Model identifier (e.g., `openai/gpt-4`) |
| `api_key` | String | Yes | - | API key for authentication |
| `api_base` | String | No | Provider default | API endpoint URL |
| `temperature` | Float | No | 0.7 | Sampling temperature (0.0-2.0) |
| `max_tokens` | Integer | No | Provider default | Maximum tokens in response |
| `top_p` | Float | No | 1.0 | Nucleus sampling parameter |
| `frequency_penalty` | Float | No | 0.0 | Frequency penalty (-2.0 to 2.0) |
| `presence_penalty` | Float | No | 0.0 | Presence penalty (-2.0 to 2.0) |
| `timeout` | Integer | No | 600 | Request timeout in seconds |

## Model Types

Standard model aliases for different use cases:

| Alias | Purpose | Recommended Models | Temperature |
|-------|---------|-------------------|-------------|
| `planning_model` | Complex reasoning, task planning | GPT-4, Claude Opus | 0.1-0.3 |
| `general_model` | Standard agent tasks | GPT-3.5, Claude Sonnet | 0.5-0.7 |
| `multimodal_model` | Image/audio processing | GPT-4 Vision, Gemini Pro Vision | 0.5 |
| `image_generation_model` | Image creation | DALL-E, Stable Diffusion | N/A |
| `audio_transcription_model` | Speech-to-text | Whisper | N/A |

## Basic Configuration

### Single Model

```yaml
model:
  model: "openai/gpt-3.5-turbo"
  api_key: "${OPENAI_API_KEY}"
  temperature: 0.7
  max_tokens: 2048
```

### Multiple Models in Shared Config

```yaml
shared_config:
  - models:
      planning_model: &planning_model
        model: "openai/gpt-4"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.3
        max_tokens: 4096
      
      general_model: &general_model
        model: "openai/gpt-3.5-turbo"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.7
        max_tokens: 2048
      
      multimodal_model: &multimodal_model
        model: "gemini/gemini-1.5-pro"
        api_key: "${GEMINI_API_KEY}"
        temperature: 0.5
```

## Provider-Specific Configuration

### OpenAI

```yaml
model:
  model: "openai/gpt-4"
  api_key: "${OPENAI_API_KEY}"
  temperature: 0.7
  max_tokens: 4096
  top_p: 1.0
  frequency_penalty: 0.0
  presence_penalty: 0.0
```

**Available Models**:
- `openai/gpt-4` - Most capable model
- `openai/gpt-4-turbo` - Faster GPT-4
- `openai/gpt-3.5-turbo` - Fast and cost-effective
- `openai/gpt-4-vision-preview` - Multimodal (text + images)

### Anthropic Claude

```yaml
model:
  model: "anthropic/claude-3-opus-20240229"
  api_key: "${ANTHROPIC_API_KEY}"
  temperature: 0.5
  max_tokens: 4096
```

**Available Models**:
- `anthropic/claude-3-opus-20240229` - Most capable
- `anthropic/claude-3-sonnet-20240229` - Balanced performance
- `anthropic/claude-3-haiku-20240307` - Fast and efficient

### Google Gemini

```yaml
model:
  model: "gemini/gemini-1.5-pro"
  api_key: "${GEMINI_API_KEY}"
  temperature: 0.7
```

**Available Models**:
- `gemini/gemini-1.5-pro` - Advanced reasoning
- `gemini/gemini-1.5-flash` - Fast responses
- `gemini/gemini-pro-vision` - Multimodal

### AWS Bedrock

```yaml
model:
  model: "bedrock/anthropic.claude-v2"
  aws_access_key_id: "${AWS_ACCESS_KEY_ID}"
  aws_secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
  aws_region_name: "us-east-1"
```

**Available Models**:
- `bedrock/anthropic.claude-v2`
- `bedrock/anthropic.claude-3-sonnet-20240229-v1:0`
- `bedrock/amazon.titan-text-express-v1`

### Azure OpenAI

```yaml
model:
  model: "azure/gpt-4"
  api_key: "${AZURE_API_KEY}"
  api_base: "${AZURE_API_BASE}"
  api_version: "2024-02-15-preview"
  azure_deployment: "gpt-4-deployment"
```

### Ollama (Local Models)

```yaml
model:
  model: "ollama/llama2"
  api_base: "http://localhost:11434"
```

**Available Models**:
- `ollama/llama2`
- `ollama/mistral`
- `ollama/codellama`

## Temperature Guidelines

Temperature controls randomness in model outputs:

| Temperature | Behavior | Use Case |
|-------------|----------|----------|
| 0.0 - 0.3 | Deterministic, focused | Planning, code generation, structured output |
| 0.4 - 0.7 | Balanced | General conversation, Q&A |
| 0.8 - 1.0 | Creative, diverse | Creative writing, brainstorming |
| 1.1 - 2.0 | Very creative | Experimental, highly creative tasks |

## Complete Examples

### Production Configuration

```yaml
shared_config:
  - models:
      # High-quality model for orchestration and planning
      planning_model: &planning_model
        model: "openai/gpt-4"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.2
        max_tokens: 4096
        timeout: 120
      
      # Cost-effective model for general tasks
      general_model: &general_model
        model: "openai/gpt-3.5-turbo"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.7
        max_tokens: 2048
        timeout: 60
      
      # Multimodal model for image understanding
      multimodal_model: &multimodal_model
        model: "gemini/gemini-1.5-pro"
        api_key: "${GEMINI_API_KEY}"
        temperature: 0.5
        max_tokens: 2048
      
      # Image generation
      image_generation_model: &image_generation_model
        model: "openai/dall-e-3"
        api_key: "${OPENAI_API_KEY}"
      
      # Audio transcription
      audio_transcription_model: &audio_transcription_model
        model: "openai/whisper-1"
        api_key: "${OPENAI_API_KEY}"
```

### Multi-Provider Configuration

```yaml
shared_config:
  - models:
      # OpenAI for general tasks
      general_model: &general_model
        model: "openai/gpt-3.5-turbo"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.7
      
      # Claude for complex reasoning
      planning_model: &planning_model
        model: "anthropic/claude-3-opus-20240229"
        api_key: "${ANTHROPIC_API_KEY}"
        temperature: 0.3
      
      # Gemini for multimodal
      multimodal_model: &multimodal_model
        model: "gemini/gemini-1.5-pro"
        api_key: "${GEMINI_API_KEY}"
        temperature: 0.5
```

### Cost-Optimized Configuration

```yaml
shared_config:
  - models:
      # Use GPT-3.5 for most tasks
      general_model: &general_model
        model: "openai/gpt-3.5-turbo"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.7
        max_tokens: 1024  # Limit tokens to reduce cost
      
      # Reserve GPT-4 only for complex planning
      planning_model: &planning_model
        model: "openai/gpt-4"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.3
        max_tokens: 2048
```

## Using Models in Agents

### Reference Shared Model

```yaml
!include shared_config.yaml

components:
  - name: my-agent
    app_config:
      model: *general_model  # Reference shared model
```

### Override Model Settings

```yaml
!include shared_config.yaml

components:
  - name: creative-agent
    app_config:
      model:
        <<: *general_model
        temperature: 1.2  # Override for more creativity
```

### Agent-Specific Model

```yaml
components:
  - name: specialized-agent
    app_config:
      model:
        model: "anthropic/claude-3-opus-20240229"
        api_key: "${ANTHROPIC_API_KEY}"
        temperature: 0.5
```

## Environment Variables

### OpenAI

```bash
export OPENAI_API_KEY="sk-..."
```

### Anthropic

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Google Gemini

```bash
export GEMINI_API_KEY="..."
```

### AWS Bedrock

```bash
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"
```

### Azure OpenAI

```bash
export AZURE_API_KEY="..."
export AZURE_API_BASE="https://your-resource.openai.azure.com"
```

## Best Practices

### 1. Use Appropriate Models for Tasks

Match model capabilities to task requirements:
- **Simple tasks**: GPT-3.5, Claude Haiku
- **Complex reasoning**: GPT-4, Claude Opus
- **Multimodal**: GPT-4 Vision, Gemini Pro Vision
- **Cost-sensitive**: GPT-3.5, Claude Haiku

### 2. Set Reasonable Token Limits

```yaml
model:
  model: "openai/gpt-4"
  max_tokens: 2048  # Prevent excessive costs
```

### 3. Adjust Temperature by Use Case

```yaml
# Deterministic tasks (code, structured data)
temperature: 0.2

# General conversation
temperature: 0.7

# Creative tasks
temperature: 1.0
```

### 4. Use Environment Variables for Keys

```yaml
# Good
api_key: "${OPENAI_API_KEY}"

# Bad - Never hardcode
api_key: "sk-actual-key-here"
```

### 5. Configure Timeouts

```yaml
model:
  model: "openai/gpt-4"
  timeout: 120  # Prevent hanging requests
```

### 6. Monitor Costs

- Track token usage per model
- Set up billing alerts
- Use cheaper models where appropriate
- Implement rate limiting

## Troubleshooting

### Authentication Failed

**Error**: `Invalid API key` or `Authentication failed`

**Solutions**:
1. Verify API key is correct
2. Check environment variable is set
3. Ensure API key has not expired
4. Verify API key has required permissions

### Rate Limit Exceeded

**Error**: `Rate limit exceeded` or `Too many requests`

**Solutions**:
1. Implement exponential backoff
2. Reduce request frequency
3. Upgrade API plan
4. Use multiple API keys with load balancing

### Model Not Found

**Error**: `Model not found` or `Invalid model`

**Solutions**:
1. Verify model identifier is correct
2. Check model is available in your region
3. Ensure you have access to the model
4. Review LiteLLM supported models list

### Timeout Errors

**Error**: `Request timeout` or `Connection timeout`

**Solutions**:
1. Increase timeout value
2. Check network connectivity
3. Verify API endpoint is accessible
4. Try different API base URL

### Token Limit Exceeded

**Error**: `Maximum context length exceeded`

**Solutions**:
1. Reduce input text length
2. Increase `max_tokens` if possible
3. Use a model with larger context window
4. Implement text chunking strategy

## Performance Optimization

### Response Time

- Use faster models (GPT-3.5, Claude Haiku) for simple tasks
- Set appropriate `max_tokens` limits
- Consider streaming responses for long outputs

### Cost Optimization

- Use cheaper models where quality difference is minimal
- Implement caching for repeated queries
- Set token limits to prevent overuse
- Monitor and analyze usage patterns

### Quality Optimization

- Use higher-quality models for critical tasks
- Adjust temperature for desired output style
- Provide clear, detailed prompts
- Implement output validation

## Related Documentation

- [Shared Configuration](./shared-configuration.md) - Defining models in shared config
- [Agent Configuration](./agent-configuration.md) - Using models in agents
- [Environment Variables](./environment-variables.md) - Model-related environment variables
- [Best Practices](./best-practices.md) - Model configuration best practices

## External Resources

- [LiteLLM Documentation](https://docs.litellm.ai/)
- [LiteLLM Supported Providers](https://docs.litellm.ai/docs/providers)
- [OpenAI Models](https://platform.openai.com/docs/models)
- [Anthropic Models](https://docs.anthropic.com/claude/docs/models-overview)
- [Google AI Models](https://ai.google.dev/models)