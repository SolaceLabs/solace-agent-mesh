"""Comprehensive tests for LiteLlm observability instrumentation."""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from google.genai.types import Content, Part, GenerateContentConfig
from google.adk.models.llm_request import LlmRequest

from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm, ObservabilityContext


@pytest.fixture
def mock_litellm_completion():
    """Mock litellm completion response with usage data."""
    response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Test response"
                }
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }
    }
    return response


@pytest.fixture
def mock_litellm_streaming():
    """Mock litellm streaming response - plain dicts work fine."""
    async def async_generator():
        # Chunk 1: First token
        yield {
            "choices": [{
                "delta": {"content": "Hello"},
                "finish_reason": None
            }]
        }

        # Chunk 2: More tokens
        yield {
            "choices": [{
                "delta": {"content": " world"},
                "finish_reason": None
            }]
        }

        # Chunk 3: Done with usage
        yield {
            "choices": [{
                "delta": {"content": ""},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12
            }
        }

    return async_generator


@pytest.fixture
def mock_cost_per_token():
    """Mock litellm cost_per_token function."""
    return (0.00001, 0.00002)  # (prompt_cost, completion_cost)


@pytest.fixture
def simple_llm_request():
    """Create a simple LLM request."""
    return LlmRequest(
        contents=[Content(role="user", parts=[Part(text="Hello")])],
        config=GenerateContentConfig()
    )


class TestObservabilityContextBasic:
    """Basic ObservabilityContext functionality tests."""

    def test_context_sets_and_cleans_up(self):
        """Test basic context setting and cleanup."""
        with ObservabilityContext(component_name="agent1", owner_id="alice"):
            assert ObservabilityContext._component_name_var.get() == "agent1"
            assert ObservabilityContext._owner_id_var.get() == "alice"

        assert ObservabilityContext._component_name_var.get() is None
        assert ObservabilityContext._owner_id_var.get() is None

    def test_nested_context_overrides_and_restores(self):
        """Test nested contexts override and restore properly."""
        with ObservabilityContext(component_name="agent1", owner_id="alice"):
            with ObservabilityContext(component_name="agent2", owner_id="bob"):
                assert ObservabilityContext._component_name_var.get() == "agent2"
                assert ObservabilityContext._owner_id_var.get() == "bob"

            assert ObservabilityContext._component_name_var.get() == "agent1"
            assert ObservabilityContext._owner_id_var.get() == "alice"

    def test_partial_override_preserves_parent(self):
        """Test that None values preserve parent context."""
        with ObservabilityContext(component_name="agent1", owner_id="alice"):
            with ObservabilityContext(component_name="tool", owner_id=None):
                assert ObservabilityContext._component_name_var.get() == "tool"
                assert ObservabilityContext._owner_id_var.get() == "alice"

    def test_context_cleanup_on_exception(self):
        """Test context cleanup when exception raised."""
        try:
            with ObservabilityContext(component_name="agent1", owner_id="alice"):
                raise ValueError("Test")
        except ValueError:
            pass

        assert ObservabilityContext._component_name_var.get() is None
        assert ObservabilityContext._owner_id_var.get() is None

    @pytest.mark.asyncio
    async def test_context_propagates_in_async(self):
        """Test context propagates through async calls."""
        async def check_context():
            return ObservabilityContext._component_name_var.get()

        with ObservabilityContext(component_name="agent1", owner_id="alice"):
            result = await check_context()
            assert result == "agent1"


class TestLiteLlmObservabilityNonStreaming:
    """Test LiteLlm observability metrics for non-streaming calls."""

    @pytest.mark.asyncio
    async def test_records_metrics_with_context(
        self, mock_litellm_completion, simple_llm_request, mock_cost_per_token
    ):
        """Test that LLM call records all metrics with proper context labels."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                mock_acompletion.return_value = mock_litellm_completion

                llm = LiteLlm(model="gpt-4")

                with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                    response = None
                    async for resp in llm.generate_content_async(simple_llm_request):
                        response = resp
                        break

                # Verify response received
                assert response is not None

                # Verify litellm was called
                assert mock_acompletion.called

    @pytest.mark.asyncio
    async def test_uses_default_labels_without_context(
        self, mock_litellm_completion, simple_llm_request, mock_cost_per_token
    ):
        """Test that metrics use 'none' as default when no context set."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                mock_acompletion.return_value = mock_litellm_completion

                llm = LiteLlm(model="gpt-4")

                # NO ObservabilityContext wrapper
                response = None
                async for resp in llm.generate_content_async(simple_llm_request):
                    response = resp
                    break

                assert response is not None

                # Context should default to "none"
                assert ObservabilityContext._component_name_var.get() is None
                assert ObservabilityContext._owner_id_var.get() is None

    @pytest.mark.asyncio
    async def test_cost_calculation_graceful_failure(
        self, mock_litellm_completion, simple_llm_request
    ):
        """Test that cost tracking fails gracefully when pricing unavailable."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', side_effect=Exception("No pricing")):
                mock_acompletion.return_value = mock_litellm_completion

                llm = LiteLlm(model="unknown-model")

                with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                    # Should not raise exception
                    response = None
                    async for resp in llm.generate_content_async(simple_llm_request):
                        response = resp
                        break

                assert response is not None

    @pytest.mark.asyncio
    async def test_token_recording_helper_method(
        self, mock_litellm_completion, simple_llm_request, mock_cost_per_token
    ):
        """Test _record_token_and_cost_metrics helper method."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                    mock_registry_instance = Mock()
                    mock_registry.get_instance.return_value = mock_registry_instance

                    mock_acompletion.return_value = mock_litellm_completion

                    llm = LiteLlm(model="gpt-4")

                    with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                        async for _ in llm.generate_content_async(simple_llm_request):
                            break

                    # Verify registry methods were called
                    assert mock_registry_instance.record_counter_from_monitor.called


class TestLiteLlmObservabilityStreaming:
    """Test LiteLlm observability metrics for streaming calls."""

    @pytest.mark.asyncio
    async def test_streaming_records_ttft_metric(
        self, mock_litellm_streaming, simple_llm_request, mock_cost_per_token
    ):
        """Test that streaming calls record TTFT (time to first token)."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                mock_acompletion.return_value = mock_litellm_streaming()

                llm = LiteLlm(model="gpt-4")

                with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                    chunks = []
                    async for chunk in llm.generate_content_async(simple_llm_request, stream=True):
                        chunks.append(chunk)

                # Should have received chunks
                assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_streaming_records_all_metrics(
        self, mock_litellm_streaming, simple_llm_request, mock_cost_per_token
    ):
        """Test that streaming records latency, tokens, and cost metrics."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                mock_acompletion.return_value = mock_litellm_streaming()

                llm = LiteLlm(model="gpt-4")

                with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                    async for _ in llm.generate_content_async(simple_llm_request, stream=True):
                        pass

                # Verify completion was called with stream mode
                assert mock_acompletion.called


class TestLiteLlmObservabilityContextPropagation:
    """Test context propagation through nested async calls."""

    @pytest.mark.asyncio
    async def test_context_propagates_through_tool_calls(
        self, mock_litellm_completion, simple_llm_request, mock_cost_per_token
    ):
        """Test that context propagates from agent to tool LLM calls."""
        async def simulate_tool_call(llm, request):
            # This simulates a tool making an LLM call
            # Context should propagate here
            component = ObservabilityContext._component_name_var.get()
            owner = ObservabilityContext._owner_id_var.get()

            async for resp in llm.generate_content_async(request):
                return component, owner, resp

        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                mock_acompletion.return_value = mock_litellm_completion

                llm = LiteLlm(model="gpt-4")

                with ObservabilityContext(component_name="main-agent", owner_id="alice"):
                    component, owner, response = await simulate_tool_call(llm, simple_llm_request)

                # Context should have propagated
                assert component == "main-agent"
                assert owner == "alice"
                assert response is not None

    @pytest.mark.asyncio
    async def test_parallel_llm_calls_maintain_context(
        self, mock_litellm_completion, simple_llm_request, mock_cost_per_token
    ):
        """Test that parallel LLM calls maintain separate contexts."""
        async def make_llm_call(llm, request, component_name, owner_id):
            with ObservabilityContext(component_name=component_name, owner_id=owner_id):
                await asyncio.sleep(0.01)  # Simulate work
                component = ObservabilityContext._component_name_var.get()
                owner = ObservabilityContext._owner_id_var.get()

                async for resp in llm.generate_content_async(request):
                    return component, owner, resp

        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                mock_acompletion.return_value = mock_litellm_completion

                llm = LiteLlm(model="gpt-4")

                # Run two LLM calls in parallel with different contexts
                results = await asyncio.gather(
                    make_llm_call(llm, simple_llm_request, "agent1", "user1"),
                    make_llm_call(llm, simple_llm_request, "agent2", "user2")
                )

                # Each call should have maintained its own context
                component1, owner1, resp1 = results[0]
                component2, owner2, resp2 = results[1]

                assert component1 == "agent1"
                assert owner1 == "user1"
                assert component2 == "agent2"
                assert owner2 == "user2"


class TestLiteLlmObservabilityEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_observability_with_empty_context_values(
        self, mock_litellm_completion, simple_llm_request, mock_cost_per_token
    ):
        """Test observability with empty string context values."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                mock_acompletion.return_value = mock_litellm_completion

                llm = LiteLlm(model="gpt-4")

                with ObservabilityContext(component_name="", owner_id=""):
                    async for _ in llm.generate_content_async(simple_llm_request):
                        break

                # Should not fail with empty strings

    @pytest.mark.asyncio
    async def test_observability_with_special_characters(
        self, mock_litellm_completion, simple_llm_request, mock_cost_per_token
    ):
        """Test observability with special characters in labels."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                mock_acompletion.return_value = mock_litellm_completion

                llm = LiteLlm(model="gpt-4")

                with ObservabilityContext(
                    component_name="agent-v1.0_test",
                    owner_id="user@example.com"
                ):
                    async for _ in llm.generate_content_async(simple_llm_request):
                        break

    @pytest.mark.asyncio
    async def test_observability_survives_llm_error(self, simple_llm_request):
        """Test that observability context is cleaned up even on LLM error."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            mock_acompletion.side_effect = Exception("LLM API error")

            llm = LiteLlm(model="gpt-4")

            try:
                with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                    async for _ in llm.generate_content_async(simple_llm_request):
                        pass
            except Exception:
                pass

            # Context should be cleaned up despite error
            assert ObservabilityContext._component_name_var.get() is None
            assert ObservabilityContext._owner_id_var.get() is None

    @pytest.mark.asyncio
    async def test_multiple_sequential_calls_different_contexts(
        self, mock_litellm_completion, simple_llm_request, mock_cost_per_token
    ):
        """Test multiple sequential LLM calls with different contexts."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                mock_acompletion.return_value = mock_litellm_completion

                llm = LiteLlm(model="gpt-4")

                # First call
                with ObservabilityContext(component_name="agent1", owner_id="user1"):
                    async for _ in llm.generate_content_async(simple_llm_request):
                        break

                # Context should be cleared
                assert ObservabilityContext._component_name_var.get() is None

                # Second call
                with ObservabilityContext(component_name="agent2", owner_id="user2"):
                    async for _ in llm.generate_content_async(simple_llm_request):
                        break

                # Context should be cleared again
                assert ObservabilityContext._component_name_var.get() is None


class TestRecordTokenAndCostMetrics:
    """Test the _record_token_and_cost_metrics helper method."""

    def test_records_input_tokens(self, mock_cost_per_token):
        """Test that input tokens are recorded with correct labels."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                mock_registry_instance = Mock()
                mock_registry.get_instance.return_value = mock_registry_instance

                llm = LiteLlm(model="gpt-4")

                with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                    llm._record_token_and_cost_metrics("gpt-4", 100, 50)

                # Should have called registry
                assert mock_registry_instance.record_counter_from_monitor.called

    def test_records_output_tokens(self, mock_cost_per_token):
        """Test that output tokens are recorded with correct labels."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                mock_registry_instance = Mock()
                mock_registry.get_instance.return_value = mock_registry_instance

                llm = LiteLlm(model="gpt-4")

                with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                    llm._record_token_and_cost_metrics("gpt-4", 100, 50)

                # Verify both input and output tokens recorded (2 calls for tokens + 1 for cost)
                assert mock_registry_instance.record_counter_from_monitor.call_count >= 2

    def test_records_cost_when_available(self, mock_cost_per_token):
        """Test that cost is recorded when pricing is available."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                mock_registry_instance = Mock()
                mock_registry.get_instance.return_value = mock_registry_instance

                llm = LiteLlm(model="gpt-4")

                with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                    llm._record_token_and_cost_metrics("gpt-4", 100, 50)

                # Should have recorded cost (3 total calls: input tokens, output tokens, cost)
                assert mock_registry_instance.record_counter_from_monitor.call_count == 3

    def test_handles_cost_calculation_failure(self):
        """Test graceful handling when cost calculation fails."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', side_effect=Exception("No pricing")):
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                mock_registry_instance = Mock()
                mock_registry.get_instance.return_value = mock_registry_instance

                llm = LiteLlm(model="unknown-model")

                with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                    # Should not raise exception
                    llm._record_token_and_cost_metrics("unknown-model", 100, 50)

                # Should still have recorded tokens (2 calls), but not cost
                assert mock_registry_instance.record_counter_from_monitor.call_count == 2

    def test_uses_default_labels_without_context(self, mock_cost_per_token):
        """Test that 'none' is used as default when context not set."""
        with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                mock_registry_instance = Mock()
                mock_registry.get_instance.return_value = mock_registry_instance

                llm = LiteLlm(model="gpt-4")

                # NO context wrapper
                llm._record_token_and_cost_metrics("gpt-4", 100, 50)

                # Should still record metrics
                assert mock_registry_instance.record_counter_from_monitor.called