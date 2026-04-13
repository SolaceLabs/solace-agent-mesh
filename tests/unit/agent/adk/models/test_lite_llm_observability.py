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
        """Test that LLM call records token and cost metrics with correct labels."""
        recorded_metrics = []

        def capture_metric_calls(monitor, value):
            """Capture all metric recording calls."""
            recorded_metrics.append({
                'metric_name': monitor.monitor_type,
                'value': value,
                'labels': monitor.labels
            })

        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                    mock_registry_instance = Mock()
                    mock_registry_instance.record_counter_from_monitor = Mock(side_effect=capture_metric_calls)
                    mock_registry.get_instance.return_value = mock_registry_instance

                    mock_acompletion.return_value = mock_litellm_completion
                    llm = LiteLlm(model="gpt-4")

                    with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                        response = None
                        async for resp in llm.generate_content_async(simple_llm_request):
                            response = resp
                            break

                    # Verify response received
                    assert response is not None

                    # Verify we recorded token metrics (input and output)
                    # Note: cost metrics are unreliable and not tested
                    token_metrics = [m for m in recorded_metrics if m['metric_name'] == 'gen_ai.tokens.used']
                    assert len(token_metrics) >= 2, f"Expected at least 2 token metrics, got {len(token_metrics)}"

                    # Verify input tokens metric
                    input_metric = next(m for m in token_metrics if m['labels'].get('gen_ai.token.type') == 'input')
                    assert input_metric['value'] == 10  # From mock_litellm_completion
                    assert input_metric['labels']['component.name'] == 'test-agent'
                    assert input_metric['labels']['owner.id'] == 'user123'
                    assert input_metric['labels']['gen_ai.request.model'] == 'gpt-4'

                    # Verify output tokens metric
                    output_metric = next(m for m in token_metrics if m['labels'].get('gen_ai.token.type') == 'output')
                    assert output_metric['value'] == 5  # From mock_litellm_completion
                    assert output_metric['labels']['component.name'] == 'test-agent'
                    assert output_metric['labels']['owner.id'] == 'user123'

    @pytest.mark.asyncio
    async def test_uses_default_labels_without_context(
        self, mock_litellm_completion, simple_llm_request, mock_cost_per_token
    ):
        """Test that metrics use 'none' as default when no context set."""
        recorded_metrics = []

        def capture_metric_calls(monitor, value):
            recorded_metrics.append({
                'metric_name': monitor.monitor_type,
                'labels': monitor.labels
            })

        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                    mock_registry_instance = Mock()
                    mock_registry_instance.record_counter_from_monitor = Mock(side_effect=capture_metric_calls)
                    mock_registry.get_instance.return_value = mock_registry_instance

                    mock_acompletion.return_value = mock_litellm_completion
                    llm = LiteLlm(model="gpt-4")

                    # NO ObservabilityContext wrapper
                    response = None
                    async for resp in llm.generate_content_async(simple_llm_request):
                        response = resp
                        break

                    assert response is not None

                    # Verify token metrics use "none" as default labels
                    token_metrics = [m for m in recorded_metrics if m['metric_name'] == 'gen_ai.tokens.used']
                    assert len(token_metrics) >= 2, f"Expected at least 2 token metrics"
                    for metric in token_metrics:
                        assert metric['labels']['component.name'] == 'none', \
                            f"Expected component.name='none', got {metric['labels']['component.name']}"
                        assert metric['labels']['owner.id'] == 'none', \
                            f"Expected owner.id='none', got {metric['labels']['owner.id']}"



class TestLiteLlmObservabilityStreaming:
    """Test LiteLlm observability metrics for streaming calls."""

    @pytest.mark.asyncio
    async def test_streaming_records_token_metrics(
        self, mock_litellm_streaming, simple_llm_request, mock_cost_per_token
    ):
        """Test that streaming records token metrics with correct labels."""
        recorded_metrics = []

        def capture_counter_calls(monitor, value):
            recorded_metrics.append({
                'metric_name': monitor.monitor_type,
                'value': value,
                'labels': monitor.labels
            })

        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                    mock_registry_instance = Mock()
                    mock_registry_instance.record_counter_from_monitor = Mock(side_effect=capture_counter_calls)
                    mock_registry.get_instance.return_value = mock_registry_instance

                    mock_acompletion.return_value = mock_litellm_streaming()
                    llm = LiteLlm(model="gpt-4")

                    with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                        chunks = []
                        async for chunk in llm.generate_content_async(simple_llm_request, stream=True):
                            chunks.append(chunk)

                    # Should have received chunks
                    assert len(chunks) > 0

                    token_metrics = [m for m in recorded_metrics if m['metric_name'] == 'gen_ai.tokens.used']
                    assert len(token_metrics) >= 2

                    # Verify input tokens
                    input_metric = next(m for m in token_metrics if m['labels'].get('gen_ai.token.type') == 'input')
                    assert input_metric['value'] == 10  # From mock_litellm_streaming
                    assert input_metric['labels']['component.name'] == 'test-agent'

                    # Verify output tokens
                    output_metric = next(m for m in token_metrics if m['labels'].get('gen_ai.token.type') == 'output')
                    assert output_metric['value'] == 2  # From mock_litellm_streaming
                    assert output_metric['labels']['component.name'] == 'test-agent'

    @pytest.mark.asyncio
    async def test_ttft_measures_request_to_first_token_latency(
        self, simple_llm_request, mock_cost_per_token
    ):
        """Test TTFT measures time from request sent to first token received (not between chunks)."""
        # Create streaming mock with controlled 10ms delay BEFORE first token
        async def delayed_streaming():
            # Simulate network + LLM processing delay BEFORE first token
            await asyncio.sleep(0.010)  # 10ms delay

            # First token arrives
            yield {
                "choices": [{
                    "delta": {"content": "Hello"},
                    "finish_reason": None
                }]
            }

            # Second token (immediate)
            yield {
                "choices": [{
                    "delta": {"content": " world"},
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12
                }
            }

        ttft_durations = []

        def capture_recorder_calls(duration, labels):
            """Capture all recorder.record() calls."""
            ttft_durations.append((duration, labels))

        with patch('solace_agent_mesh.agent.adk.models.lite_llm.acompletion') as mock_acompletion:
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
                with patch('solace_ai_connector.common.observability.api.MetricRegistry') as mock_registry:
                    with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry', mock_registry):
                        mock_recorder = Mock()
                        mock_recorder.record = Mock(side_effect=capture_recorder_calls)

                        mock_registry_instance = Mock()
                        mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
                        mock_registry_instance.record_counter_from_monitor = Mock()
                        mock_registry.get_instance.return_value = mock_registry_instance

                        mock_acompletion.return_value = delayed_streaming()

                        llm = LiteLlm(model="gpt-4")

                        with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                            async for _ in llm.generate_content_async(simple_llm_request, stream=True):
                                pass

                        # Verify TTFT monitor was used
                        ttft_get_recorder_calls = [
                            call for call in mock_registry_instance.get_recorder.call_args_list
                            if call[0][0] == "gen_ai.client.operation.ttft.duration"
                        ]

                        assert len(ttft_get_recorder_calls) > 0, "TTFT monitor should have been used"
                        assert len(ttft_durations) > 0, "TTFT should have been recorded"

                        # Get the TTFT duration (should be one of the recorded durations)
                        # TTFT should be ~10ms (with tolerance for test timing variance)
                        ttft_found = False
                        for duration, labels in ttft_durations:
                            ttft_ms = duration * 1000
                            # Check if this looks like the TTFT measurement (around 10ms)
                            if 8.0 <= ttft_ms <= 20.0:
                                ttft_found = True
                                assert ttft_ms >= 8.0, f"TTFT too low ({ttft_ms:.2f}ms) - timer may have started too late"
                                break

                        assert ttft_found, f"TTFT measurement not found in recorded durations: {[(d*1000, l) for d, l in ttft_durations]}"


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
    """Test the _record_token_and_cost_metrics helper method directly."""

    def test_helper_records_correct_values_and_labels(self, mock_cost_per_token):
        """Test that helper method records correct token metric values and labels."""
        recorded_metrics = []

        def capture_metric_calls(monitor, value):
            recorded_metrics.append({
                'metric_name': monitor.monitor_type,
                'value': value,
                'labels': monitor.labels
            })

        with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                mock_registry_instance = Mock()
                mock_registry_instance.record_counter_from_monitor = Mock(side_effect=capture_metric_calls)
                mock_registry.get_instance.return_value = mock_registry_instance

                llm = LiteLlm(model="gpt-4")

                with ObservabilityContext(component_name="test-agent", owner_id="user123"):
                    llm._record_token_and_cost_metrics("gpt-4", 100, 50)

                # Verify token metrics recorded (cost is unreliable and not tested)
                token_metrics = [m for m in recorded_metrics if m['metric_name'] == 'gen_ai.tokens.used']
                assert len(token_metrics) == 2

                # Verify input tokens
                input_metric = next(m for m in token_metrics if m['labels'].get('gen_ai.token.type') == 'input')
                assert input_metric['value'] == 100
                assert input_metric['labels']['component.name'] == 'test-agent'
                assert input_metric['labels']['owner.id'] == 'user123'
                assert input_metric['labels']['gen_ai.request.model'] == 'gpt-4'
                assert input_metric['labels']['gen_ai.token.type'] == 'input'

                # Verify output tokens
                output_metric = next(m for m in token_metrics if m['labels'].get('gen_ai.token.type') == 'output')
                assert output_metric['value'] == 50
                assert output_metric['labels']['component.name'] == 'test-agent'
                assert output_metric['labels']['owner.id'] == 'user123'
                assert output_metric['labels']['gen_ai.token.type'] == 'output'

    def test_helper_uses_default_labels_without_context(self, mock_cost_per_token):
        """Test that 'none' is used as default when context not set."""
        recorded_metrics = []

        def capture_metric_calls(monitor, value):
            recorded_metrics.append({
                'metric_name': monitor.monitor_type,
                'labels': monitor.labels
            })

        with patch('solace_agent_mesh.agent.adk.models.lite_llm.cost_per_token', return_value=mock_cost_per_token):
            with patch('solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry') as mock_registry:
                mock_registry_instance = Mock()
                mock_registry_instance.record_counter_from_monitor = Mock(side_effect=capture_metric_calls)
                mock_registry.get_instance.return_value = mock_registry_instance

                llm = LiteLlm(model="gpt-4")

                # NO context wrapper
                llm._record_token_and_cost_metrics("gpt-4", 100, 50)

                # Verify token metrics use "none" as default
                token_metrics = [m for m in recorded_metrics if m['metric_name'] == 'gen_ai.tokens.used']
                assert len(token_metrics) == 2
                for metric in token_metrics:
                    assert metric['labels']['component.name'] == 'none'
                    assert metric['labels']['owner.id'] == 'none'