---
title: Context Compression
sidebar_position: 3
---

# Context Compression

Context compression allows you to continue long conversations without losing context when approaching the model's token limit. The feature generates an LLM-powered summary of your conversation history and creates a new session with the compressed context, preserving the essential information while freeing up space for continued interaction.

## How Context Compression Works

When you compress a conversation, Agent Mesh performs the following steps:

1. Retrieves all messages from the current session
2. Sends the conversation history to an LLM for summarization
3. Creates a new session with compression metadata linking it to the original
4. Adds the generated summary as the first message in the new session
5. Navigates you to the new session where you can continue the conversation

The compression process tracks token usage for the summarization LLM call, counting it toward your usage quota.

## Using Context Compression

### Trigger Conditions

The compression button appears in the context usage indicator when either of these conditions is met:

- The session contains 15 or more messages
- Token usage exceeds 70% of the model's context limit

These thresholds ensure that compression is available when it would provide meaningful benefit without being offered prematurely for short conversations.

### Compressing a Conversation

To compress a conversation:

1. Open the context usage indicator in the chat interface (click the token usage display)
2. When the threshold conditions are met, a "Compress & Continue" button appears
3. Click the button to initiate compression
4. Wait for the summary to be generated (a loading indicator shows progress)
5. The system automatically navigates you to the new session with the compressed context

After compression, you can continue your conversation with the full context of previous exchanges preserved in the summary.

## Configuration

### LLM Provider Selection

Context compression supports multiple LLM providers for generating summaries. The system attempts to use providers in the following order based on available API keys:

1. OpenAI (default model: `gpt-4o-mini`)
2. Anthropic (default model: `claude-3-5-sonnet-20241022`)
3. Gemini (default model: `gemini-1.5-flash`)

You can configure the compression LLM through environment variables:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

### Component Configuration

For more control over compression behavior, you can add a compression section to your gateway configuration:

```yaml
compression:
  enabled: true
  summarization:
    model: "gpt-4o-mini"
    anthropic_model: "claude-3-5-sonnet-20241022"
    gemini_model: "gemini-1.5-flash"
    temperature: 0.3
    max_tokens: 1000
```

## Fallback Behavior

If the LLM API call fails during compression, the system falls back to a structured summary that:

- Preserves the first and last message previews
- Extracts topics using keyword analysis
- Lists any artifacts created during the session
- Provides a basic conversation timeline

This fallback ensures that compression remains available even when LLM services are temporarily unavailable.

## Database Requirements

Context compression requires database persistence for session data. Ensure your session service is configured to use SQL storage:

```yaml
session_service:
  type: sql
```

The compression feature adds two columns to the sessions table:

- `is_compression_branch`: Boolean flag indicating the session was created through compression
- `compression_metadata`: JSON field containing information about the original session and compression parameters

To apply the required schema changes, run the database migration:

```bash
cd src/solace_agent_mesh/gateway/http_sse
alembic upgrade head
```

## Token Usage and Costs

Compression LLM calls are tracked in your token usage with the source marked as "compression". The context field includes the session ID that was compressed, allowing you to identify compression-related usage in your reports.

Approximate costs per compression:

| Provider | Model | Estimated Cost |
|----------|-------|----------------|
| OpenAI | gpt-4o-mini | $0.01–$0.05 |
| Anthropic | claude-3-5-sonnet | $0.02–$0.08 |
| Google | gemini-1.5-flash | $0.005–$0.02 |

Compression typically achieves 50–90% token reduction, making it cost-effective for long conversations that would otherwise require starting fresh.

## Viewing Compression History

Sessions created through compression maintain a link to their original session through the compression metadata. You can identify compressed sessions by the summary message that appears at the start of the conversation, which includes:

- A header indicating the session is a continuation
- The generated summary of previous context
- Information about any artifacts from the original session
- Token savings achieved through compression

## Troubleshooting

### Compression Button Not Appearing

If the compression button does not appear:

1. Verify the session has at least 15 messages or 70% token usage
2. Ensure the context usage indicator is expanded (click to expand)
3. Check that token usage tracking is enabled in your configuration

### Compression Fails

If compression fails with an error:

1. Check that at least one LLM provider API key is configured
2. Verify network connectivity to the LLM provider
3. Review the server logs for detailed error messages
4. The system should fall back to structured summary if LLM calls fail

### Summary Quality Issues

If the generated summary does not capture the conversation adequately:

1. Consider using a more capable model for summarization
2. Adjust the `temperature` parameter (lower values produce more focused summaries)
3. Increase `max_tokens` if summaries are being truncated