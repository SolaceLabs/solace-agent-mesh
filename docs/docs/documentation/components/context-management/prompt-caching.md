---
title: Prompt Caching
sidebar_position: 4
---

# Prompt Caching

Prompt caching reduces latency and costs by storing frequently used prompt content at the LLM provider level. When you send requests with identical cached content, the provider can serve responses faster and often at reduced token charges.

## How Prompt Caching Works

LLM providers like Anthropic and OpenAI support caching mechanisms that store prompt prefixes for reuse across requests. Agent Mesh integrates with these mechanisms through the LiteLLM wrapper, which adds cache control headers to system instructions and tool definitions.

When caching is enabled:

1. The LiteLLM wrapper adds `cache_control` metadata to cacheable content
2. The LLM provider stores the cached content for the configured duration
3. Subsequent requests with identical cached content benefit from faster processing
4. The provider may charge reduced rates for cached tokens

## Configuring Cache Strategy

You can configure the cache strategy at the model level using the `cache_strategy` parameter:

```yaml
# In shared_config.yaml or agent config
llm_config:
  model: claude-sonnet-4-5
  api_base: ${LLM_SERVICE_ENDPOINT}
  api_key: ${LLM_SERVICE_API_KEY}
  cache_strategy: "5m"
```

### Available Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `"none"` | Caching disabled | When you need fresh processing for every request |
| `"5m"` | 5-minute ephemeral cache (default) | Standard interactive sessions |
| `"1h"` | 1-hour extended cache | Long-running sessions or batch processing |

The default strategy is `"5m"`, which provides a balance between cache benefits and freshness for typical interactive use cases.

## What Gets Cached

Agent Mesh applies cache control to two types of content:

### System Instructions

System instructions define the agent's behavior and are typically identical across requests within a session. The cache control is applied to the entire system instruction block:

```yaml
# Example system instruction caching
system_instruction: "You are a helpful assistant with access to tools."
# With cache_strategy: "5m", this becomes:
# {
#   "type": "text",
#   "text": "You are a helpful assistant...",
#   "cache_control": {"type": "ephemeral"}
# }
```

### Tool Definitions

Tool definitions describe the available functions an agent can call. Because Agent Mesh sorts peer agents alphabetically, tool definitions remain stable across requests, making them good candidates for caching.

Cache control is applied to the last tool in the list, which signals to the provider that all preceding tools should also be cached:

```yaml
# With multiple tools, cache_control is added to the last one
tools:
  - tool1  # No cache_control
  - tool2  # No cache_control
  - tool3  # cache_control: {"type": "ephemeral"}
```

## Provider Support

Prompt caching support varies by LLM provider:

| Provider | Caching Support | Notes |
|----------|-----------------|-------|
| Anthropic (Claude) | Full support | Native ephemeral caching |
| OpenAI | Supported | Requires specific model versions |
| Google (Gemini) | Limited | Varies by model |
| Bedrock | Supported | Through Anthropic models |
| Deepseek | Supported | Through LiteLLM translation |

LiteLLM handles the translation of cache control headers to provider-specific formats, so you can use the same configuration across different providers.

## Monitoring Cache Effectiveness

When token usage tracking is enabled, you can monitor cache effectiveness through the cached tokens metric. A high ratio of cached tokens to total prompt tokens indicates effective caching.

To enable cached token tracking:

```yaml
llm_config:
  model: claude-sonnet-4-5
  cache_strategy: "5m"
  track_token_usage: true
```

The cached token count appears in:

- The context usage indicator in the chat interface
- The Usage Details page
- API responses from token usage endpoints

## Best Practices

### Stable System Instructions

Design system instructions that remain constant across requests. Avoid including dynamic content like timestamps or session-specific data in the system instruction, as this prevents effective caching.

### Consistent Tool Ordering

Agent Mesh automatically sorts peer agents alphabetically to ensure consistent tool ordering. If you define custom tools, maintain a consistent order to maximize cache hits.

### Appropriate Cache Duration

Choose a cache strategy that matches your usage pattern:

- Use `"5m"` for interactive sessions where users may switch contexts frequently
- Use `"1h"` for batch processing or long-running automated tasks
- Use `"none"` when you need to ensure fresh processing for every request

### Monitor Cache Metrics

Regularly review cached token metrics to understand cache effectiveness. If cached tokens are consistently low despite caching being enabled, investigate whether your prompts contain dynamic content that prevents caching.

## Troubleshooting

### Cached Tokens Always Zero

If cached tokens are always reported as zero:

1. Verify that `cache_strategy` is not set to `"none"`
2. Check that your LLM provider supports prompt caching
3. Ensure your prompts meet the provider's minimum length requirements for caching
4. Verify that `track_token_usage: true` is set to see cached token metrics

### Cache Not Reducing Costs

If you do not see cost reductions from caching:

1. Verify that your provider charges reduced rates for cached tokens
2. Check that requests are being made within the cache duration window
3. Ensure system instructions and tools are identical across requests

### Invalid Cache Strategy Warning

If you see a warning about invalid cache strategy:

1. Check that `cache_strategy` is set to one of: `"none"`, `"5m"`, or `"1h"`
2. The system defaults to `"5m"` when an invalid strategy is specified