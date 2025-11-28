---
title: Context Management
sidebar_position: 1
---

# Context Management

Agent Mesh provides features for managing LLM context efficiently, helping you monitor token consumption and optimize long conversations. These capabilities are particularly valuable when working with large language models that have context window limitations.

## Tracking Token Usage

When you interact with LLM-powered agents, each request consumes tokens from the model's context window. Token usage tracking allows you to monitor this consumption in real time, providing visibility into prompt tokens, completion tokens, and cached tokens. You can view usage statistics in the web UI and access detailed breakdowns by session or time period. The tracking system also supports cost estimation based on model pricing, helping you understand the operational costs of your agent deployments. For configuration options and implementation details, see [Token Usage Tracking](./token-usage-tracking.md).

## Compressing Conversation Context

Long conversations can exhaust the available context window, limiting the model's ability to process new information. Context compression addresses this by generating LLM-powered summaries of conversation history and creating a new session with the compressed context. This approach preserves the essential information from previous exchanges while freeing up context space for continued interaction. The compression feature supports multiple LLM providers and includes fallback mechanisms for reliability. For guidance on using context compression, see [Context Compression](./context-compression.md).

## Prompt Caching

Many LLM providers support prompt caching, which stores frequently used prompt content to reduce latency and costs. Agent Mesh integrates with provider-specific caching mechanisms through the LiteLLM wrapper, allowing you to configure cache strategies for system instructions and tool definitions. When caching is enabled, subsequent requests with identical cached content can benefit from faster response times and reduced token charges. For cache configuration options, see [Prompt Caching](./prompt-caching.md).