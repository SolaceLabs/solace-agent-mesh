---
title: Configuring Built-in Tools
sidebar_position: 60
---

# Configuring Built-in Tools

This guide provides instructions for enabling and configuring the built-in tools provided by Agent Mesh framework.

## Overview

Built-in tools are pre-packaged functionalities that can be granted to agents without requiring custom Python code. These tools address common operations such as file management, data analysis, web requests, and multi-modal generation.

The Agent Mesh framework manages these tools through a central `tool_registry`, which is responsible for loading the tools, generating instructional prompts for the Large Language Model (LLM), and handling their execution in a consistent manner.

## Configuration Methods

Tool configuration is managed within the `tools` list in an agent's `app_config` block in the corresponding YAML configuration file.

### Method 1: Enabling Tool Groups (Recommended)

For efficient configuration, built-in tools are organized into logical groups. An entire group of related tools can be enabled with a single entry. This is the recommended approach for standard functionalities.


**Example:**
```yaml
# In your agent's app_config:
tools:
  - tool_type: builtin-group
    group_name: "artifact_management"
  - tool_type: builtin-group
    group_name: "data_analysis"
```

**Configuration:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool_type` | string | Yes | Must be `builtin-group` |
| `group_name` | string | Yes | Tool group identifier. Available groups: `artifact_management`, `data_analysis`, `web`, `audio`, `image`, `general`|
| `tool_config` | object | No | Group-specific configuration parameters |

### Method 2: Enabling Individual Tools

For more granular control over an agent's capabilities, specific tools can be enabled individually.

**Example:**
```yaml
# In your agent's app_config:
tools:
  - tool_type: builtin
    tool_name: "web_request"
  - tool_type: builtin
    tool_name: "time_delay"
```

**Configuration:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool_type` | string | Yes | Must be `builtin` |
| `tool_name` | string | Yes | Specific tool name to enable |
| `tool_config` | object | No | Tool-specific configuration parameters |

:::info Note
The Agent Mesh framework automatically handles duplicate tool registrations. If a tool group is enabled and a tool from that group is also listed individually, the tool is only loaded once.
:::

## Available Tool Groups and Tools

The following sections detail the available tool groups and the individual tools they contain.

### Artifact Management
**Group Name**: `artifact_management`

**Description**: Tools for creating, loading, and managing file artifacts.

**Individual Tools**:
- `append_to_artifact`
- `list_artifacts`
- `load_artifact`
- `apply_embed_and_create_artifact`
- `extract_content_from_artifact`

:::info
For a more in-depth guide on using artifact management tools, refer to the [Artifact Management](./artifact-management.md) documentation.
:::

### Data Analysis
**Group Name**: `data_analysis`

**Description**: Tools for querying, transforming, and visualizing data.

**Individual Tools**:
- `query_data_with_sql`
- `create_sqlite_db`
- `transform_data_with_jq`
- `create_chart_from_plotly_config`

:::info
For a more in-depth guide on using Data Analysis tools, refer to the [Data Analysis Tools](./data-analysis-tools.md) documentation.
:::

### Web Search
**Group Name**: `web_search`

**Description**: Tools for searching the web and retrieving current information.

**Individual Tools**:
- `web_search_google`

:::info
For a more in-depth guide on using web search tools, refer to the [Research Tools](./research-tools.md) documentation.
:::

### Research
**Group Name**: `research`

**Description**: Advanced research tools for comprehensive information gathering.

**Individual Tools**:
- `deep_research`

:::info
For a more in-depth guide on using the deep research tool, refer to the [Research Tools](./research-tools.md) documentation.
:::

### Web
**Group Name**: `web`

**Description**: Tools for interacting with web resources.

**Individual Tools**:
- `web_request`

### Audio
**Group Name**: `audio`

**Description**: Tools for generating and transcribing audio content.

**Individual Tools**:
- `text_to_speech`
- `multi_speaker_text_to_speech`
- `transcribe_audio`

:::info
For a more in-depth guide on using audio tools, refer to the [Audio Tools](./audio-tools.md) documentation.
:::

### Image
**Group Name**: `image`

**Description**: Tools for generating and analyzing images.

**Individual Tools**:
- `create_image_from_description`
- `describe_image`
- `edit_image_with_gemini`
- `describe_audio`

### General
**Group Name**: `general`

**Description**: General-purpose utility tools.

**Individual Tools**:
- `convert_file_to_markdown`
- `mermaid_diagram_generator`

## Complete Configuration Example

Below is a comprehensive example of a well-formed `app_config` that uses the unified method to enable a mix of tool groups and individual tools.

```yaml
# In your agent's YAML file:
app_config:
  namespace: "myorg/dev"
  agent_name: "DataAndWebAgent"
  model: "gemini-1.5-pro"
  instruction: "You are an agent that can analyze data and browse the web."

  # --- Unified Tool Configuration ---
  tools:
    # Enable a group of tools
    - tool_type: builtin-group
      group_name: "data_analysis"

    # Enable another group
    - tool_type: builtin-group
      group_name: "artifact_management"

    # Enable a single, specific tool
    - tool_type: builtin
      tool_name: "web_request"

  # ... other service configurations (session_service, artifact_service, etc.)
```

## Additional Tool Types

For extending agent capabilities beyond built-in tools:
- **Custom Python Tools**: See [Creating Python Tools](../../developing/creating-python-tools.md) for creating custom tools with your own business logic
- **MCP Integration**: See [MCP Integration Tutorial](../../developing/tutorials/mcp-integration.md) for connecting to Model Context Protocol servers