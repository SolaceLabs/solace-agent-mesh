---
title: Dynamic Tools
sidebar_position: 8
toc_max_heading_level: 4
---

# Dynamic Tools

:::info[Enterprise Feature]
Dynamic Tools are an enterprise feature of Solace Agent Mesh. Please contact Solace for more information on enterprise licensing.
:::

Dynamic tools allow you to define tools in configuration rather than code, making it easier to integrate external services without writing custom Python code. This guide explains how to use dynamic tools in Solace Agent Mesh.

## REST API Tools

The first supported dynamic tool type is REST API tools, which allow you to define HTTP endpoints as tools that can be used by your agent.

### Configuration

To configure REST API tools, add a tool with `tool_type: dynamic_tool` and `group_name: rest_api` to your agent's configuration:

```yaml
tools:
  - tool_type: dynamic_tool
    group_name: rest_api
    tools:
      - tool_name: get_weather
        url: https://api.weatherapi.com/v1/current.json
        method: GET
        parameters:
          q: string
          key: string
        headers:
          Accept: application/json
        description: Get current weather information for a location
```

### Tool Configuration Options

Each REST API tool supports the following configuration options:

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `tool_name` | string | Yes | The name of the tool, used by the agent to invoke it |
| `url` | string | Yes | The URL of the API endpoint |
| `method` | string | Yes | The HTTP method (GET, POST, PUT, PATCH, DELETE) |
| `parameters` | object | No | Map of parameter names to types (string, integer, number, boolean, object, array) |
| `headers` | object | No | Map of HTTP header names to values |
| `timeout` | integer | No | Request timeout in seconds (default: 30) |
| `description` | string | No | Description of the tool for the agent |
| `response_mapping` | object | No | Configuration for mapping API responses to tool results |

### Path Parameters

You can include path parameters in your URL by using curly braces:

```yaml
- tool_name: get_user
  url: https://api.example.com/users/{user_id}
  method: GET
  parameters:
    user_id: string
```

Path parameters are automatically extracted from the URL and marked as required parameters.

### Response Mapping

You can configure how API responses are mapped to tool results using the `response_mapping` option:

```yaml
- tool_name: get_user
  url: https://api.example.com/users/{user_id}
  method: GET
  parameters:
    user_id: string
  response_mapping:
    success_path: data.user
```

This extracts the `data.user` object from the API response and returns it as the tool result.

## Example Configuration

Here's a complete example configuration for an agent with REST API tools:

```yaml
namespace: test/dynamic-tools
agent_name: rest-api-agent
model: gemini-1.5-pro-latest
instruction: |
  You are an API assistant that can interact with various REST APIs.
  Use the provided tools to make API requests and process the responses.

tools:
  - tool_type: dynamic_tool
    group_name: rest_api
    tools:
      # Simple GET request
      - tool_name: get_weather
        url: https://api.example.com/weather
        method: GET
        parameters:
          city: string
        
      # POST request
      - tool_name: create_user
        url: https://api.example.com/users
        method: POST
        parameters:
          name: string
          email: string
          role: string
        headers:
          Content-Type: application/json
          Authorization: Bearer {api_key}