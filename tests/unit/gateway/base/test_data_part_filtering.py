"""Unit tests for _should_include_data_part_in_final_output data part filtering."""

from unittest.mock import patch

from a2a.types import DataPart

from solace_agent_mesh.gateway.base.component import BaseGatewayComponent


def _make_data_part(data_type, metadata=None):
    """Create a DataPart with the given type and optional metadata."""
    data = {"type": data_type} if data_type else {}
    return DataPart(data=data, metadata=metadata)


def _make_component(supports_inline=True):
    """Create a BaseGatewayComponent instance with mocked init."""
    with patch.object(BaseGatewayComponent, "__init__", lambda self, *a, **kw: None):
        comp = BaseGatewayComponent()
        comp.supports_inline_artifact_resolution = supports_inline
        return comp


class TestShouldIncludeDataPartInFinalOutput:
    """Tests for the _should_include_data_part_in_final_output method."""

    def test_thinking_content_passes_filter(self):
        """thinking_content data parts should be included in output."""
        comp = _make_component()
        part = _make_data_part("thinking_content")
        assert comp._should_include_data_part_in_final_output(part) is True

    def test_agent_progress_update_passes_filter(self):
        """agent_progress_update data parts should be included."""
        comp = _make_component()
        part = _make_data_part("agent_progress_update")
        assert comp._should_include_data_part_in_final_output(part) is True

    def test_tool_related_types_filtered_out(self):
        """Tool-related data types should be filtered out."""
        comp = _make_component()
        for tool_type in ["tool_call", "tool_result", "tool_error", "tool_execution"]:
            part = _make_data_part(tool_type)
            assert comp._should_include_data_part_in_final_output(part) is False, (
                f"{tool_type} should be filtered out"
            )

    def test_non_datapart_passes_through(self):
        """Non-DataPart objects should pass through."""
        comp = _make_component()
        assert comp._should_include_data_part_in_final_output("not a data part") is True

    def test_tool_metadata_filtered_out(self):
        """Parts with tool_name in metadata should be filtered out."""
        comp = _make_component()
        part = _make_data_part("some_type", metadata={"tool_name": "search"})
        assert comp._should_include_data_part_in_final_output(part) is False
