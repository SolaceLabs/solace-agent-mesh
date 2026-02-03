"""Unit tests for the callbacks module helper functions."""

import pytest

from solace_agent_mesh.agent.adk.callbacks import _parse_tags_param


class TestParseTagsParam:
    """Tests for the _parse_tags_param helper function."""

    def test_none_input_returns_empty_list(self):
        """None input should return an empty list."""
        assert _parse_tags_param(None) == []

    def test_empty_string_returns_empty_list(self):
        """Empty string should return an empty list."""
        assert _parse_tags_param("") == []

    def test_single_tag(self):
        """Single tag should return a list with one item."""
        assert _parse_tags_param("__working") == ["__working"]

    def test_multiple_tags(self):
        """Multiple comma-separated tags should return a list."""
        result = _parse_tags_param("__working,__user_uploaded,custom")
        assert result == ["__working", "__user_uploaded", "custom"]

    def test_tags_with_whitespace_are_trimmed(self):
        """Tags with surrounding whitespace should be trimmed."""
        result = _parse_tags_param("  __working  ,  __user_uploaded  ")
        assert result == ["__working", "__user_uploaded"]

    def test_empty_tags_filtered_out(self):
        """Empty tags (just commas) should be filtered out."""
        assert _parse_tags_param(",,,") == []
        assert _parse_tags_param("  ,  ,  ") == []

    def test_mixed_empty_and_valid_tags(self):
        """Mixed empty and valid tags should only return valid ones."""
        result = _parse_tags_param("__working,,__user_uploaded,  ,custom")
        assert result == ["__working", "__user_uploaded", "custom"]

    def test_whitespace_only_string(self):
        """Whitespace-only string should return empty list."""
        assert _parse_tags_param("   ") == []
