# Token Usage Tracking Feature

## Overview
This feature adds comprehensive token usage tracking and reporting throughout the Solace Agent Mesh system. It captures token consumption from LLM calls made by both agents and tools, aggregates this data at the task level, and makes it available through status updates and persistent storage.

## Goals
1. **Cost Visibility**: Enable accurate cost calculation and monitoring by tracking token usage across all LLM interactions
2. **Performance Analysis**: Provide data for optimizing agent prompts and tool implementations
3. **Debugging Support**: Help developers understand token consumption patterns and identify inefficiencies
4. **Audit Trail**: Maintain historical records of token usage for compliance and billing purposes

## Business Value
- **Cost Management**: Organizations can accurately track and allocate AI infrastructure costs
- **Optimization**: Teams can identify and reduce unnecessary token consumption
- **Transparency**: Users and administrators gain visibility into resource utilization
- **Billing**: Enables accurate chargeback or showback models for multi-tenant deployments

## Requirements

### Functional Requirements

#### FR1: Token Usage Capture
- **FR1.1**: Capture token usage from all LLM calls made by agents
- **FR1.2**: Capture token usage from LLM calls made within tools
- **FR1.3**: Support modern token types including:
  - Input tokens (standard prompt tokens)
  - Output tokens (standard completion tokens)
  - Cached input tokens (prompt cache hits)
  - Future extensibility for reasoning tokens, audio tokens, etc.
- **FR1.4**: Record the model identifier for each LLM call

#### FR2: Real-time Reporting
- **FR2.1**: Include token usage in existing status update events (no new event types)
- **FR2.2**: Attach token usage to LLM invocation/response events
- **FR2.3**: Attach token usage to tool result events when tools make LLM calls
- **FR2.4**: Provide incremental token counts in each status update

#### FR3: Task-Level Aggregation
- **FR3.1**: Accumulate total token usage across all LLM calls within a task
- **FR3.2**: Track token usage breakdown by:
  - Model (e.g., gpt-4, gemini-pro)
  - Source (agent vs. tool)
  - Tool name (for tool-originated LLM calls)
- **FR3.3**: Include aggregated token usage in final task response metadata

#### FR4: Persistent Storage
- **FR4.1**: Store token usage totals in the task database table
- **FR4.2**: Store detailed token usage breakdown as JSON
- **FR4.3**: Support querying tasks by token usage metrics
- **FR4.4**: Maintain backwards compatibility with existing tasks (nullable fields)

### Non-Functional Requirements

#### NFR1: Performance
- Token tracking must not introduce noticeable latency to LLM calls or task execution

#### NFR2: Accuracy
- Token counts must accurately reflect the values reported by LLM providers
- Aggregation logic must correctly sum tokens across multiple calls

#### NFR3: Extensibility
- The data model must accommodate future token types without breaking changes
- Support for new LLM providers and their token reporting formats

#### NFR4: Backwards Compatibility
- Existing tasks without token data must continue to function
- Database schema changes must be non-breaking (nullable columns)
- API responses must handle missing token data gracefully

## Key Design Decisions

### Decision 1: Token Naming Convention
**Decision**: Use `input_tokens` and `output_tokens` instead of `prompt_tokens` and `completion_tokens`

**Rationale**: 
- Aligns with modern LLM provider APIs (Anthropic, OpenAI's newer APIs)
- More intuitive and universally understood terminology
- Better reflects the actual data flow

### Decision 2: No New Event Types
**Decision**: Embed token usage in existing status update events rather than creating dedicated token usage events

**Rationale**:
- Reduces event volume and complexity
- Token usage is contextually relevant to LLM calls and tool executions
- Simplifies client-side event processing
- Avoids redundant events for the same operation

### Decision 3: Structured Token Data Model
**Decision**: Support multiple token types (cached, reasoning, audio) from the start, even if not all are immediately used

**Rationale**:
- LLM providers are rapidly adding new token types
- Easier to add support incrementally than to refactor later
- Optional fields allow graceful handling of providers that don't support all types
- Future-proofs the implementation

### Decision 4: Model Tracking
**Decision**: Always capture and store the model identifier with token usage

**Rationale**:
- Essential for accurate cost calculation (pricing varies dramatically by model)
- Useful for debugging and optimization
- Enables analysis of model selection patterns
- Minimal overhead to capture

### Decision 5: Two-Level Storage
**Decision**: Store both aggregated totals (separate columns) and detailed breakdown (JSON column)

**Rationale**:
- Totals in columns enable efficient querying and indexing
- JSON details preserve full context for analysis
- Balances query performance with data richness
- Supports both simple and complex reporting needs

### Decision 6: Source Attribution
**Decision**: Track whether tokens came from agent LLM calls or tool LLM calls

**Rationale**:
- Helps identify which tools are token-intensive
- Enables optimization of tool implementations
- Supports cost allocation to specific capabilities
- Minimal complexity to implement

## Scope

### In Scope
- Token usage tracking for agent LLM calls
- Token usage tracking for tool LLM calls
- Real-time status updates with token data
- Task-level aggregation and storage
- Database schema updates
- Support for cached tokens and standard input/output tokens
- Model identifier tracking

### Out of Scope (Future Enhancements)
- Cost calculation and reporting (token counts only, not dollar amounts)
- Token usage quotas or rate limiting
- Token usage analytics dashboard
- Historical trend analysis
- Token usage optimization recommendations
- Support for reasoning tokens, audio tokens (data model supports, but no active tracking yet)
- Per-user or per-organization token usage rollups

## Success Criteria
1. Token usage is accurately captured for 100% of LLM calls
2. Token data appears in status updates within the same event cycle as the LLM call
3. Final task responses include complete token usage summary
4. Database successfully stores token data for all new tasks
5. No performance degradation in task execution time
6. Existing tasks and clients continue to function without modification

## Dependencies
- Google ADK's `usage_metadata` in `LlmResponse` objects
- LiteLLM's token usage reporting from various providers
- Existing A2A status update event infrastructure
- Task persistence layer (TaskLoggerService)
- Database migration system (Alembic)

## Risks and Mitigations

### Risk 1: Provider Inconsistency
**Risk**: Different LLM providers report token usage in different formats or with different levels of detail

**Mitigation**: 
- Use optional fields for provider-specific token types
- Normalize to common fields (input_tokens, output_tokens) where possible
- Document provider-specific behavior

### Risk 2: Tool LLM Call Tracking Complexity
**Risk**: Tools that make LLM calls may not properly report token usage

**Mitigation**:
- Start with agent-level tracking (simpler, higher value)
- Add tool tracking incrementally
- Provide clear patterns and helper functions for tool developers

### Risk 3: Database Migration
**Risk**: Schema changes could cause issues in production deployments

**Mitigation**:
- Use nullable columns for backwards compatibility
- Test migration thoroughly on copy of production data
- Provide rollback migration
- Document migration process

## Open Questions
1. Should token usage be visible to end users in the UI, or only to administrators?
2. What level of token usage detail should be exposed in public APIs?
3. Should there be configurable thresholds for logging warnings about high token usage?
4. How long should detailed token usage breakdowns be retained in the database?

## Future Enhancements
- Cost calculation based on token usage and model pricing
- Token usage dashboards and analytics
- Automated alerts for unusual token consumption patterns
- Token usage optimization recommendations
- Support for additional token types (reasoning, audio, video)
- Per-user and per-organization token usage aggregation
- Token usage quotas and rate limiting
