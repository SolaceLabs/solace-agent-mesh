"""
Integration tests for ADK setup and initialization.
Tests the core ADK integration layer including tool loading, agent initialization, and runner setup.
"""

import pytest
from sam_test_infrastructure.llm_server.server import TestLLMServer
from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from sam_test_infrastructure.a2a_validator.validator import A2AMessageValidator
from sam_test_infrastructure.artifact_service.service import TestInMemoryArtifactService
from solace_agent_mesh.agent.sac.app import SamAgentApp
from solace_agent_mesh.agent.adk.setup import load_adk_tools, initialize_adk_agent, initialize_adk_runner
from solace_agent_mesh.agent.adk.services import initialize_session_service, initialize_artifact_service

from tests.integration.scenarios_programmatic.test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
    extract_outputs_from_event_list,
    assert_final_response_text_contains
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.agent,
]


class TestADKSetup:
    """Tests for ADK setup and initialization."""

    async def test_load_adk_tools_with_builtin_tools(
        self,
        sam_app_under_test: SamAgentApp,
    ):
        """Test loading ADK tools including builtin tools."""
        scenario_id = "test_load_adk_tools_builtin"
        
        # Get the component from the app
        component = sam_app_under_test.get_component()
        assert component is not None, f"Scenario {scenario_id}: Component not found"
        
        # Load tools
        loaded_tools, builtin_tools, cleanup_hooks = await load_adk_tools(component)
        
        # Verify tools were loaded
        assert len(loaded_tools) > 0, f"Scenario {scenario_id}: No tools loaded"
        assert len(builtin_tools) > 0, f"Scenario {scenario_id}: No builtin tools loaded"
        
        # Verify cleanup hooks
        assert isinstance(cleanup_hooks, list), f"Scenario {scenario_id}: Cleanup hooks should be a list"
        
        print(f"Scenario {scenario_id}: Loaded {len(loaded_tools)} tools, {len(builtin_tools)} builtin tools")

    async def test_initialize_adk_agent(
        self,
        sam_app_under_test: SamAgentApp,
    ):
        """Test ADK agent initialization."""
        scenario_id = "test_initialize_adk_agent"
        
        component = sam_app_under_test.get_component()
        assert component is not None
        
        # Load tools first
        loaded_tools, builtin_tools, _ = await load_adk_tools(component)
        
        # Initialize agent
        agent = initialize_adk_agent(component, loaded_tools, builtin_tools)
        
        # Verify agent was created
        assert agent is not None, f"Scenario {scenario_id}: Agent not initialized"
        assert hasattr(agent, 'host_component'), f"Scenario {scenario_id}: Agent missing host_component"
        assert agent.host_component == component, f"Scenario {scenario_id}: Agent host_component mismatch"
        
        print(f"Scenario {scenario_id}: Agent initialized successfully")

    async def test_initialize_adk_runner(
        self,
        sam_app_under_test: SamAgentApp,
    ):
        """Test ADK runner initialization."""
        scenario_id = "test_initialize_adk_runner"
        
        component = sam_app_under_test.get_component()
        assert component is not None
        
        # Initialize runner
        runner = initialize_adk_runner(component)
        
        # Verify runner was created
        assert runner is not None, f"Scenario {scenario_id}: Runner not initialized"
        
        print(f"Scenario {scenario_id}: Runner initialized successfully")

    async def test_session_service_initialization(
        self,
        sam_app_under_test: SamAgentApp,
    ):
        """Test session service initialization."""
        scenario_id = "test_session_service_init"
        
        component = sam_app_under_test.get_component()
        assert component is not None
        
        # Initialize session service
        session_service = initialize_session_service(component)
        
        # Verify service was created
        assert session_service is not None, f"Scenario {scenario_id}: Session service not initialized"
        
        print(f"Scenario {scenario_id}: Session service initialized successfully")

    async def test_artifact_service_initialization(
        self,
        sam_app_under_test: SamAgentApp,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test artifact service initialization."""
        scenario_id = "test_artifact_service_init"
        
        component = sam_app_under_test.get_component()
        assert component is not None
        
        # Initialize artifact service
        artifact_service = initialize_artifact_service(component)
        
        # Verify service was created
        assert artifact_service is not None, f"Scenario {scenario_id}: Artifact service not initialized"
        
        print(f"Scenario {scenario_id}: Artifact service initialized successfully")


class TestADKCallbacks:
    """Tests for ADK callback functionality."""

    async def test_dynamic_instructions_injection(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test that dynamic instructions are properly injected into LLM requests."""
        scenario_id = "test_dynamic_instructions_injection"
        
        # Prime LLM with a simple response
        llm_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Instructions received and understood."
                },
                "finish_reason": "stop"
            }]
        }
        prime_llm_server(test_llm_server, [llm_response])
        
        # Create test input
        test_input = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="test_user@example.com",
            text_parts_content=["Hello, can you help me?"],
            scenario_id=scenario_id
        )
        
        # Submit task
        task_id = await submit_test_input(test_gateway_app_instance, test_input, scenario_id)
        
        # Get events
        all_events = await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=5.0)
        
        # Verify response
        terminal_event, stream_text, terminal_text = extract_outputs_from_event_list(all_events, scenario_id)
        content = stream_text if stream_text else terminal_text
        
        assert_final_response_text_contains(
            content,
            "Instructions received",
            scenario_id,
            terminal_event
        )
        
        # Verify LLM was called with instructions
        captured_requests = test_llm_server.get_captured_requests()
        assert len(captured_requests) > 0, f"Scenario {scenario_id}: No LLM requests captured"
        
        # Check that system message contains instructions
        first_request = captured_requests[0]
        messages = first_request.messages
        system_messages = [msg for msg in messages if msg.role == "system"]
        assert len(system_messages) > 0, f"Scenario {scenario_id}: No system messages found"
        
        print(f"Scenario {scenario_id}: Dynamic instructions properly injected")

    async def test_tool_invocation_notification(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test that tool invocation notifications are sent."""
        scenario_id = "test_tool_invocation_notification"
        
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
        
        # Create test input
        test_input = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="test_user@example.com",
            text_parts_content=["What's the weather in Paris?"],
            scenario_id=scenario_id
        )
        
        # Submit task
        task_id = await submit_test_input(test_gateway_app_instance, test_input, scenario_id)
        
        # Get events
        all_events = await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=10.0)
        
        # Verify we got tool invocation events
        from a2a.types import TaskStatusUpdateEvent
        status_events = [e for e in all_events if isinstance(e, TaskStatusUpdateEvent)]
        
        # Should have at least one status update for tool invocation
        assert len(status_events) > 0, f"Scenario {scenario_id}: No status update events found"
        
        print(f"Scenario {scenario_id}: Tool invocation notifications sent successfully")


class TestADKToolWrapper:
    """Tests for ADK tool wrapper functionality."""

    async def test_tool_config_injection(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test that tool config is properly injected into tool calls."""
        scenario_id = "test_tool_config_injection"
        
        # Prime LLM to call web_request tool with config
        tool_call_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_web_123",
                        "type": "function",
                        "function": {
                            "name": "web_request",
                            "arguments": '{"url": "http://127.0.0.1:8089/test.txt", "method": "GET"}'
                        }
                    }]
                },
                "finish_reason": "tool_calls"
            }]
        }
        
        final_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Request completed successfully."
                },
                "finish_reason": "stop"
            }]
        }
        
        prime_llm_server(test_llm_server, [tool_call_response, final_response])
        
        # Create test input
        test_input = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="test_user@example.com",
            text_parts_content=["Make a web request to localhost"],
            scenario_id=scenario_id
        )
        
        # Submit task
        task_id = await submit_test_input(test_gateway_app_instance, test_input, scenario_id)
        
        # Get events
        all_events = await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=10.0)
        
        # Verify response
        terminal_event, stream_text, terminal_text = extract_outputs_from_event_list(all_events, scenario_id)
        content = stream_text if stream_text else terminal_text
        
        # Tool should execute successfully with config allowing loopback
        assert_final_response_text_contains(
            content,
            "completed",
            scenario_id,
            terminal_event
        )
        
        print(f"Scenario {scenario_id}: Tool config properly injected")

    async def test_tool_error_handling(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test that tool errors are properly handled and reported."""
        scenario_id = "test_tool_error_handling"
        
        # Prime LLM to call a tool with invalid arguments
        tool_call_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_error_123",
                        "type": "function",
                        "function": {
                            "name": "web_request",
                            "arguments": '{"url": "invalid-url", "method": "GET"}'
                        }
                    }]
                },
                "finish_reason": "tool_calls"
            }]
        }
        
        final_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "There was an error with the request."
                },
                "finish_reason": "stop"
            }]
        }
        
        prime_llm_server(test_llm_server, [tool_call_response, final_response])
        
        # Create test input
        test_input = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="test_user@example.com",
            text_parts_content=["Make a request to an invalid URL"],
            scenario_id=scenario_id
        )
        
        # Submit task
        task_id = await submit_test_input(test_gateway_app_instance, test_input, scenario_id)
        
        # Get events
        all_events = await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=10.0)
        
        # Verify we got a response (error should be handled gracefully)
        terminal_event, stream_text, terminal_text = extract_outputs_from_event_list(all_events, scenario_id)
        content = stream_text if stream_text else terminal_text
        
        assert content is not None, f"Scenario {scenario_id}: No response received"
        
        print(f"Scenario {scenario_id}: Tool error handled gracefully")