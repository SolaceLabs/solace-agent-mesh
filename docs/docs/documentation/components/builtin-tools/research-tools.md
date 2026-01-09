---
title: Research Tools
sidebar_position: 50
---

# Research Tools

Agent Mesh provides research tools that enable agents to search the web and conduct comprehensive research on complex topics. These tools give agents access to current information beyond their training data and the ability to synthesize findings from multiple sources into detailed reports.

## Overview

The research tools consist of two categories:

The web search tools provide direct access to web search engines, allowing agents to retrieve current information, news, and facts. The deep research tool builds on web search to conduct iterative research with LLM-powered reflection and report generation.

## Setup and Configuration

### Prerequisites

To use the web search functionality, you need a Google Custom Search API key and a Custom Search Engine ID. You can obtain these from the Google Cloud Console.

### Environment Variables

Set the following environment variables:

```bash
export GOOGLE_API_KEY="your_google_api_key_here"
export GOOGLE_CSE_ID="your_custom_search_engine_id_here"
```

### Enabling the Tools

Enable the research tools in your agent's `app_config.yml`:

```yaml
tools:
  - tool_type: builtin-group
    group_name: "web_search"

  - tool_type: builtin-group
    group_name: "research"
```

You can also enable individual tools:

```yaml
tools:
  - tool_type: builtin
    tool_name: "web_search_google"
  - tool_type: builtin
    tool_name: "deep_research"
```

### Tool Configuration

Both tools accept configuration through the `tool_config` block:

```yaml
- tool_type: builtin
  tool_name: "web_search_google"
  tool_config:
    google_search_api_key: ${GOOGLE_API_KEY}
    google_cse_id: ${GOOGLE_CSE_ID}

- tool_type: builtin
  tool_name: "deep_research"
  tool_config:
    google_search_api_key: ${GOOGLE_API_KEY}
    google_cse_id: ${GOOGLE_CSE_ID}
    max_iterations: 5
    max_runtime_seconds: 300
    sources:
      - web
```

## Web Search Tool

The `web_search_google` tool searches the web using Google Custom Search API and returns results with source citations.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | The search query (required) |
| `max_results` | integer | Maximum number of results to return (1-10, default: 5) |
| `search_type` | string | Set to `"image"` for image search |
| `date_restrict` | string | Restrict results by recency (for example, `"d7"` for last 7 days) |
| `safe_search` | string | Safe search level: `"off"`, `"medium"`, or `"high"` |

### Usage Examples

A basic web search:
```
Search the web for "latest developments in quantum computing"
```

An image search:
```
Search for images of "aurora borealis"
```

A search with date restriction:
```
Search for news about "AI regulations" from the last 7 days
```

### Response Format

The tool returns search results with the following information for each result:
- Title and URL of the source
- A text snippet from the page
- Attribution information for citations
- Favicon URL for display purposes

The results include metadata that enables automatic citation rendering in the UI. Agents should cite sources using the citation format provided in their instructions.

:::info
Image results are displayed automatically in the UI. Agents should not cite images or mention image URLs in their response text.
:::

## Deep Research Tool

The `deep_research` tool conducts comprehensive, iterative research across multiple sources. It uses LLM-powered reflection to identify knowledge gaps and refine search queries, then synthesizes findings into a detailed report with proper citations.

### How Deep Research Works

The deep research process follows these steps:

1. The tool breaks down the research question into multiple search queries using LLM analysis
2. It searches across configured sources (currently web search, with knowledge base support planned)
3. The LLM reflects on the findings to assess completeness and identify gaps
4. Based on the reflection, the tool generates refined queries and conducts additional searches
5. The tool selects the most authoritative sources and fetches their full content
6. Finally, it synthesizes all findings into a comprehensive report with citations

Throughout this process, the tool sends progress updates to the frontend, allowing users to see the current research phase, queries being executed, and sources being analyzed.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `research_question` | string | The research question or topic to investigate (required) |
| `research_type` | string | `"quick"` (5 min, 3 iterations) or `"in-depth"` (10 min, 10 iterations) |
| `max_iterations` | integer | Maximum research iterations (1-10, overrides research_type) |
| `max_runtime_minutes` | integer | Maximum runtime in minutes (1-10, overrides research_type) |
| `max_runtime_seconds` | integer | Maximum runtime in seconds (60-600) |
| `sources` | array | Sources to search: `["web"]` or `["web", "kb"]` |
| `kb_ids` | array | Specific knowledge base IDs to search (when `"kb"` is in sources) |

### Configuration Priority

The tool resolves configuration in this order (highest to lowest priority):

1. Explicit parameters passed to the tool
2. Values from `tool_config` in the agent configuration
3. Defaults based on `research_type` ("quick" or "in-depth")

### Research Types

The `research_type` parameter provides convenient presets:

| Type | Duration | Iterations | Use Case |
|------|----------|------------|----------|
| `quick` | 5 minutes | 3 | Fast answers, simple topics |
| `in-depth` | 10 minutes | 10 | Complex topics, comprehensive analysis |

### Advanced Configuration

You can configure phase-specific models for cost optimization or quality control:

```yaml
- tool_type: builtin
  tool_name: "deep_research"
  tool_config:
    google_search_api_key: ${GOOGLE_API_KEY}
    google_cse_id: ${GOOGLE_CSE_ID}
    
    # Use faster models for query generation and reflection
    models:
      query_generation: "gpt-4o-mini"
      reflection: "gpt-4o-mini"
      source_selection: "gpt-4o-mini"
    
    # Use a more capable model for report generation
    model_configs:
      report_generation:
        model: "claude-3-5-sonnet-20241022"
        temperature: 0.7
        max_tokens: 16000
```

### Usage Examples

A quick research request:
```
Research the current state of renewable energy adoption in Europe
```

An in-depth research request:
```
Conduct in-depth research on the economic impact of artificial intelligence on the job market over the next decade
```

A research request with specific parameters:
```
Research quantum computing applications in drug discovery. Use 5 iterations and limit to 3 minutes.
```

### Output

The deep research tool produces:

1. A comprehensive research report saved as a Markdown artifact
2. Metadata with all sources and citations for UI rendering
3. Progress updates throughout the research process

The report includes:
- Executive summary
- Introduction with context
- Main analysis organized by themes
- Comparative analysis of different perspectives
- Implications and conclusions
- References section with all cited sources
- Research methodology section

### Progress Updates

During research, the tool sends structured progress updates that include:
- Current phase (planning, searching, analyzing, writing)
- Progress percentage
- Current iteration and total iterations
- Number of sources found
- Current search query
- URLs being fetched

These updates enable rich UI visualizations of the research process.

## Required Scopes

The research tools require the following scopes for authorization:

| Tool | Required Scope |
|------|----------------|
| `web_search_google` | `tool:web_search:execute` |
| `deep_research` | `tool:research:deep_research` |

## Alternative Search Providers

The built-in web search uses Google Custom Search API. For other search providers such as Exa, Brave, or Tavily, use the corresponding plugins from the solace-agent-mesh-plugins repository.

## Technical Considerations

### Rate Limits

Google Custom Search API has usage limits. Monitor your API usage and implement appropriate rate limiting for production deployments.

### Content Fetching

When the deep research tool fetches full content from web pages, some sites may block automated requests or return incomplete content. The tool handles these failures gracefully and continues with available sources.

### Report Quality

The quality of research reports depends on:
- The quality and relevance of search results
- The number of iterations and sources analyzed
- The capabilities of the LLM used for report generation

For best results, use capable models for the report generation phase and allow sufficient iterations for complex topics.