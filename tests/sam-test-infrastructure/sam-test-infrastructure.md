# SAM Test Infrastructure

## Overview

The SAM Test Infrastructure is a comprehensive testing framework designed for integration testing of the Solace Agent Mesh (SAM). It provides mock servers, test fixtures, and utilities that enable developers to write reliable, deterministic tests without requiring external dependencies like real LLM APIs or message brokers.

### Key Features

- **Mock LLM Server**: Simulates OpenAI-compatible API endpoints with configurable responses
- **Test Gateway**: GDK-based gateway component for programmatic test input
- **A2A Agent Server**: Mock A2A-compliant agent server for testing inter-agent communication
- **Artifact Service**: In-memory artifact storage for testing file operations
- **MCP Server**: Mock Model Context Protocol server for testing MCP tool integrations
- **Static File Server**: HTTP server for testing web request tools
- **A2A Message Validator**: Validates all A2A messages against the official schema
- **Comprehensive Fixtures**: Pre-configured pytest fixtures for common test scenarios

## Architecture

The test infrastructure operates in "dev mode" where all components communicate through an in-memory message broker instead of requiring a real Solace PubSub+ broker.

## Core Components

### 1. TestLLMServer

A FastAPI-based mock server that mimics OpenAI's chat completion API.

**Key Methods:**
- `prime_responses(responses: List[Dict])`: Queue responses to be returned in order
- `configure_static_response(response: Dict)`: Set a default response
- `get_captured_requests()`: Retrieve all captured LLM requests
- `clear_all_configurations()`: Reset server state

### 2. TestGatewayComponent

A GDK-based gateway component that translates test inputs into A2A messages.

**Key Methods:**
- `send_test_input(test_input_data: Dict) -> str`: Submit test input, returns task_id
- `get_next_captured_output(task_id: str, timeout: float)`: Get next event
- `get_all_captured_outputs(task_id: str)`: Drain all events for a task

### 3. TestA2AAgentServer

A mock A2A-compliant agent server for testing inter-agent communication.

**Key Methods:**
- `prime_responses(responses: List[Dict])`: Queue responses
- `configure_auth_validation()`: Test authentication
- `was_cancel_requested_for_task(task_id: str) -> bool`: Check cancellation

### 4. TestInMemoryArtifactService

In-memory implementation of the ADK BaseArtifactService.

### 5. TestMCPServer

Configurable MCP server supporting stdio, HTTP, and SSE transports.

### 6. TestStaticFileServer

HTTP server for testing web request tools.

### 7. A2AMessageValidator

Validates all A2A messages against the official schema.

## Writing Tests

### Programmatic Tests

```python
import pytest
from sam_test_infrastructure.llm_server.server import TestLLMServer
from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from .test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
    extract_outputs_from_event_list,
    assert_final_response_text_contains,
)

@pytest.mark.asyncio
async def test_basic_response(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    a2a_message_validator: A2AMessageValidator,
):
    """Test basic text response from agent."""
    
    # 1. Prime LLM server
    llm_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "The answer is 4."
            },
            "finish_reason": "stop"
        }]
    }
    prime_llm_server(test_llm_server, [llm_response])
    
    # 2. Create test input
    test_input = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="test_user@example.com",
        text_parts_content=["What is 2+2?"],
        scenario_id="test_basic_response"
    )
    
    # 3. Submit input
    task_id = await submit_test_input(
        test_gateway_app_instance,
        test_input,
        "test_basic_response"
    )
    
    # 4. Get all events
    all_events = await get_all_task_events(
        test_gateway_app_instance,
        task_id,
        overall_timeout=5.0
    )
    
    # 5. Verify response
    terminal_event, stream_text, terminal_text = extract_outputs_from_event_list(
        all_events,
        "test_basic_response"
    )
    
    content = stream_text if stream_text else terminal_text
    assert_final_response_text_contains(
        content,
        "The answer is 4.",
        "test_basic_response",
        terminal_event
    )
```

### Declarative Tests (YAML)

Declarative tests use YAML files to define test scenarios.

**Example YAML Test:**

```yaml
test_case_id: create_chart_png_success
description: "Tests successful creation of a PNG chart"
tags: ["all", "agent", "tools"]

gateway_input:
  target_agent_name: "TestAgent"
  user_identity: "chart_tester@example.com"
  parts:
    - type: "text"
      text: "Create a PNG chart from the provided config."
  external_context:
    a2a_session_id: "chart_creation_session"

llm_interactions:
  - static_response:
      choices:
        - message:
            role: "assistant"
            tool_calls:
              - id: "call_chart_tool"
                type: "function"
                function:
                  name: "create_chart_from_plotly_config"
                  arguments: '{"config_content": "...", "output_filename": "chart.png"}'
  - expected_request:
      expected_tool_responses_in_llm_messages:
        - tool_call_id_matches_prior_request_index: 0
          response_json_matches:
            status: "success"
            output_filename: "chart.png"
    static_response:
      choices:
        - message:
            role: "assistant"
            content: "Chart created successfully as 'chart.png'."

expected_gateway_output:
  - type: "final_response"
    kind: "task"
    status:
      state: "completed"
      message:
        parts:
          - kind: "text"
            text_contains:
              - "Chart created successfully"

expected_artifacts:
  - filename: "chart.png"
    mime_type: "image/png"
```

## Test Helpers

The [`test_helpers.py`](../../tests/integration/scenarios_programmatic/test_helpers.py) module provides utility functions:

- `prime_llm_server()`: Prime LLM server with responses
- `create_gateway_input_data()`: Create test input structure
- `submit_test_input()`: Submit input and get task_id
- `get_all_task_events()`: Collect all events for a task
- `extract_outputs_from_event_list()`: Extract response content
- `assert_final_response_text_contains()`: Verify response content
- `assert_llm_request_count()`: Verify number of LLM calls

## Best Practices

### 1. Use Helper Functions

Always use the helper functions from `test_helpers.py` to reduce boilerplate and ensure consistency.

### 2. Clear Test Isolation

Rely on auto-use fixtures for cleanup. Don't manually clear state unless necessary.

### 3. Descriptive Scenario IDs

Use clear, descriptive scenario IDs that indicate what the test is verifying.

### 4. Verify LLM Interactions

Always verify that the expected number of LLM requests were made:

```python
assert_llm_request_count(test_llm_server, 2, scenario_id)
```

### 5. Test Both Streaming and Non-Streaming

Test both modes when applicable:

```python
test_input = create_gateway_input_data(
    target_agent="TestAgent",
    user_identity="test@example.com",
    text_parts_content=["Hello"],
    scenario_id="test_id"
)
test_input["is_streaming"] = False  # For non-streaming
```

### 6. Use A2A Validator

Always include the `a2a_message_validator` fixture to ensure A2A compliance:

```python
async def test_something(
    a2a_message_validator: A2AMessageValidator,
    # ... other fixtures
):
    # Test code - all A2A messages will be validated
```

### 7. Test Error Scenarios

Test both success and failure paths:

```python
# Simulate LLM error
error_response = {
    "status_code": 500,
    "json_body": {"error": "Internal server error"}
}
test_llm_server.prime_responses([error_response])
```

### 8. Verify Artifacts

When testing artifact creation, verify both existence and content:

```python
artifacts = await test_artifact_service_instance.list_artifact_keys(
    app_name="TestAgent",
    user_id="user@example.com",
    session_id="session_id"
)
assert "output.txt" in artifacts

artifact = await test_artifact_service_instance.load_artifact(
    app_name="TestAgent",
    user_id="user@example.com",
    session_id="session_id",
    filename="output.txt"
)
assert artifact.inline_data.data == b"expected content"
```

## Running Tests

### Run All Integration Tests

```bash
pytest tests/integration/
```

### Run Specific Test File

```bash
pytest tests/integration/scenarios_programmatic/test_basic_flows.py
```

### Run Tests with Specific Markers

```bash
pytest tests/integration/ -m "agent and tools"
```

### Run with Verbose Output

```bash
pytest tests/integration/ -v -s
```

### Run Declarative Tests Only

```bash
pytest tests/integration/scenarios_declarative/
```

## Debugging Tests

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect Captured Requests

```python
captured_requests = test_llm_server.get_captured_requests()
for i, req in enumerate(captured_requests):
    print(f"Request {i}: {req.model_dump_json(indent=2)}")
```

### Pretty Print Event History

```python
from solace_agent_mesh.agent.testing.debug_utils import pretty_print_event_history

all_events = await get_all_task_events(gateway, task_id)
pretty_print_event_history(all_events)
```

### Check A2A Messages

The A2A validator logs all validated messages. Check test output for validation details.

## Common Patterns

### Testing Tool Calls

```python
# Prime LLM to call a tool
tool_call_response = {
    "choices": [{
        "message": {
            "role": "assistant",
            "tool_calls": [{
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "get_weather_tool",
                    "arguments": '{"location": "Paris"}'
                }
            }]
        },
        "finish_reason": "tool_calls"
    }]
}

# Prime LLM response after tool execution
final_response = {
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "The weather in Paris is sunny."
        },
        "finish_reason": "stop"
    }]
}

prime_llm_server(test_llm_server, [tool_call_response, final_response])
```

### Testing Agent Delegation

```python
# Configure peer agent response
test_a2a_agent_server_harness.prime_responses([{
    "static_response": {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Response from peer agent"
            }
        }]
    }
}])

# Test delegation through main agent
# ... submit task that triggers delegation ...

# Verify peer agent was called
assert len(test_a2a_agent_server_harness.captured_requests) > 0
```

### Testing Artifacts

```python
# Setup initial artifacts
setup_artifacts = [{
    "filename": "input.txt",
    "content": "Initial content",
    "mime_type": "text/plain"
}]

# Include in declarative test YAML or setup programmatically
# ... run test ...

# Verify artifact was modified/created
artifacts = await test_artifact_service_instance.list_artifact_keys(
    app_name="TestAgent",
    user_id="user@example.com",
    session_id="session_id"
)
assert "output.txt" in artifacts
```

## Troubleshooting

### Test Hangs or Times Out

- Check that LLM server has primed responses for all expected requests
- Verify timeout values are appropriate
- Check for deadlocks in async code

### A2A Validation Failures

- Review the detailed validation error message
- Check that message structure matches A2A schema
- Verify JSON-RPC compliance (id, method, params structure)

### Artifacts Not Found

- Verify app_name, user_id, and session_id match between setup and verification
- Check that artifact service fixture is properly injected
- Ensure artifacts are created before verification

### LLM Request Count Mismatch

- Check if agent is making unexpected LLM calls
- Verify tool execution paths
- Review captured requests to understand actual flow

## Additional Resources

- [Integration Test Examples](../../tests/integration/scenarios_programmatic/)
- [Declarative Test Examples](../../tests/integration/scenarios_declarative/test_data/)
- [Test Helpers Source](../../tests/integration/scenarios_programmatic/test_helpers.py)
- [Conftest Fixtures](../../tests/integration/conftest.py)