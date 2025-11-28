#!/usr/bin/env python3
"""
Unit tests for UsageTrackingService.

Tests cover:
1. Token usage recording with all token types (prompt, completion, cached)
2. Cost calculation integration
3. Transaction creation
4. Monthly usage aggregation
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime


class TestUsageTrackingService:
    """Tests for UsageTrackingService."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.add = MagicMock()
        session.commit = MagicMock()
        session.query = MagicMock()
        return session

    @pytest.fixture
    def mock_cost_calculator(self):
        """Create a mock cost calculator."""
        calculator = MagicMock()
        calculator.calculate_cost.return_value = {
            "prompt_cost": 100,
            "completion_cost": 200,
            "cached_cost": 50,
            "total_cost": 350,
            "prompt_rate": 0.001,
            "completion_rate": 0.002,
            "cached_rate": 0.0005,
            "model": "gpt-4",
        }
        return calculator

    @pytest.fixture
    def usage_service(self, mock_db_session, mock_cost_calculator):
        """Create a UsageTrackingService instance."""
        from solace_agent_mesh.gateway.http_sse.services.usage_tracking_service import (
            UsageTrackingService,
        )
        return UsageTrackingService(
            db_session=mock_db_session,
            cost_calculator=mock_cost_calculator,
        )

    def test_record_token_usage_basic(self, usage_service, mock_db_session, mock_cost_calculator):
        """Test basic token usage recording."""
        result = usage_service.record_token_usage(
            user_id="user123",
            task_id="task456",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
        )

        # Verify cost calculator was called
        mock_cost_calculator.calculate_cost.assert_called_once_with(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            cached_input_tokens=0,
        )

        # Verify transactions were added to session
        assert mock_db_session.add.call_count >= 2  # At least prompt and completion

    def test_record_token_usage_with_cached_tokens(
        self, usage_service, mock_db_session, mock_cost_calculator
    ):
        """Test token usage recording with cached tokens."""
        result = usage_service.record_token_usage(
            user_id="user123",
            task_id="task456",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            cached_input_tokens=30,
        )

        # Verify cost calculator was called with cached tokens
        mock_cost_calculator.calculate_cost.assert_called_once_with(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            cached_input_tokens=30,
        )

        # Verify cached transaction was created (3 transactions: prompt, completion, cached)
        assert mock_db_session.add.call_count >= 3

    def test_record_token_usage_with_tool_source(
        self, usage_service, mock_db_session, mock_cost_calculator
    ):
        """Test token usage recording from a tool."""
        result = usage_service.record_token_usage(
            user_id="user123",
            task_id="task456",
            model="gpt-4",
            prompt_tokens=50,
            completion_tokens=25,
            source="tool",
            tool_name="example_tool",
        )

        # Verify cost calculator was called
        mock_cost_calculator.calculate_cost.assert_called_once()

    def test_record_token_usage_without_task_id(
        self, usage_service, mock_db_session, mock_cost_calculator
    ):
        """Test token usage recording without a task ID."""
        result = usage_service.record_token_usage(
            user_id="user123",
            task_id=None,
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
        )

        # Should still work without task_id
        mock_cost_calculator.calculate_cost.assert_called_once()

    def test_record_token_usage_zero_tokens(
        self, usage_service, mock_db_session, mock_cost_calculator
    ):
        """Test token usage recording with zero tokens."""
        result = usage_service.record_token_usage(
            user_id="user123",
            task_id="task456",
            model="gpt-4",
            prompt_tokens=0,
            completion_tokens=0,
            cached_input_tokens=0,
        )

        # Cost calculator should still be called
        mock_cost_calculator.calculate_cost.assert_called_once()


class TestLiteLLMCostCalculator:
    """Tests for LiteLLMCostCalculator."""

    @pytest.fixture
    def cost_calculator(self):
        """Create a LiteLLMCostCalculator instance."""
        from solace_agent_mesh.gateway.http_sse.services.litellm_cost_calculator import (
            LiteLLMCostCalculator,
        )
        return LiteLLMCostCalculator()

    def test_calculate_cost_basic(self, cost_calculator):
        """Test basic cost calculation."""
        with patch(
            "solace_agent_mesh.gateway.http_sse.services.litellm_cost_calculator.litellm_completion_cost"
        ) as mock_cost:
            mock_cost.return_value = 0.001  # $0.001

            result = cost_calculator.calculate_cost(
                model="gpt-4",
                prompt_tokens=100,
                completion_tokens=50,
            )

            assert "prompt_cost" in result
            assert "completion_cost" in result
            assert "total_cost" in result
            assert "model" in result
            assert result["model"] == "gpt-4"

    def test_calculate_cost_with_cached_tokens(self, cost_calculator):
        """Test cost calculation with cached tokens."""
        with patch(
            "solace_agent_mesh.gateway.http_sse.services.litellm_cost_calculator.litellm_completion_cost"
        ) as mock_cost:
            mock_cost.return_value = 0.0005  # $0.0005

            result = cost_calculator.calculate_cost(
                model="gpt-4",
                prompt_tokens=100,
                completion_tokens=50,
                cached_input_tokens=30,
            )

            assert "cached_cost" in result
            assert "cached_rate" in result

    def test_calculate_cost_handles_unknown_model(self, cost_calculator):
        """Test cost calculation with unknown model falls back gracefully."""
        with patch(
            "solace_agent_mesh.gateway.http_sse.services.litellm_cost_calculator.litellm_completion_cost"
        ) as mock_cost:
            # Simulate LiteLLM raising an exception for unknown model
            mock_cost.side_effect = Exception("Unknown model")

            result = cost_calculator.calculate_cost(
                model="unknown-model-xyz",
                prompt_tokens=100,
                completion_tokens=50,
            )

            # Should return fallback values
            assert "total_cost" in result
            assert result["model"] == "unknown-model-xyz"

    def test_calculate_cost_zero_tokens(self, cost_calculator):
        """Test cost calculation with zero tokens."""
        with patch(
            "solace_agent_mesh.gateway.http_sse.services.litellm_cost_calculator.litellm_completion_cost"
        ) as mock_cost:
            mock_cost.return_value = 0.0

            result = cost_calculator.calculate_cost(
                model="gpt-4",
                prompt_tokens=0,
                completion_tokens=0,
            )

            assert result["total_cost"] == 0


class TestTaskExecutionContextTokenTracking:
    """Tests for token tracking in TaskExecutionContext."""

    @pytest.fixture
    def task_context(self):
        """Create a TaskExecutionContext instance."""
        from solace_agent_mesh.agent.sac.task_execution_context import (
            TaskExecutionContext,
        )
        # TaskExecutionContext requires task_id and a2a_context dict
        a2a_context = {
            "user_id": "test-user",
            "session_id": "test-session",
            "logical_task_id": "test-task-123",
        }
        return TaskExecutionContext(
            task_id="test-task-123",
            a2a_context=a2a_context,
        )

    def test_record_token_usage_updates_totals(self, task_context):
        """Test that recording token usage updates total counters."""
        task_context.record_token_usage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
        )

        assert task_context.total_input_tokens == 100
        assert task_context.total_output_tokens == 50
        assert task_context.total_cached_input_tokens == 0

    def test_record_token_usage_with_cached_tokens(self, task_context):
        """Test that cached tokens are tracked correctly."""
        task_context.record_token_usage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
            cached_input_tokens=30,
        )

        assert task_context.total_input_tokens == 100
        assert task_context.total_output_tokens == 50
        assert task_context.total_cached_input_tokens == 30

    def test_record_token_usage_accumulates(self, task_context):
        """Test that multiple calls accumulate token counts."""
        task_context.record_token_usage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
        )
        task_context.record_token_usage(
            input_tokens=200,
            output_tokens=100,
            model="gpt-4",
            cached_input_tokens=50,
        )

        assert task_context.total_input_tokens == 300
        assert task_context.total_output_tokens == 150
        assert task_context.total_cached_input_tokens == 50

    def test_record_token_usage_tracks_by_model(self, task_context):
        """Test that token usage is tracked per model."""
        task_context.record_token_usage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
        )
        task_context.record_token_usage(
            input_tokens=200,
            output_tokens=100,
            model="gpt-3.5-turbo",
        )

        assert "gpt-4" in task_context.token_usage_by_model
        assert "gpt-3.5-turbo" in task_context.token_usage_by_model
        assert task_context.token_usage_by_model["gpt-4"]["input_tokens"] == 100
        assert task_context.token_usage_by_model["gpt-3.5-turbo"]["input_tokens"] == 200

    def test_record_token_usage_tracks_by_source(self, task_context):
        """Test that token usage is tracked per source."""
        task_context.record_token_usage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
            source="agent",
        )
        task_context.record_token_usage(
            input_tokens=50,
            output_tokens=25,
            model="gpt-4",
            source="tool",
            tool_name="example_tool",
        )

        assert "agent" in task_context.token_usage_by_source
        assert "tool:example_tool" in task_context.token_usage_by_source
        assert task_context.token_usage_by_source["agent"]["input_tokens"] == 100
        assert task_context.token_usage_by_source["tool:example_tool"]["input_tokens"] == 50

    def test_record_token_usage_tracks_cached_by_model(self, task_context):
        """Test that cached tokens are tracked per model."""
        task_context.record_token_usage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
            cached_input_tokens=30,
        )

        assert task_context.token_usage_by_model["gpt-4"]["cached_input_tokens"] == 30

    def test_get_token_usage_summary(self, task_context):
        """Test getting token usage summary."""
        task_context.record_token_usage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
            cached_input_tokens=30,
        )

        summary = task_context.get_token_usage_summary()

        assert summary["total_input_tokens"] == 100
        assert summary["total_output_tokens"] == 50
        assert summary["total_cached_input_tokens"] == 30
        assert summary["total_tokens"] == 150  # input + output

    def test_record_token_usage_with_usage_service(self, task_context):
        """Test that usage service is called when set."""
        mock_usage_service = MagicMock()
        task_context.set_usage_service(mock_usage_service)

        task_context.record_token_usage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
            cached_input_tokens=30,
        )

        # Verify usage service was called
        mock_usage_service.record_token_usage.assert_called_once()
        call_args = mock_usage_service.record_token_usage.call_args
        assert call_args.kwargs["prompt_tokens"] == 100
        assert call_args.kwargs["completion_tokens"] == 50
        assert call_args.kwargs["cached_input_tokens"] == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])