"""
Unit tests for workflow agent caller input resolution.

Tests the _resolve_node_input method which handles:
- Explicit input mapping with template resolution
- Implicit input inference for nodes without explicit input
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
from solace_agent_mesh.workflow.agent_caller import AgentCaller
from solace_agent_mesh.workflow.app import AgentNode, SwitchNode, SwitchCase
from solace_agent_mesh.workflow.workflow_execution_context import (
    WorkflowExecutionContext,
    WorkflowExecutionState,
)


def create_mock_host(default_node_timeout_seconds: int = 60):
    """Create a mock host component with required attributes."""
    host = Mock()
    host.log_identifier = "[Test]"
    host.dag_executor = Mock()
    host.dag_executor.nodes = {}
    host.dag_executor.resolve_value = Mock(side_effect=lambda v, s: v)
    config = {"default_node_timeout_seconds": default_node_timeout_seconds}
    host.get_config = Mock(side_effect=lambda key, default=None: config.get(key, default))
    return host


def create_workflow_state(
    node_outputs: dict = None,
    completed_nodes: dict = None,
) -> WorkflowExecutionState:
    """Create a workflow state with given outputs."""
    state = WorkflowExecutionState(
        execution_id="test-exec-001",
        workflow_name="TestWorkflow",
        start_time=datetime.now(),
    )
    if node_outputs:
        state.node_outputs = node_outputs
    if completed_nodes:
        state.completed_nodes = completed_nodes
    return state


class TestResolveNodeInputExplicit:
    """Tests for explicit input mapping resolution."""

    @pytest.mark.asyncio
    async def test_explicit_input_resolved_via_dag_executor(self):
        """When node has explicit input, each value is resolved via DAGExecutor."""
        host = create_mock_host()
        # Mock resolve_value to transform templates
        host.dag_executor.resolve_value = Mock(
            side_effect=lambda v, s: f"resolved_{v}" if isinstance(v, str) else v
        )

        caller = AgentCaller(host)

        node = AgentNode(
            id="test_node",
            type="agent",
            agent_name="TestAgent",
            input={"field1": "{{workflow.input.x}}", "field2": "literal"},
        )

        state = create_workflow_state(
            node_outputs={"workflow_input": {"output": {"x": 42}}}
        )

        result = await caller._resolve_node_input(node, state)

        # Each value should be passed through resolve_value
        assert host.dag_executor.resolve_value.call_count == 2
        assert result == {
            "field1": "resolved_{{workflow.input.x}}",
            "field2": "resolved_literal",
        }

    @pytest.mark.asyncio
    async def test_explicit_input_empty_dict_returns_empty(self):
        """When node has empty input dict, return empty dict."""
        host = create_mock_host()
        caller = AgentCaller(host)

        node = AgentNode(
            id="test_node",
            type="agent",
            agent_name="TestAgent",
            input={},
        )

        state = create_workflow_state()
        result = await caller._resolve_node_input(node, state)

        assert result == {}


class TestResolveNodeInputImplicitInitialNode:
    """Tests for implicit input inference - initial nodes (no dependencies)."""

    @pytest.mark.asyncio
    async def test_initial_node_uses_workflow_input(self):
        """Node with no dependencies uses workflow input."""
        host = create_mock_host()
        caller = AgentCaller(host)

        node = AgentNode(
            id="first_node",
            type="agent",
            agent_name="TestAgent",
            # No input mapping, no depends_on
        )

        workflow_input_data = {"customer": "Alice", "amount": 100}
        state = create_workflow_state(
            node_outputs={"workflow_input": {"output": workflow_input_data}}
        )

        result = await caller._resolve_node_input(node, state)

        assert result == workflow_input_data

    @pytest.mark.asyncio
    async def test_initial_node_raises_when_workflow_input_missing(self):
        """Node with no dependencies raises if workflow_input not initialized."""
        host = create_mock_host()
        caller = AgentCaller(host)

        node = AgentNode(
            id="first_node",
            type="agent",
            agent_name="TestAgent",
        )

        # No workflow_input in state
        state = create_workflow_state(node_outputs={})

        with pytest.raises(ValueError) as exc_info:
            await caller._resolve_node_input(node, state)

        assert "Workflow input has not been initialized" in str(exc_info.value)


class TestResolveNodeInputImplicitSingleDependency:
    """Tests for implicit input inference - single dependency."""

    @pytest.mark.asyncio
    async def test_single_dependency_uses_dependency_output(self):
        """Node with one non-switch dependency uses that dependency's output."""
        host = create_mock_host()
        # Register the dependency as a regular agent node
        host.dag_executor.nodes = {
            "step_1": AgentNode(id="step_1", type="agent", agent_name="Agent1")
        }
        caller = AgentCaller(host)

        node = AgentNode(
            id="step_2",
            type="agent",
            agent_name="TestAgent",
            depends_on=["step_1"],
            # No explicit input
        )

        step1_output = {"processed": True, "data": "result"}
        state = create_workflow_state(
            node_outputs={
                "workflow_input": {"output": {"original": "input"}},
                "step_1": {"output": step1_output},
            }
        )

        result = await caller._resolve_node_input(node, state)

        assert result == step1_output

    @pytest.mark.asyncio
    async def test_single_dependency_raises_when_dependency_not_complete(self):
        """Node raises if its single dependency hasn't completed."""
        host = create_mock_host()
        host.dag_executor.nodes = {
            "step_1": AgentNode(id="step_1", type="agent", agent_name="Agent1")
        }
        caller = AgentCaller(host)

        node = AgentNode(
            id="step_2",
            type="agent",
            agent_name="TestAgent",
            depends_on=["step_1"],
        )

        # step_1 not in node_outputs (hasn't completed)
        state = create_workflow_state(
            node_outputs={"workflow_input": {"output": {}}}
        )

        with pytest.raises(ValueError) as exc_info:
            await caller._resolve_node_input(node, state)

        assert "Dependency 'step_1' has not completed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_switch_dependency_uses_workflow_input(self):
        """Node depending on switch uses workflow input, not switch output."""
        host = create_mock_host()
        # Register the dependency as a switch node
        host.dag_executor.nodes = {
            "branch": SwitchNode(
                id="branch",
                type="switch",
                cases=[
                    SwitchCase(condition="{{step_1.output.status}} == 'success'", node="success_path"),
                ],
                default="failure_path",
            )
        }
        caller = AgentCaller(host)

        node = AgentNode(
            id="success_path",
            type="agent",
            agent_name="TestAgent",
            depends_on=["branch"],
            # No explicit input
        )

        workflow_input_data = {"original": "workflow input"}
        state = create_workflow_state(
            node_outputs={
                "workflow_input": {"output": workflow_input_data},
                "branch": {"output": {"selected_branch": "success_path"}},
            }
        )

        result = await caller._resolve_node_input(node, state)

        # Should use workflow input, not branch output
        assert result == workflow_input_data

    @pytest.mark.asyncio
    async def test_switch_dependency_raises_when_workflow_input_missing(self):
        """Node depending on switch raises if workflow_input missing."""
        host = create_mock_host()
        host.dag_executor.nodes = {
            "branch": SwitchNode(
                id="branch",
                type="switch",
                cases=[
                    SwitchCase(condition="true", node="next"),
                ],
            )
        }
        caller = AgentCaller(host)

        node = AgentNode(
            id="next",
            type="agent",
            agent_name="TestAgent",
            depends_on=["branch"],
        )

        # No workflow_input
        state = create_workflow_state(
            node_outputs={"branch": {"output": {}}}
        )

        with pytest.raises(ValueError) as exc_info:
            await caller._resolve_node_input(node, state)

        assert "Workflow input has not been initialized" in str(exc_info.value)


class TestResolveNodeInputImplicitMultipleDependencies:
    """Tests for implicit input inference - multiple dependencies (error case)."""

    @pytest.mark.asyncio
    async def test_multiple_dependencies_without_explicit_input_raises(self):
        """Node with multiple dependencies but no explicit input raises error."""
        host = create_mock_host()
        host.dag_executor.nodes = {
            "step_1": AgentNode(id="step_1", type="agent", agent_name="Agent1"),
            "step_2": AgentNode(id="step_2", type="agent", agent_name="Agent2"),
        }
        caller = AgentCaller(host)

        node = AgentNode(
            id="merge_node",
            type="agent",
            agent_name="MergeAgent",
            depends_on=["step_1", "step_2"],
            # No explicit input - ambiguous which dependency to use
        )

        state = create_workflow_state(
            node_outputs={
                "workflow_input": {"output": {}},
                "step_1": {"output": {"data": "from_1"}},
                "step_2": {"output": {"data": "from_2"}},
            }
        )

        with pytest.raises(ValueError) as exc_info:
            await caller._resolve_node_input(node, state)

        error_msg = str(exc_info.value)
        assert "multiple dependencies" in error_msg.lower()
        assert "step_1" in error_msg
        assert "step_2" in error_msg
        assert "explicit 'input' mapping" in error_msg


class TestResolveNodeTimeout:
    """Tests for per-node timeout resolution.

    Regression coverage for DATAGO-134263 — the per-node ``timeout`` field
    was previously declared on AgentNode/WorkflowInvokeNode but ignored at
    runtime; the workflow-level ``default_node_timeout_seconds`` was always
    used. These tests pin the new behaviour: per-node timeout wins, with
    fallback to the workflow default.
    """

    def test_node_timeout_overrides_default(self):
        host = create_mock_host(default_node_timeout_seconds=60)
        caller = AgentCaller(host)
        assert caller._resolve_node_timeout("5m") == 300.0
        assert caller._resolve_node_timeout("30s") == 30.0
        assert caller._resolve_node_timeout("1h") == 3600.0

    def test_missing_node_timeout_uses_default(self):
        host = create_mock_host(default_node_timeout_seconds=60)
        caller = AgentCaller(host)
        assert caller._resolve_node_timeout(None) == 60.0
        assert caller._resolve_node_timeout("") == 60.0

    def test_invalid_node_timeout_falls_back_to_default(self):
        """Invalid duration strings should not crash the call — fall back."""
        host = create_mock_host(default_node_timeout_seconds=60)
        caller = AgentCaller(host)
        assert caller._resolve_node_timeout("not-a-duration") == 60.0


class TestPublishAgentRequestTimeout:
    """Tests that the resolved timeout is propagated to cache + context."""

    @pytest.mark.asyncio
    async def test_publish_uses_passed_timeout_for_cache_expiry(self):
        from a2a.types import Message, Role, TextPart, Part

        host = create_mock_host(default_node_timeout_seconds=60)
        host.namespace = "test"
        host.workflow_name = "TestWorkflow"
        host.cache_service = Mock()
        host.publish_a2a_message = Mock()
        caller = AgentCaller(host)

        ctx = WorkflowExecutionContext(
            workflow_task_id="wf-task-1",
            a2a_context={"user_id": "u1", "session_id": "s1"},
        )

        message = Message(
            messageId="m1",
            role=Role.user,
            parts=[Part(root=TextPart(text="hi"))],
        )

        await caller._publish_agent_request(
            agent_name="TargetAgent",
            message=message,
            sub_task_id="sub-1",
            workflow_context=ctx,
            timeout_seconds=300.0,
        )

        # Cache expiry must use the passed timeout, not the default.
        _, kwargs = host.cache_service.add_data.call_args
        assert kwargs["expiry"] == 300.0
        assert kwargs["key"] == "sub-1"

        # Context must remember the resolved timeout for later error reporting.
        assert ctx.get_sub_task_timeout("sub-1") == 300.0
