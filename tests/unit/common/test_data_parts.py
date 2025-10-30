"""
Unit tests for common/data_parts.py
Tests Pydantic models for structured data payloads used in A2A DataPart objects.
"""

import pytest
from pydantic import ValidationError

from solace_agent_mesh.common.data_parts import (
    ToolInvocationStartData,
    LlmInvocationData,
    AgentProgressUpdateData,
    ArtifactCreationProgressData,
    ToolResultData,
)


class TestToolInvocationStartData:
    """Test ToolInvocationStartData model."""

    def test_valid_tool_invocation_start(self):
        """Test creating a valid ToolInvocationStartData."""
        data = ToolInvocationStartData(
            tool_name="get_weather",
            tool_args={"location": "Paris", "units": "celsius"},
            function_call_id="call_123",
        )
        
        assert data.type == "tool_invocation_start"
        assert data.tool_name == "get_weather"
        assert data.tool_args == {"location": "Paris", "units": "celsius"}
        assert data.function_call_id == "call_123"

    def test_tool_invocation_start_type_is_literal(self):
        """Test that type field is always 'tool_invocation_start'."""
        data = ToolInvocationStartData(
            tool_name="test_tool",
            tool_args={},
            function_call_id="call_456",
        )
        assert data.type == "tool_invocation_start"

    def test_tool_invocation_start_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            ToolInvocationStartData(tool_name="test_tool")

    def test_tool_invocation_start_with_empty_args(self):
        """Test tool invocation with empty arguments."""
        data = ToolInvocationStartData(
            tool_name="no_arg_tool",
            tool_args={},
            function_call_id="call_789",
        )
        assert data.tool_args == {}

    def test_tool_invocation_start_with_complex_args(self):
        """Test tool invocation with complex nested arguments."""
        complex_args = {
            "config": {
                "nested": {"value": 123},
                "list": [1, 2, 3],
            },
            "flag": True,
        }
        data = ToolInvocationStartData(
            tool_name="complex_tool",
            tool_args=complex_args,
            function_call_id="call_complex",
        )
        assert data.tool_args == complex_args

    def test_tool_invocation_start_serialization(self):
        """Test serialization to dict."""
        data = ToolInvocationStartData(
            tool_name="test_tool",
            tool_args={"key": "value"},
            function_call_id="call_123",
        )
        serialized = data.model_dump()
        
        assert serialized["type"] == "tool_invocation_start"
        assert serialized["tool_name"] == "test_tool"
        assert serialized["tool_args"] == {"key": "value"}
        assert serialized["function_call_id"] == "call_123"


class TestLlmInvocationData:
    """Test LlmInvocationData model."""

    def test_valid_llm_invocation_without_usage(self):
        """Test creating a valid LlmInvocationData without usage."""
        request_data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
        }
        data = LlmInvocationData(request=request_data)
        
        assert data.type == "llm_invocation"
        assert data.request == request_data
        assert data.usage is None

    def test_valid_llm_invocation_with_usage(self):
        """Test creating a valid LlmInvocationData with usage."""
        request_data = {"model": "gpt-4", "messages": []}
        usage_data = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cached_input_tokens": 20,
            "model": "gpt-4",
        }
        data = LlmInvocationData(request=request_data, usage=usage_data)
        
        assert data.type == "llm_invocation"
        assert data.request == request_data
        assert data.usage == usage_data

    def test_llm_invocation_type_is_literal(self):
        """Test that type field is always 'llm_invocation'."""
        data = LlmInvocationData(request={"model": "test"})
        assert data.type == "llm_invocation"

    def test_llm_invocation_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            LlmInvocationData()

    def test_llm_invocation_serialization(self):
        """Test serialization to dict."""
        request_data = {"model": "gpt-4"}
        usage_data = {"input_tokens": 10, "output_tokens": 5, "model": "gpt-4"}
        data = LlmInvocationData(request=request_data, usage=usage_data)
        
        serialized = data.model_dump()
        assert serialized["type"] == "llm_invocation"
        assert serialized["request"] == request_data
        assert serialized["usage"] == usage_data


class TestAgentProgressUpdateData:
    """Test AgentProgressUpdateData model."""

    def test_valid_agent_progress_update(self):
        """Test creating a valid AgentProgressUpdateData."""
        data = AgentProgressUpdateData(status_text="Processing your request...")
        
        assert data.type == "agent_progress_update"
        assert data.status_text == "Processing your request..."

    def test_agent_progress_update_type_is_literal(self):
        """Test that type field is always 'agent_progress_update'."""
        data = AgentProgressUpdateData(status_text="Working...")
        assert data.type == "agent_progress_update"

    def test_agent_progress_update_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            AgentProgressUpdateData()

    def test_agent_progress_update_with_empty_status(self):
        """Test progress update with empty status text."""
        data = AgentProgressUpdateData(status_text="")
        assert data.status_text == ""
        """Test progress update with long status text."""
        long_status = "A" * 1000
        data = AgentProgressUpdateData(status_text=long_status)
        assert data.status_text == long_status
        assert len(data.status_text) == 1000

        """Test serialization to dict."""
        data = AgentProgressUpdateData(status_text="Test status")
        serialized = data.model_dump()
        
        assert serialized["type"] == "agent_progress_update"
        assert serialized["status_text"] == "Test status"

        """Test creating a valid ToolResultData without LLM usage."""
        result_data = {"status": "success", "data": [1, 2, 3]}
        data = ToolResultData(
            tool_name="data_processor",
            result_data=result_data,
            function_call_id="call_123",
        )
        
        assert data.type == "tool_result"
        assert data.tool_name == "data_processor"
        assert data.result_data == result_data
        assert data.function_call_id == "call_123"
        assert data.llm_usage is None


        """Test creating a valid ToolResultData with LLM usage."""
        result_data = {"output": "processed"}
        llm_usage = {
            "input_tokens": 50,
            "output_tokens": 25,
            "model": "gpt-4",
        }
        data = ToolResultData(
            tool_name="llm_tool",
            result_data=result_data,
            function_call_id="call_456",
            llm_usage=llm_usage,
        )
        
        assert data.type == "tool_result"
        assert data.llm_usage == llm_usage

        """Test tool result with various result data types."""
        # String result
        data1 = ToolResultData(
            tool_name="tool1",
            result_data="string result",
            function_call_id="call_1",
        )
        assert data1.result_data == "string result"
        
        # List result
        data2 = ToolResultData(
            tool_name="tool2",
            result_data=[1, 2, 3],
            function_call_id="call_2",
        )
        assert data2.result_data == [1, 2, 3]
        
        # Dict result
        data3 = ToolResultData(
            tool_name="tool3",
            result_data={"key": "value"},
            function_call_id="call_3",
        )
        assert data3.result_data == {"key": "value"}
        
        # None result
        data4 = ToolResultData(
            tool_name="tool4",
            result_data=None,
            function_call_id="call_4",
        )
        assert data4.result_data is None

        """Test serialization to dict."""
        result_data = {"status": "ok"}
        llm_usage = {"input_tokens": 10, "output_tokens": 5, "model": "gpt-4"}
        data = ToolResultData(
            tool_name="test_tool",
            result_data=result_data,
            function_call_id="call_123",
            llm_usage=llm_usage,
        )
        
        serialized = data.model_dump()
        assert serialized["type"] == "tool_result"
        assert serialized["tool_name"] == "test_tool"
        assert serialized["result_data"] == result_data
        assert serialized["function_call_id"] == "call_123"
        assert serialized["llm_usage"] == llm_usage

        """Test that signal types can be discriminated by their type field."""
        signals = [
            ToolInvocationStartData(
                tool_name="t1", tool_args={}, function_call_id="c1"
            ),
            LlmInvocationData(request={}),
            AgentProgressUpdateData(status_text="test"),
            ArtifactCreationProgressData(
                filename="f", bytes_saved=1, artifact_chunk="c"
            ),
            ToolResultData(tool_name="t2", result_data={}, function_call_id="c2"),
        ]
        
        expected_types = [
            "tool_invocation_start",
            "llm_invocation",
            "agent_progress_update",
            "artifact_creation_progress",
            "tool_result",
        ]
        
        for signal, expected_type in zip(signals, expected_types):
            assert signal.type == expected_type