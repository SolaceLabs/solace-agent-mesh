---
title: Token Usage Breakdown
sidebar_position: 345
---

# Token Usage Breakdown

Understanding token usage in Agent Mesh helps you estimate costs and optimize your LLM configurations. This page provides a breakdown of what gets sent to the LLM on each request and explains how prompt caching can reduce costs.

:::info Approximate Token Counts
The token counts in this document are approximate estimates based on a typical Orchestrator Agent configuration. Actual token counts vary based on your specific configuration, the LLM provider's tokenizer, custom instructions, the number of peer agents discovered, and the tools enabled. You can run `python scripts/calculate_token_usage.py` to calculate token counts for your specific setup.
:::

## Components Sent to the LLM

Each LLM request in Agent Mesh consists of several components that contribute to the total token count. The system instruction and tool definitions are cacheable, while conversation history and user messages are sent fresh with each request.

### System Instruction

The system instruction is the largest component and consists of multiple parts. The following table shows approximate token counts for a typical Orchestrator Agent configuration:

| Component | Approximate Tokens | Description |
|-----------|-------------------|-------------|
| Base Agent Instruction | ~250-300 | Your custom agent instruction from YAML config |
| Planning Instruction | ~500 | Parallel tool calling and response formatting rules |
| Artifact Instructions | ~600-700 | Instructions for creating text-based artifacts |
| Inline Template Instruction | ~400-450 | Liquid template syntax for data rendering |
| Fenced Block Syntax Rules | ~400 | Syntax rules for artifact blocks |
| Embed Instruction | ~1,100-1,200 | Dynamic embeds including math, datetime, and artifact_content |
| Conversation Flow Instruction | ~400-450 | Response formatting and status update guidelines |
| Examples Instruction | ~800-900 | Usage examples for artifacts and templates |
| Peer Agent Instructions | ~50-100 per agent | Instructions for discovered peer agents |

The total system instruction typically uses 4,000-5,000 tokens depending on your configuration.

### Tool Definitions

Tool definitions are converted to OpenAPI-style function declarations. The built-in tools consume approximately 500-600 tokens across 8 tools:

| Tool | Approximate Tokens | Description |
|------|-------------------|-------------|
| `create_artifact` | ~120-130 | Creates a new artifact with content |
| `list_artifacts` | ~40-50 | Lists all artifacts in session |
| `load_artifact` | ~75-85 | Loads artifact content |
| `signal_artifact_for_return` | ~80-90 | Signals artifact for user return |
| `delete_artifact` | ~55-65 | Deletes an artifact |
| `jq_query` | ~75-85 | Executes jq query on JSON |
| `sql_query` | ~80-90 | Executes SQL on tabular data |
| `get_current_time` | ~40-50 | Gets current date and time |

Peer agent tools add approximately 80-130 tokens per agent depending on the agent's description and capabilities. With 3 peer agents, the tool definitions consume approximately 250-350 additional tokens.

The total tool definitions typically use 800-1,000 tokens depending on the number of tools and peer agents.

### Conversation History

Conversation history grows with each turn and is not currently cached. The token usage varies based on message content:

| Message Type | Typical Tokens | Notes |
|--------------|---------------|-------|
| User Message | 50-500 | Depends on user input length |
| Assistant Response | 100-2,000 | Depends on response complexity |
| Tool Call | 30-100 | Function name and arguments |
| Tool Response | 50-5,000 | Depends on tool output size |

### User Message

The current user message is always sent fresh and cannot be cached because it is unique for each request.

## Prompt Caching

LLM prompt caching stores content that appears at the beginning of the prompt and remains identical across requests. Agent Mesh marks the system instruction and tool definitions for caching, which reduces costs on subsequent requests.

The following table shows what gets cached in Agent Mesh:

| Component | Cached | Reason |
|-----------|--------|--------|
| System Instruction | Yes | Marked with `cache_control` and stable across requests |
| Tool Definitions | Yes | Last tool marked with `cache_control` and stable across requests |
| Conversation History | No | Not currently marked for caching |
| Current User Message | No | Always unique and cannot be cached |

:::info Conversation History Caching
The conversation history up to but not including the latest turn is identical to what was sent in the previous request. This means it could be cached using incremental cache breakpoints.

Agent Mesh currently adds `cache_control` to the system instruction and the last tool, which caches approximately 5,000-6,000 tokens. LiteLLM supports automatic cache control injection via `cache_control_injection_points`. You could configure this in your LiteLLM config:

```yaml
# In litellm config.yaml
model_list:
  - model_name: claude-with-history-caching
    litellm_params:
      model: anthropic/claude-sonnet-4-5-20250929
      cache_control_injection_points:
        - location: message
          role: system
        - location: message
          index: -2  # Second-to-last message (history prefix)
```

This configuration caches the conversation history prefix automatically. Anthropic allows a maximum of 4 cache breakpoints per request. For more information, see [LiteLLM Auto-Inject Prompt Caching documentation](https://docs.litellm.ai/docs/completion/prompt_caching#auto-inject-prompt-caching-checkpoints).
:::

### How Caching Works

The LLM provider caches content from the start of the prompt. For Anthropic, content must be marked with `cache_control`, while OpenAI caches automatically when prompts exceed 1,024 tokens. The cache is invalidated if any content before a cache breakpoint changes. Multiple cache breakpoints can be used for incremental caching.

Agent Mesh sends requests in this order: system instruction (cached), tool definitions (cached), conversation history (not cached), and user message (not cached).

:::note Provider-Specific Behavior
LiteLLM supports prompt caching for these providers using the OpenAI-compatible usage format:

| Provider | Model Prefix | Caching Type | Notes |
|----------|--------------|--------------|-------|
| OpenAI | `openai/` | Automatic | Prompts over 1,024 tokens cached automatically |
| Anthropic | `anthropic/` | Explicit | Requires `cache_control: {"type": "ephemeral"}` markers |
| AWS Bedrock | `bedrock/`, `bedrock/converse/` | Explicit | All models Bedrock supports prompt caching on |
| Vertex AI (Gemini) | `vertex_ai/` | Explicit | Supports `cache_control: {"type": "ephemeral"}` markers like Anthropic |

:::

## Token Usage Summary

The following summary shows approximate token usage for a typical Orchestrator Agent:

| Component | Approximate Tokens |
|-----------|-------------------|
| System Instruction (all components) | ~4,500 |
| Built-in Tool Definitions (8 tools) | ~600 |
| Peer Agent Tool Definitions (3 agents) | ~300 |
| Total Cacheable | ~5,400 |

Non-cacheable components vary based on usage:

| Component | Typical Tokens |
|-----------|---------------|
| User Message | 50-500 |
| Conversation History (per turn) | 100-2,000 |
| Tool Responses | 50-5,000 |

## Cost Estimation

This section uses Claude Sonnet 4.5 pricing as of late 2025 for illustration. Input tokens cost $3 per million tokens ($0.003/1K), cached input tokens cost $0.30 per million tokens ($0.0003/1K) representing a 90% discount, and output tokens cost $15 per million tokens ($0.015/1K).

### First Request

On the first request, a cache miss occurs and the content is stored for future requests:

| Component | Approximate Tokens | Rate | Approximate Cost |
|-----------|-------------------|------|------------------|
| System Instruction | ~4,500 | $0.003/1K | ~$0.014 |
| Tool Definitions | ~900 | $0.003/1K | ~$0.003 |
| User Message | ~100 | $0.003/1K | ~$0.000 |
| Total Input | ~5,500 | — | ~$0.017 |
| Output (typical response) | ~500 | $0.015/1K | ~$0.008 |
| Total Cost | — | — | ~$0.025 |

### Subsequent Requests

On subsequent requests, cached content is served at the discounted rate:

| Component | Approximate Tokens | Rate | Approximate Cost |
|-----------|-------------------|------|------------------|
| Cached Content (system + tools) | ~5,400 | $0.0003/1K | ~$0.002 |
| Conversation History | ~500 | $0.003/1K | ~$0.002 |
| User Message | ~100 | $0.003/1K | ~$0.000 |
| Total Input | ~6,000 | — | ~$0.004 |
| Output (typical response) | ~500 | $0.015/1K | ~$0.008 |
| Total Cost | — | — | ~$0.012 |

The savings compared to the first request is approximately 50-55%.

### Cost Comparison

| Scenario | Approximate Input Cost | Output Cost | Approximate Total | Savings |
|----------|----------------------|-------------|-------------------|---------|
| First request (cache miss) | ~$0.017 | ~$0.008 | ~$0.025 | — |
| Subsequent request (cache hit) | ~$0.004 | ~$0.008 | ~$0.012 | ~50% |
| 10 requests (1 miss + 9 hits) | ~$0.053 | ~$0.080 | ~$0.133 | ~45% vs no cache |

:::tip Cost Optimization
For high-frequency agents, prompt caching can reduce input token costs by up to 90% on cache hits. The system instruction and tool definitions (approximately 5,000-6,000 tokens representing 85-90% of base input) are cached, while only conversation history and user messages are charged at full rate. Pricing varies by provider and model, so check your provider's current pricing for accurate cost estimates.
:::

## Token Usage by Agent Type

Different agent configurations have different token overhead. The following examples show typical usage patterns.

An Orchestrator Agent with full features uses approximately 4,500 tokens for the system instruction and 900 tokens for tool definitions (8 built-in tools plus 3 peer agents), resulting in a base overhead of approximately 5,400 tokens per request.

A specialized agent with minimal features uses approximately 2,000-2,500 tokens for the system instruction (with fewer instructions enabled) and 200-400 tokens for tool definitions (2-3 specific tools), resulting in a base overhead of approximately 2,500-3,000 tokens per request.

An agent with MCP tools uses approximately 4,500 tokens for the system instruction and 1,500-3,000 tokens for tool definitions (MCP tools can be verbose), resulting in a base overhead of approximately 6,000-7,500 tokens per request.

## Factors Affecting Token Usage

Several configuration options affect token usage. The following options increase token consumption:

| Configuration | Approximate Impact | Recommendation |
|--------------|-------------------|----------------|
| `enable_embed_resolution: true` | +800-1,000 tokens | Keep enabled for artifact support |
| `enable_artifact_content_instruction: true` | +300-500 tokens | Disable if not using artifact_content embeds |
| `agent_discovery: enabled: true` | +150-250 tokens per peer | Limit peer agents via allow_list |
| Large custom instruction | Variable | Keep instructions concise |

The following options reduce token consumption:

| Configuration | Approximate Impact | Recommendation |
|--------------|-------------------|----------------|
| `enable_embed_resolution: false` | -800-1,000 tokens | Only if not using embeds |
| `agent_discovery: enabled: false` | Removes peer overhead | For isolated agents |
| Minimal tool configuration | -50-150 per tool | Only include needed tools |

## Monitoring Token Usage

Agent Mesh tracks token usage per task and reports it in the final task metadata:

```json
{
  "token_usage": {
    "total_tokens": 6150,
    "total_input_tokens": 5650,
    "total_output_tokens": 500,
    "total_cached_input_tokens": 5600,
    "llm_calls": 1
  }
}
```

Token usage is available in LLM response callbacks where each LLM call reports individual usage.

## Optimizing Token Usage

You can optimize token usage by configuring appropriate cache strategies based on usage patterns. Use `cache_strategy: "5m"` for high-frequency agents that make 10 or more calls per hour, `cache_strategy: "1h"` for burst patterns with 3-10 calls per hour, or `cache_strategy: "none"` for rarely-used agents with fewer than 2 calls per hour:

```yaml
model:
  cache_strategy: "5m"  # For high-frequency agents (10+ calls/hour)
  # cache_strategy: "1h"  # For burst patterns (3-10 calls/hour)
  # cache_strategy: "none"  # For rarely-used agents (<2 calls/hour)
```

Keep custom instructions focused and concise. A good instruction is direct and specific:

```yaml
# Good: Focused instruction
instruction: |
  You are a data analysis agent. Analyze CSV and JSON files using the provided tools.
  Save results as artifacts when requested.

# Avoid: Verbose instruction with redundant information
instruction: |
  You are a helpful AI assistant that specializes in data analysis...
  [500+ words of detailed instructions that duplicate system capabilities]
```

Use allow_list to control which peer agents are visible:

```yaml
inter_agent_communication:
  allow_list: ["DataAgent", "ReportAgent"]  # Only specific agents
  # allow_list: ["*"]  # All agents (higher token usage)
```

Only include tools the agent actually needs:

```yaml
tools:
  - tool_type: builtin-group
    group_name: "artifact_management"  # Include if agent creates files
  # Avoid including unused tool groups
```

## Illustrative Example

:::note Rough Illustration
This example is for rough illustration purposes only. Actual token counts vary based on your specific configuration, the LLM provider's tokenizer, and the tools and agents available in your deployment.
:::

### Scenario: User asks "What is the weather in Toronto?"

The following breakdown shows approximately what gets sent to the LLM for this simple question:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         REQUEST TO LLM                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ 1. SYSTEM INSTRUCTION (role: "developer")                   ~4,500 tokens │    │
│  │    ┌─────────────────────────────────────────────────────────────────┐  │    │
│  │    │ • Base Agent Instruction                          ~250 tokens   │  │    │
│  │    │ • Planning Instruction                            ~500 tokens   │  │    │
│  │    │ • Artifact Instructions                           ~650 tokens   │  │    │
│  │    │ • Inline Template Instruction                     ~450 tokens   │  │    │
│  │    │ • Fenced Block Syntax Rules                       ~400 tokens   │  │    │
│  │    │ • Embed Instruction                             ~1,150 tokens   │  │    │
│  │    │ • Conversation Flow Instruction                   ~450 tokens   │  │    │
│  │    │ • Examples Instruction                            ~850 tokens   │  │    │
│  │    │ • Peer Agent Instructions (varies by agents)      ~250 tokens   │  │    │
│  │    └─────────────────────────────────────────────────────────────────┘  │    │
│  │    [cache_control: {"type": "ephemeral"}]  ← CACHED                     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ 2. TOOL DEFINITIONS                                        ~900 tokens │    │
│  │    ┌─────────────────────────────────────────────────────────────────┐  │    │
│  │    │ Built-in Tools (8):                                  ~600 tokens │  │    │
│  │    │   • create_artifact, list_artifacts, load_artifact              │  │    │
│  │    │   • signal_artifact_for_return, delete_artifact                 │  │    │
│  │    │   • jq_query, sql_query, get_current_time                       │  │    │
│  │    │                                                                 │  │    │
│  │    │ Peer Agent Tools (varies):                           ~300 tokens │  │    │
│  │    │   • peer_MarkitdownAgent, peer_WebAgent, peer_MermaidAgent      │  │    │
│  │    └─────────────────────────────────────────────────────────────────┘  │    │
│  │    [cache_control: {"type": "ephemeral"}] on last tool  ← CACHED        │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │ 3. USER MESSAGE (role: "user")                               ~10 tokens │    │
│  │    "What is the weather in Toronto?"                                    │    │
│  │    [NOT CACHED - unique each request]                                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│ TOTAL INPUT TOKENS:                                           ~5,400 tokens     │
│   • Cached (system + tools):                                  ~5,400 tokens     │
│   • Non-cached (user message):                                   ~10 tokens     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Cost Calculation

Using Claude Sonnet 4.5 pricing as of late 2025:

| Component | Approximate Tokens | Rate | Approximate Cost |
|-----------|-------------------|------|------------------|
| Cached input | ~5,400 | $0.30/1M | ~$0.0016 |
| Non-cached input | ~10 | $3.00/1M | ~$0.00003 |
| Output | ~150 | $15.00/1M | ~$0.0023 |
| Total | — | — | ~$0.004 |

Without caching, the same request would cost approximately $0.016 for input plus $0.002 for output, totaling approximately $0.018. The savings from caching is approximately 75-80%.

### Multi-Turn Conversation Example

As the conversation continues, history accumulates:

Turn 1 with the question "What is the weather in Toronto?" uses approximately 5,400 input tokens (5,400 cached plus 10 new) and generates approximately 150 output tokens.

Turn 2 with the question "What about tomorrow?" uses approximately 5,600 input tokens (5,400 cached plus 160 history plus 10 new) and generates approximately 120 output tokens.

Turn 3 with the question "Should I bring an umbrella?" uses approximately 5,700 input tokens (5,400 cached plus 290 history plus 10 new) and generates approximately 80 output tokens.

Currently, conversation history is not cached. Only the system instruction and tool definitions benefit from caching. This means the history portion is charged at full rate.

### Provider-Specific Caching Behavior

| Provider | Model Prefix | Caching Type | How It Works |
|----------|--------------|--------------|--------------|
| OpenAI | `openai/` | Automatic | Caches prompts over 1,024 tokens automatically with no markers needed |
| Anthropic | `anthropic/` | Explicit | Requires `cache_control: {"type": "ephemeral"}` markers which Agent Mesh adds automatically; Anthropic charges for cache writes via `cache_creation_input_tokens` |
| AWS Bedrock | `bedrock/`, `bedrock/converse/` | Explicit | LiteLLM translates cache markers for Bedrock-hosted Anthropic models |
| Vertex AI (Gemini) | `vertex_ai/` | Explicit | Supports `cache_control: {"type": "ephemeral"}` markers like Anthropic; Agent Mesh cache markers work automatically |

## Related Documentation

For more information about LLM provider configuration and prompt caching, see [Configuring LLMs](./large_language_models.md). For agent-specific settings, see [Agent Configuration](./agent-configuration.md). For overall configuration structure, see [Configurations](./configurations.md).