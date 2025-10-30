
# Comprehensive Guide to Creating Declarative Integration YAML Tests

This guide explains how to create declarative integration tests for the Solace Agent Mesh using YAML files. These tests are executed by [`test_declarative_runner.py`](../tests/integration/scenarios_declarative/test_declarative_runner.py).

## Table of Contents

1. [Overview](#overview)
2. [Basic Structure](#basic-structure)
3. [Core Components](#core-components)
4. [Gateway Input](#gateway-input)
5. [LLM Interactions](#llm-interactions)
6. [Expected Gateway Output](#expected-gateway-output)
7. [Setup and Teardown](#setup-and-teardown)
8. [Advanced Features](#advanced-features)
9. [Assertion Patterns](#assertion-patterns)
10. [Best Practices](#best-practices)
11. [Examples](#examples)

---

## Overview

Declarative tests allow you to define integration test scenarios in YAML format without writing Python code. The test runner:
- Sets up mock LLM responses
- Sends input to the gateway
- Captures all events
- Validates outputs against expectations
- Verifies artifact states

### Test File Location
Place test files in: `tests/integration/scenarios_declarative/test_data/`

Organize by feature area (e.g., `builtin_artifact_tools/`, `mcp/`, `image_tools/`)

---

## Basic Structure

Every test YAML file must include these top-level fields:

```yaml
test_case_id: "unique_test_identifier_001"
description: "Clear description of what this test validates"
tags: ["all", "agent", "tools"]  # For test filtering
skip_intermediate_events: true   # Recommended for most tests

gateway_input:
  # How to send input to the agent

llm_interactions:
  # Mock LLM responses

expected_gateway_output:
  # What events/outputs to expect
```

### Minimal Example

```yaml
test_case_id: "basic_text_response_001"
description: "Agent receives a simple text query and responds with text directly."
tags: ["all", "default"]
skip_intermediate_events: true

gateway_input:
  target_agent_name: "TestAgent"
  user_identity: "test_user@example.com"
  a2a_parts:
    - type: "text"
      text: "Hello Agent, what is 2+2?"
  external_context:
    a2a_session_id: "session_basic_001"

llm_interactions:
  - step_id: "agent_responds_to_query"
    static_response:
      id: "chatcmpl-test-001"
      object: "chat.completion"
      model: "test-llm-model"
      choices:
        - index: 0
          message:
            role: "assistant"
            content: "Two plus two equals four."
          finish_reason: "stop"

expected_gateway_output:
  - type: "final_response"
    content_parts:
      - type: "text"
        text_exact: "Two plus two equals four."
    task_state: "completed"
```

---

## Core Components

### 1. Test Metadata

```yaml
test_case_id: "unique_identifier_001"
description: |
  Multi-line description explaining:
  - What is being tested
  - Expected behavior
  - Any special conditions
tags: ["all", "agent", "tools", "specific_feature"]
skip_intermediate_events: true  # Skip non-essential events
expected_completion_timeout_seconds: 15  # Optional, default varies
```

**Tags:**
- `"all"` - Include in all test runs
- `"default"` - Include in default test suite
- Feature-specific tags for filtering (e.g., `"mcp"`, `"artifacts"`, `"tools"`)

**skip_intermediate_events:**
- `true` (recommended): Only assert on explicitly listed events
- `false`: Assert on ALL events in exact order

---

## Gateway Input

### Standard Gateway Input (A2A Protocol)

```yaml
gateway_input:
  target_agent_name: "TestAgent"  # Must match fixture agent name
  user_identity: "user@example.com"
  a2a_parts:  # or just 'parts:'
    - type: "text"
      text: "Your query here"
  external_context:
    source_test_file: "test_file.yaml"
    a2a_session_id: "unique_session_id"
    initial_request_timestamp: "2025-05-31T12:00:00Z"
```

### HTTP Request Input (WebUI API)

```yaml
http_request_input:
  method: "POST"
  path: "/api/v1/message:stream"
  user_identity: "user@example.com"
  json_body:
    jsonrpc: "2.0"
    id: "http-req-123"
    method: "message/stream"
    params:
      message:
        role: "user"
        messageId: "msg-123"
        kind: "message"
        parts:
          - kind: "text"
            text: "Your message"
        metadata:
          agent_name: "TestAgent"
  query_params:  # Optional
    param1: "value1"
```

### Input with File Parts

```yaml
gateway_input:
  target_agent_name: "TestAgent"
  user_identity: "user@example.com"
  a2a_parts:
    - type: "text"
      text: "Process this file"
    - type: "file"
      filename: "data.csv"
      mime_type: "text/csv"
      content_base64: "Y29sdW1uMSxjb2x1bW4yCnZhbHVlMSx2YWx1ZTI="
```

---

## LLM Interactions

Define mock LLM responses in sequence. Each interaction represents one LLM call.

### Basic Text Response

```yaml
llm_interactions:
  - step_id: "descriptive_step_name"
    static_response:
      id: "chatcmpl-unique-id"
      object: "chat.completion"
      model: "test-llm-model"
      choices:
        - index: 0
          message:
            role: "assistant"
            content: "The agent's text response"
          finish_reason: "stop"
      usage:
        prompt_tokens: 10
        completion_tokens: 5
        total_tokens: 15
```

### Tool Call Response

```yaml
llm_interactions:
  - step_id: "llm_requests_tool"
    expected_request:  # Optional: validate what LLM receives
      tools_present: ["tool_name"]
    static_response:
      id: "chatcmpl-tool-call"
      object: "chat.completion"
      model: "test-llm-model"
      choices:
        - index: 0
          message:
            role: "assistant"
            content: null
            tool_calls:
              - id: "call_123"
                type: "function"
                function:
                  name: "tool_name"
                  arguments: '{"param": "value"}'
          finish_reason: "tool_calls"
```

### Multiple Tool Calls

```yaml
llm_interactions:
  - step_id: "llm_calls_multiple_tools"
    static_response:
      choices:
        - message:
            role: "assistant"
            tool_calls:
              - id: "call_1"
                type: "function"
                function:
                  name: "first_tool"
                  arguments: '{"arg": "value1"}'
              - id: "call_2"
                type: "function"
                function:
                  name: "second_tool"
                  arguments: '{"arg": "value2"}'
          finish_reason: "tool_calls"
```

### Processing Tool Results

```yaml
llm_interactions:
  - step_id: "llm_processes_tool_response"
    expected_request:
      expected_tool_responses_in_llm_messages:
        - tool_name: "tool_name"
          tool_call_id_matches_prior_request_index: 0
          response_contains: "expected substring"
          response_json_matches:
            status: "success"
            result: "expected value"
    static_response:
      choices:
        - message:
            role: "assistant"
            content: "Final response after tool execution"
          finish_reason: "stop"
```

### Expected Request Validations

```yaml
expected_request:
  # Validate tools are present
  tools_present: ["tool1", "tool2"]
  
  # Validate exact tool list
  assert_tools_exact: ["tool1", "tool2", "tool3"]
  
  # Validate tools are NOT present
  tools_not_present: ["unwanted_tool"]
  
  # Validate tool declarations
  expected_tool_declarations_contain:
    - name: "tool_name"
      description_contains: "substring in description"
  
  # Validate artifact summaries in prompt
  prompt_contains_artifact_summary_for:
    - filename: "file.txt"
      version: "latest"
    - filename_matches_regex: "output_.*\\.json"
  
  # Validate tool responses
  expected_tool_responses_in_llm_messages:
    - tool_name: "tool_name"
      tool_call_id_matches_prior_request_index: 0
      response_contains: "substring"
      response_json_matches:
        key: "value"
```

---

## Expected Gateway Output

Define expected events from the gateway. Events are matched in order (or skipped if `skip_intermediate_events: true`).

### Final Response Event

```yaml
expected_gateway_output:
  - type: "final_response"
    kind: "task"
    id: "*"  # Wildcard for any ID
    contextId: "session_id_here"
    status:
      state: "completed"  # or "failed", "cancelled"
      message:
        kind: "message"
        messageId: "*"
        role: "agent"
        parts:
          - kind: "text"
            text_exact: "Exact text match"
          # OR
          - type: "text"
            text_contains:
              - "substring 1"
              - "substring 2"
          # OR
          - type: "text"
            text_matches_regex: "pattern.*here"
```

### Status Update Event

```yaml
expected_gateway_output:
  - type: "status_update"
    event_purpose: "tool_invocation_start"
    expected_tool_name: "tool_name"
    expected_tool_args_contain:
      param1: "value1"
      param2: "value2"
    final_flag: false
```

### Artifact Update Event

```yaml
expected_gateway_output:
  - type: "artifact_update"
    artifact_filename: "output.txt"
    artifact_version: 0
    artifact_mime_type: "text/plain"
```

### Aggregated Text Content

For streaming text responses:

```yaml
expected_gateway_output:
  - type: "aggregated_text_content"
    text_exact: "Complete aggregated text"
    # OR
    text_contains: ["substring1", "substring2"]
    # OR
    text_matches_regex: "pattern"
```

### Error Event

```yaml
expected_gateway_output:
  - type: "error"
    error_code: -32603
    error_message_contains: "error description"
```

---

## Setup and Teardown

### Setup Artifacts

Create artifacts before the test runs:

```yaml
setup_artifacts:
  - filename: "input.txt"
    mime_type: "text/plain"
    content: "Text content here"
    metadata:
      description: "Input file for testing"
      source: "test_setup"
  
  - filename: "binary.png"
    mime_type: "image/png"
    content_base64: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    metadata:
      description: "Binary image file"
      size_bytes: 68
  
  # For proxy tests, specify app_name explicitly
  - filename: "proxy_artifact.txt"
    app_name: "TargetAgentName"
    content: "Content for specific agent"
```

### Setup Tasks

Create tasks in the database before the test:

```yaml
setup_tasks:
  - task_id: "task-123"
    user_id: "user@example.com"
    message: "Previous task message"
    status: "completed"
    start_time_iso: "2025-01-01T10:00:00Z"
    end_time_iso: "2025-01-01T10:05:00Z"
```

### Primed Image Generation Responses

For image generation tools:

```yaml
primed_image_generation_responses:
  - response: '{"created": 1677652288, "data": [{"b64_json": "base64_encoded_image_data"}]}'
    status_code: 200
```

---

## Advanced Features

### Test Runner Config Overrides

Override agent configuration for specific tests:

```yaml
test_runner_config_overrides:
  agent_config:
    mcp_tool_response_save_threshold_bytes: 10
    max_tool_calls_per_turn: 5
  artifact_scope: "namespace"  # or "agent" (default)
```

### Gateway Actions

Perform actions during test execution:

```yaml
gateway_actions:
  - type: "cancel_task"
    delay_seconds: 0.5  # Wait before cancelling
```

### Downstream Agent Configuration

For proxy/multi-agent tests:

```yaml
downstream_agent_auth:
  enabled: true
  type: "bearer"
  expected_value: "test_token_123"
  should_fail_once: false  # Test retry logic

downstream_http_error:
  status_code: 503
  error_body: "Service temporarily unavailable"
```

### Mock OAuth Server

```yaml
mock_oauth_server:
  token_url: "http://localhost:8080/oauth/token"
  access_token: "test_token_12345"
  expires_in: 3600
  # OR for error testing
  error: "invalid_client"
  status_code: 401
  # OR for retry testing
  response_sequence:
    - status_code: 500
      error: "server_error"
    - status_code: 200
      access_token: "test_token_12345"
```

### HTTP Response Assertions

Validate HTTP API responses:

```yaml
expected_http_responses:
  - description: "Verify task appears in list"
    request:
      method: "GET"
      path: "/api/v1/tasks"
      query_params:
        user_id: "user@example.com"
    expected_status_code: 200
    expected_content_type: "application/json"
    text_contains:
      - "expected substring"
    expected_json_body_matches:
      - user_id: "user@example.com"
        status: "completed"
        id_matches_regex: ".+"
    expected_list_length: 5
```

### Cancellation Assertions

```yaml
expected_cancellation:
  gateway_sent: true
  downstream_received: true
```

---

## Assertion Patterns

### Artifact State Assertions

Verify artifact content and metadata:

```yaml
expected_gateway_output:
  - type: "final_response"
    # ... other fields ...
    assert_artifact_state:
      - filename: "output.txt"
        user_id: "user@example.com"
        session_id: "session_123"
        version: 0
        expected_content_text: "Expected text content"
        expected_metadata_contains:
          description: "Output file"
          source: "agent_generated"
      
      - filename_
      - filename_matches_regex: "output_.*\\.json"
        version: 0
        expected_content_bytes_base64: "base64_encoded_content"
      
      # For binary files
      - filename: "image.png"
        version: 0
        expected_content_bytes_base64: "iVBORw0KGgo..."
        expected_metadata_contains:
          mime_type: "image/png"
          size_bytes: 68
      
      # Assert metadata schema
      - filename: "data.json"
        version: 0
        assert_metadata_schema_key_count: 5
```

### Text Matching Options

```yaml
# Exact match
text_exact: "Exact string to match"

# Contains substrings (all must be present)
text_contains:
  - "substring 1"
  - "substring 2"

# Regex pattern
text_matches_regex: "^Pattern.*here$"

# Regex with flags
text_matches_regex: "(?i)case.*insensitive"
```

### JSON Matching

```yaml
# Exact subset match
response_json_matches:
  status: "success"
  result:
    key: "value"
    nested:
      field: 123

# Regex in JSON values
response_json_matches:
  id_matches_regex: "^[a-f0-9]{8}-"
  message_matches_regex: ".*completed.*"

# Contains substring in JSON string value
response_json_matches:
  message_contains: "partial text"
```

### Dict/List Subset Matching

The test runner uses subset matching for dicts and lists:

```yaml
# Dict subset - actual can have more keys
expected_json_body_matches:
  user_id: "user@example.com"
  status: "completed"
  # Actual response can have additional fields

# List subset - checks if expected items exist in actual list
expected_json_body_matches:
  - id: "task-1"
    status: "completed"
  - id: "task-2"
    status: "pending"
  # Actual list can have more items
```

---

## Best Practices

### 1. Use Descriptive IDs and Names

```yaml
test_case_id: "feature_scenario_condition_001"
# Good: "builtin_load_artifact_binary_content_001"
# Bad: "test_001"

step_id: "llm_calls_tool_with_params"
# Good: Describes what happens
# Bad: "step_1"
```

### 2. Enable skip_intermediate_events

```yaml
skip_intermediate_events: true
```

This makes tests more maintainable by only asserting on critical events.

### 3. Use Wildcards for Dynamic Values

```yaml
id: "*"  # Any ID
messageId: "*"  # Any message ID
contextId: "session_123"  # Specific session
```

### 4. Organize by Feature

```
test_data/
  builtin_artifact_tools/
    load_artifact/
      test_load_artifact_binary_content.yaml
      test_load_artifact_version_not_found.yaml
  image_tools/
    create_image/
      test_create_image_happy_path.yaml
      test_create_image_api_failure.yaml
```

### 5. Test Both Success and Failure Cases

```yaml
# Success case
test_case_id: "tool_success_001"
# ...

# Error case
test_case_id: "tool_file_not_found_001"
# ...
```

### 6. Use Meaningful Session IDs

```yaml
external_context:
  a2a_session_id: "session_feature_scenario_001"
  # Not: "session_1"
```

### 7. Document Complex Scenarios

```yaml
description: |
  Tests the following scenario:
  1. Agent receives request with file
  2. Agent calls tool to process file
  3. Tool returns processed result
  4. Agent generates final response
  
  Expected behavior:
  - File is processed correctly
  - Metadata is preserved
  - Final response includes summary
```

### 8. Use Appropriate Timeouts

```yaml
expected_completion_timeout_seconds: 30  # For complex scenarios
# Default is usually sufficient for simple tests
```

### 9. Validate Tool Declarations

```yaml
expected_request:
  expected_tool_declarations_contain:
    - name: "tool_name"
      description_contains: "key functionality"
```

This ensures tools are properly registered and described.

### 10. Test Embed Resolution

For tests involving embeds (e.g., `«math:5+3»`):

```yaml
llm_interactions:
  - static_response:
      choices:
        - message:
            content: "Result is «math:5+3»"

expected_gateway_output:
  - type: "final_response"
    content_parts:
      - text_contains: ["Result is 8"]
```

---

## Examples

### Example 1: Simple Text Response

```yaml
test_case_id: "simple_greeting_001"
description: "Agent responds to a greeting"
tags: ["all", "basic"]
skip_intermediate_events: true

gateway_input:
  target_agent_name: "TestAgent"
  user_identity: "user@example.com"
  a2a_parts:
    - type: "text"
      text: "Hello!"

llm_interactions:
  - static_response:
      choices:
        - message:
            role: "assistant"
            content: "Hello! How can I help you today?"

expected_gateway_output:
  - type: "final_response"
    status:
      state: "completed"
      message:
        parts:
          - text_exact: "Hello! How can I help you today?"
```

### Example 2: Tool Call with Validation

```yaml
test_case_id: "weather_tool_call_001"
description: "Agent uses weather tool to get current conditions"
tags: ["all", "tools"]
skip_intermediate_events: true

gateway_input:
  target_agent_name: "TestAgent"
  user_identity: "user@example.com"
  a2a_parts:
    - type: "text"
      text: "What's the weather in London?"

llm_interactions:
  - step_id: "llm_calls_weather_tool"
    expected_request:
      tools_present: ["get_weather"]
    static_response:
      choices:
        - message:
            role: "assistant"
            tool_calls:
              - id: "call_weather_1"
                type: "function"
                function:
                  name: "get_weather"
                  arguments: '{"location": "London"}'
          finish_reason: "tool_calls"
  
  - step_id: "llm_responds_with_weather"
    expected_request:
      expected_tool_responses_in_llm_messages:
        - tool_name: "get_weather"
          response_json_matches:
            temperature: 22
            condition: "sunny"
    static_response:
      choices:
        - message:
            role: "assistant"
            content: "It's sunny and 22°C in London."

expected_gateway_output:
  - type: "status_update"
    event_purpose: "tool_invocation_start"
    expected_tool_name: "get_weather"
    expected_tool_args_contain:
      location: "London"
  
  - type: "final_response"
    status:
      state: "completed"
      message:
        parts:
          - text_contains: ["sunny", "22°C", "London"]
```

### Example 3: Artifact Creation and Validation

```yaml
test_case_id: "create_report_artifact_001"
description: "Agent creates a report artifact"
tags: ["all", "artifacts"]
skip_intermediate_events: true

gateway_input:
  target_agent_name: "TestAgent"
  user_identity: "user@example.com"
  a2a_parts:
    - type: "text"
      text: "Create a report"
  external_context:
    a2a_session_id: "session_report_001"

llm_interactions:
  - static_response:
      choices:
        - message:
            role: "assistant"
            tool_calls:
              - id: "call_create_1"
                type: "function"
                function:
                  name: "create_artifact"
                  arguments: '{"filename": "report.txt", "content": "Report content"}'
  
  - static_response:
      choices:
        - message:
            role: "assistant"
            content: "I've created the report."

expected_gateway_output:
  - type: "final_response"
    status:
      state: "completed"
    assert_artifact_state:
      - filename: "report.txt"
        version: 0
        expected_content_text: "Report content"
        expected_metadata_contains:
          description: "Created artifact"
```

### Example 4: HTTP API Test

```yaml
test_case_id: "api_get_tasks_001"
description: "Test retrieving tasks via HTTP API"
tags: ["api", "tasks"]
skip_intermediate_events: true

http_request_input:
  method: "POST"
  path: "/api/v1/message:stream"
  user_identity: "user@example.com"
  json_body:
    jsonrpc: "2.0"
    id: "req-1"
    method: "message/stream"
    params:
      message:
        role: "user"
        kind: "message"
        parts:
          - kind: "text"
            text: "Create a task"
        metadata:
          agent_name: "TestAgent"

llm_interactions:
  - static_response:
      choices:
        - message:
            role: "assistant"
            content: "Task created"

expected_gateway_output:
  - type: "final_response"
    status:
      state: "completed"

expected_http_responses:
  - description: "Verify task in list"
    request:
      method: "GET"
      path: "/api/v1/tasks"
    expected_status_code: 200
    expected_json_body_matches:
      - user_id: "user@example.com"
        status: "completed"
```

### Example 5: Error Handling

```yaml
test_case_id: "tool_error_handling_001"
description: "Agent handles tool error gracefully"
tags: ["all", "errors"]
skip_intermediate_events: true

gateway_input:
  target_agent_name: "TestAgent"
  user_identity: "user@example.com"
  a2a_parts:
    - type: "text"
      text: "Load non-existent file"

llm_interactions:
  - static_response:
      choices:
        - message:
            role: "assistant"
            tool_calls:
              - id: "call_load_1"
                type: "function"
                function:
                  name: "load_artifact"
                  arguments: '{"filename": "missing.txt"}'
  
  - expected_request:
      expected_tool_responses_in_llm_messages:
        - tool_name: "load_artifact"
          response_json_matches:
            status: "error"
            message_contains: "not found"
    static_response:
      choices:
        - message:
            role: "assistant"
            content: "Sorry, the file was not found."

expected_gateway_output:
  - type: "final_response"
    status:
      state: "completed"
      message:
        parts:
          - text_contains: ["not found"]
```

### Example 6: Multi-Step with Embeds

```yaml
test_case_id: "embed_math_calculation_001"
description: "Agent uses math embed in response"
tags: ["all", "embeds"]
skip_intermediate_events: true

gateway_input:
  target_agent_name: "TestAgent"
  user_identity: "user@example.com"
  a2a_parts:
    - type: "text"
      text: "Calculate 15 * 3"

llm_interactions:
  - static_response:
      choices:
        - message:
            role: "assistant"
            content: "The result is «math:15*3»."

expected_gateway_output:
  - type: "final_response"
    status:
      state: "completed"
      message:
        parts:
          - text_contains: ["The result is 45"]
```

---

## Running Tests

### Run All Tests

```bash
pytest tests/integration/scenarios_declarative/
```

### Run Specific Tags

```bash
pytest tests/integration/scenarios_declarative/ -m "tools"
pytest tests/integration/scenarios_declarative/ -m "artifacts"
```

### Run Single Test File

```bash
pytest tests/integration/scenarios_declarative/test_declarative_runner.py::test_declarative_scenario[test_basic_text_response.yaml]
```

### Debug Mode

Set environment variable for verbose output:

```bash
DEBUG=1 pytest tests/integration/scenarios_declarative/ -v -s
```

---

## Troubleshooting

### Common Issues

1. **Event Mismatch**: Use `skip_intermediate_events: true` to focus on key events
2. **Tool Call ID Mismatch**: Ensure `tool_call_id_matches_prior_request_index` references correct interaction
3. **Artifact Not Found**: Check `session_id` and `user_identity` match between setup and assertions
4. **Timeout**: Increase `expected_completion_timeout_seconds` for complex scenarios
5. **JSON Matching**: Use `_contains` or `_matches_regex` suffixes for flexible matching

### Debugging Tips

1. Check test output for actual vs expected events
2. Use `pretty_print_event_history` utility for event inspection
3. Verify LLM interaction sequence matches expected flow
4. Ensure artifact setup uses correct `app_name` for proxy tests
5. Check that tool names match exactly (case-sensitive)

---

## Reference

### Event Types

- `final_response` - Terminal task completion event
- `status_update` - Progress updates (tool calls, etc.)
- `artifact_update` - Artifact creation/modification
- `error` - Error events
- `aggregated_text_content` - Streaming text aggregation

### Event Purposes

- `tool_invocation_start` - Tool execution begins
- `tool_invocation_end` - Tool execution completes
- `llm_invocation` - LLM call initiated
- `llm_response` - LLM response received
- `generic_text_update` - Text streaming update
- `artifact_creation_progress` - Artifact being created

### Task States

- `completed` - Task finished successfully
- `failed` - Task failed with error
- `cancelled` - Task was cancelled
- `running` - Task in progress

---

