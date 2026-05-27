"""
Regression tests for _generate_workflow_instructions — ensures the prompt injected
into workflow node agents does not reference non-existent or wrong tool names,
which would cause LLM hallucinations (issue #1261).
"""

from unittest.mock import MagicMock

from src.solace_agent_mesh.agent.sac.structured_invocation.handler import (
    StructuredInvocationHandler,
)
from src.solace_agent_mesh.common.data_parts import StructuredInvocationRequest


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"doubled_value": {"type": "number"}},
    "required": ["doubled_value"],
}


def _make_handler() -> StructuredInvocationHandler:
    mock_component = MagicMock()
    mock_component.get_config.return_value = None
    return StructuredInvocationHandler(mock_component)


def _make_request(**kwargs) -> StructuredInvocationRequest:
    defaults = {"workflow_name": "TestWorkflow", "node_id": "test_node"}
    return StructuredInvocationRequest(**{**defaults, **kwargs})


class TestWorkflowInstructionsToolNames:
    """Issue #1261: instructions must not reference non-existent tool names."""

    def test_output_schema_branch_does_not_say_save_artifact_tool(self):
        # "save_artifact tool" was the hallucination trigger — the string
        # is fine as part of the fenced block syntax, but must not appear
        # as a tool name reference.
        instructions = _make_handler()._generate_workflow_instructions(
            _make_request(), OUTPUT_SCHEMA
        )
        assert "save_artifact tool" not in instructions

    def test_no_output_schema_branch_does_not_say_save_artifact_tool(self):
        instructions = _make_handler()._generate_workflow_instructions(
            _make_request(), None
        )
        assert "save_artifact tool" not in instructions

    def test_output_schema_branch_mentions_inline_fenced_block_syntax(self):
        # The correct mechanism for creating artifacts is the «««save_artifact:...»»»
        # inline fenced block, not a tool call.
        instructions = _make_handler()._generate_workflow_instructions(
            _make_request(), OUTPUT_SCHEMA
        )
        assert "save_artifact:" in instructions

    def test_suggested_filename_branch_does_not_say_save_artifact_tool(self):
        instructions = _make_handler()._generate_workflow_instructions(
            _make_request(suggested_output_filename="output.json"), OUTPUT_SCHEMA
        )
        assert "save_artifact tool" not in instructions

    def test_output_schema_is_serialized_into_instructions(self):
        instructions = _make_handler()._generate_workflow_instructions(
            _make_request(), OUTPUT_SCHEMA
        )
        assert "doubled_value" in instructions

    def test_result_embed_syntax_is_present(self):
        instructions = _make_handler()._generate_workflow_instructions(
            _make_request(), OUTPUT_SCHEMA
        )
        assert "result:artifact=" in instructions

    def test_not_a_tool_call_is_explicit(self):
        # The instruction must clarify the fenced block is NOT a tool call,
        # preventing the LLM from inventing a function name.
        instructions = _make_handler()._generate_workflow_instructions(
            _make_request(), OUTPUT_SCHEMA
        )
        assert "NOT a tool call" in instructions
