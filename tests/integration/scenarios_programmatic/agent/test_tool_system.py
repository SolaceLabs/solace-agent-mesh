"""
Integration tests for the tool system.
Tests builtin tools, dynamic tools, and tool registry functionality.
"""

import pytest
from typing import Dict, Any
from sam_test_infrastructure.llm_server.server import TestLLMServer
from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from sam_test_infrastructure.a2a_validator.validator import A2AMessageValidator
from solace_agent_mesh.agent.sac.app import SamAgentApp
from solace_agent_mesh.agent.tools.registry import tool_registry
from solace_agent_mesh.agent.tools.tool_definition import BuiltinTool

from tests.integration.scenarios_programmatic.test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
    extract_outputs_from_event_list,
    assert_final_response_text_contains,
    assert_llm_request_count,
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.agent,
]


class TestBuiltinTools:
    """Tests for builtin tool functionality."""

    async def test_data_analysis_tool(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test data analysis tool execution."""
        scenario_id = "test_data_analysis_tool"
        
        # Prime LLM to call chart creation tool
        import json
        plotly_config = {"data": [{"x": [1, 2, 3, 4, 5], "y": [1, 4, 9, 16, 25], "type": "scatter"}], "layout": {"title": "Sample Chart"}}
        tool_call_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_chart_123",
                        "type": "function",
                        "function": {
                            "name": "create_chart_from_plotly_config",
                            "arguments": json.dumps({"config_content": json.dumps(plotly_config), "output_filename": "test_chart.png"})
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
                    "content": "Chart created successfully as test_chart.png"
                },
                "finish_reason": "stop"
            }]
        }
        
        prime_llm_server(test_llm_server, [tool_call_response, final_response])
        
        # Create test input
        test_input = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="test_user@example.com",
            text_parts_content=["Create a chart from this data"],
            scenario_id=scenario_id
        )
        
        # Submit task
        task_id = await submit_test_input(test_gateway_app_instance, test_input, scenario_id)
        
        # Get events
        all_events = await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=10.0)
        
        # Verify response
        terminal_event, stream_text, terminal_text = extract_outputs_from_event_list(all_events, scenario_id)
        content = stream_text if stream_text else terminal_text
        
        assert_final_response_text_contains(
            content,
            "Chart created",
            scenario_id,
            terminal_event
        )
        
        print(f"Scenario {scenario_id}: Data analysis tool executed successfully")

    async def test_web_request_tool(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test web request tool with loopback allowed."""
        scenario_id = "test_web_request_tool"
        
        # Prime LLM to call web_request tool
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
        
        assert_final_response_text_contains(
            content,
            "completed",
            scenario_id,
            terminal_event
        )
        
        print(f"Scenario {scenario_id}: Web request tool executed successfully")

    async def test_mcp_tool_stdio(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test MCP tool with stdio transport."""
        scenario_id = "test_mcp_tool_stdio"
        
        # Prime LLM to call MCP tool
        tool_call_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_mcp_123",
                        "type": "function",
                        "function": {
                            "name": "get_data_stdio",
                            "arguments": '{"key": "test_key"}'
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
                    "content": "MCP tool executed successfully."
                },
                "finish_reason": "stop"
            }]
        }
        
        prime_llm_server(test_llm_server, [tool_call_response, final_response])
        
        # Create test input
        test_input = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="test_user@example.com",
            text_parts_content=["Get data using MCP stdio"],
            scenario_id=scenario_id
        )
        
        # Submit task
        task_id = await submit_test_input(test_gateway_app_instance, test_input, scenario_id)
        
        # Get events
        all_events = await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=15.0)
        
        # Verify response
        terminal_event, stream_text, terminal_text = extract_outputs_from_event_list(all_events, scenario_id)
        content = stream_text if stream_text else terminal_text
        
        assert content is not None, f"Scenario {scenario_id}: No response received"
        
        print(f"Scenario {scenario_id}: MCP stdio tool executed successfully")


class TestDynamicTools:
    """Tests for dynamic tool loading and execution."""

    async def test_dynamic_tool_loading(
        self,
        sam_app_under_test: SamAgentApp,
    ):
        """Test that dynamic tools are loaded correctly."""
        scenario_id = "test_dynamic_tool_loading"
        
        # Get the CombinedDynamicAgent component
        component = sam_app_under_test.get_component()
        
        if component is None:
            pytest.skip("CombinedDynamicAgent not available in test configuration")
        
        # Verify tools were loaded
        agent = component.adk_agent
        assert agent is not None, f"Scenario {scenario_id}: Agent not initialized"
        
        print(f"Scenario {scenario_id}: Dynamic tools loaded successfully")

    async def test_dynamic_tool_with_config(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test dynamic tool execution with configuration."""
        scenario_id = "test_dynamic_tool_with_config"
        
        # Check if ConfigContextAgent is available
        component = sam_app_under_test.get_component()
        if component is None:
            pytest.skip("ConfigContextAgent not available in test configuration")
        
        # Prime LLM with a simple response
        llm_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Dynamic tool with config executed."
                },
                "finish_reason": "stop"
            }]
        }
        prime_llm_server(test_llm_server, [llm_response])
        
        # Create test input
        test_input = create_gateway_input_data(
            target_agent="ConfigContextAgent",
            user_identity="test_user@example.com",
            text_parts_content=["Test dynamic tool with config"],
            scenario_id=scenario_id
        )
        
        # Submit task
        task_id = await submit_test_input(test_gateway_app_instance, test_input, scenario_id)
        
        # Get events
        all_events = await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=5.0)
        
        # Verify response
        terminal_event, stream_text, terminal_text = extract_outputs_from_event_list(all_events, scenario_id)
        content = stream_text if stream_text else terminal_text
        
        assert content is not None, f"Scenario {scenario_id}: No response received"
        
        print(f"Scenario {scenario_id}: Dynamic tool with config executed successfully")


class TestToolRegistry:
    """Tests for tool registry functionality."""

    def test_tool_registry_registration(
        self,
        clear_tool_registry_fixture,
    ):
        """Test registering tools in the registry."""
        scenario_id = "test_tool_registry_registration"
        
        # Create a test tool
        async def test_tool_func(param: str) -> dict:
            """A test tool function."""
            return {"result": f"Processed: {param}"}
        
        from google.genai import types as adk_types
        test_tool = BuiltinTool(
            name="test_registry_tool",
            description="A test tool for registry",
            implementation=test_tool_func,
            parameters=adk_types.Schema(
                type=adk_types.Type.OBJECT,
                properties={"param": adk_types.Schema(type=adk_types.Type.STRING)}
            ),
            category="test"
        )
        
        # Register the tool
        tool_registry.register(test_tool)
        
        # Verify it's registered
        registered_tools = tool_registry.get_all_tools()
        tool_names = [t.name for t in registered_tools]
        
        assert "test_registry_tool" in tool_names, f"Scenario {scenario_id}: Tool not registered"
        
        print(f"Scenario {scenario_id}: Tool registered successfully")

    def test_tool_registry_get_by_name(
        self,
        clear_tool_registry_fixture,
    ):
        """Test retrieving tools by name from registry."""
        scenario_id = "test_tool_registry_get_by_name"
        
        # Create and register a test tool
        async def test_tool_func(param: str) -> dict:
            """A test tool function."""
            return {"result": param}
        
        from google.genai import types as adk_types
        test_tool = BuiltinTool(
            name="test_get_tool",
            description="A test tool",
            implementation=test_tool_func,
            parameters=adk_types.Schema(
                type=adk_types.Type.OBJECT,
                properties={"param": adk_types.Schema(type=adk_types.Type.STRING)}
            ),
            category="test"
        )
        
        tool_registry.register(test_tool)
        
        # Retrieve by name
        retrieved_tool = tool_registry.get_tool_by_name("test_get_tool")
        
        assert retrieved_tool is not None, f"Scenario {scenario_id}: Tool not found"
        assert retrieved_tool.name == "test_get_tool", f"Scenario {scenario_id}: Tool name mismatch"
        
        print(f"Scenario {scenario_id}: Tool retrieved by name successfully")

    def test_tool_registry_get_by_category(
        self,
        clear_tool_registry_fixture,
    ):
        """Test retrieving tools by category from registry."""
        scenario_id = "test_tool_registry_get_by_category"
        
        # Create and register multiple tools in same category
        for i in range(3):
            async def test_tool_func(param: str) -> dict:
                """A test tool function."""
                return {"result": param}
            
            from google.genai import types as adk_types
            test_tool = BuiltinTool(
                name=f"test_category_tool_{i}",
                description=f"Test tool {i}",
                implementation=test_tool_func,
                parameters=adk_types.Schema(
                    type=adk_types.Type.OBJECT,
                    properties={"param": adk_types.Schema(type=adk_types.Type.STRING)}
                ),
                category="test_category"
            )
            
            tool_registry.register(test_tool)
        
        # Retrieve by category
        category_tools = tool_registry.get_tools_by_category("test_category")
        
        assert len(category_tools) == 3, f"Scenario {scenario_id}: Expected 3 tools, got {len(category_tools)}"
        
        print(f"Scenario {scenario_id}: Tools retrieved by category successfully")


class TestPeerAgentTool:
    """Tests for peer agent tool functionality."""

    async def test_peer_agent_delegation(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test delegating tasks to peer agents."""
        scenario_id = "test_peer_agent_delegation"
        
        # Prime main agent to delegate to peer
        delegation_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_peer_123",
                        "type": "function",
                        "function": {
                            "name": "TestPeerAgentA",
                            "arguments": '{"task_description": "Analyze this data"}'
                        }
                    }]
                },
                "finish_reason": "tool_calls"
            }]
        }
        # Prime peer agent response
        peer_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Peer agent completed the analysis."
                },
                "finish_reason": "stop"
            }]
        }
        
        # Prime main agent final response
        final_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "The peer agent has completed the task."
                },
                "finish_reason": "stop"
            }]
        }
        
        prime_llm_server(test_llm_server, [delegation_response, peer_response, final_response])
        
        # Create test input
        test_input = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="test_user@example.com",
            text_parts_content=["Delegate this task to TestPeerAgentA"],
            scenario_id=scenario_id
        )
        
        # Submit task
        task_id = await submit_test_input(test_gateway_app_instance, test_input, scenario_id)
        
        # Get events
        all_events = await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=15.0)
        
        # Verify response
        terminal_event, stream_text, terminal_text = extract_outputs_from_event_list(all_events, scenario_id)
        content = stream_text if stream_text else terminal_text
        
        assert content is not None, f"Scenario {scenario_id}: No response received"
        
        print(f"Scenario {scenario_id}: Peer agent delegation executed successfully")
                