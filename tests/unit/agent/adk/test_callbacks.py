"""Unit tests for the callbacks module helper functions."""

import pytest

from solace_agent_mesh.agent.adk.callbacks import (
    _parse_tags_param,
    _sanitize_bytes_in_dict_inplace,
)


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


class TestSanitizeBytesInDictInplace:
    """Tests for _sanitize_bytes_in_dict_inplace()."""

    def test_bytes_in_flat_dict(self):
        obj = {"key": b"hello"}
        _sanitize_bytes_in_dict_inplace(obj)
        assert obj == {"key": "<binary data: 5 bytes>"}

    def test_bytearray_in_flat_dict(self):
        obj = {"key": bytearray(b"abc")}
        _sanitize_bytes_in_dict_inplace(obj)
        assert obj == {"key": "<binary data: 3 bytes>"}

    def test_nested_dict_with_bytes(self):
        obj = {"outer": {"inner": b"\x00\x01\x02"}}
        _sanitize_bytes_in_dict_inplace(obj)
        assert obj == {"outer": {"inner": "<binary data: 3 bytes>"}}

    def test_bytes_in_list(self):
        obj = [b"data", "text"]
        _sanitize_bytes_in_dict_inplace(obj)
        assert obj == ["<binary data: 4 bytes>", "text"]

    def test_nested_list_in_dict(self):
        obj = {"items": [{"data": b"img"}, "ok"]}
        _sanitize_bytes_in_dict_inplace(obj)
        assert obj == {"items": [{"data": "<binary data: 3 bytes>"}, "ok"]}

    def test_clean_data_unchanged(self):
        obj = {"key": "value", "num": 42, "nested": {"a": [1, 2]}}
        original = {"key": "value", "num": 42, "nested": {"a": [1, 2]}}
        _sanitize_bytes_in_dict_inplace(obj)
        assert obj == original

    def test_empty_dict(self):
        obj = {}
        _sanitize_bytes_in_dict_inplace(obj)
        assert obj == {}

    def test_empty_list(self):
        obj = []
        _sanitize_bytes_in_dict_inplace(obj)
        assert obj == []

    def test_empty_bytes(self):
        obj = {"data": b""}
        _sanitize_bytes_in_dict_inplace(obj)
        assert obj == {"data": "<binary data: 0 bytes>"}
