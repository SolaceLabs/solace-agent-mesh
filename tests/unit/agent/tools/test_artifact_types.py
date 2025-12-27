"""
Unit tests for artifact_types.py

Tests for the type detection functions that identify ArtifactContent
type annotations for automatic artifact pre-loading.
"""

import pytest
from typing import List, Optional, Union

# Import directly from the module to avoid package-level import issues
from solace_agent_mesh.agent.tools.artifact_types import (
    ArtifactContent,
    ArtifactMetadata,
    is_artifact_content_type,
    get_artifact_content_info,
    is_artifact_metadata_type,
    ArtifactContentInfo,
)


class TestIsArtifactContentType:
    """Test cases for is_artifact_content_type function."""

    # Direct type checks
    def test_direct_artifact_content_type(self):
        """Direct ArtifactContent type should be detected."""
        assert is_artifact_content_type(ArtifactContent) is True

    def test_string_annotation_artifact_content(self):
        """String annotation 'ArtifactContent' should be detected."""
        assert is_artifact_content_type("ArtifactContent") is True

    def test_string_annotation_with_whitespace(self):
        """String annotation with whitespace should be detected."""
        assert is_artifact_content_type("  ArtifactContent  ") is True

    # List types
    def test_list_artifact_content(self):
        """List[ArtifactContent] should be detected."""
        assert is_artifact_content_type(List[ArtifactContent]) is True

    def test_list_string_not_artifact(self):
        """List[str] should NOT be detected as artifact type."""
        assert is_artifact_content_type(List[str]) is False

    def test_list_int_not_artifact(self):
        """List[int] should NOT be detected as artifact type."""
        assert is_artifact_content_type(List[int]) is False

    # Optional types
    def test_optional_artifact_content(self):
        """Optional[ArtifactContent] should be detected."""
        assert is_artifact_content_type(Optional[ArtifactContent]) is True

    def test_union_artifact_content_none(self):
        """Union[ArtifactContent, None] should be detected."""
        assert is_artifact_content_type(Union[ArtifactContent, None]) is True

    # Negative cases
    def test_regular_string_type(self):
        """Regular str type should NOT be detected."""
        assert is_artifact_content_type(str) is False

    def test_regular_bytes_type(self):
        """Regular bytes type should NOT be detected."""
        assert is_artifact_content_type(bytes) is False

    def test_regular_list_type(self):
        """Plain list type should NOT be detected."""
        assert is_artifact_content_type(list) is False

    def test_none_annotation(self):
        """None annotation should NOT be detected."""
        assert is_artifact_content_type(None) is False

    def test_regular_int_type(self):
        """Regular int type should NOT be detected."""
        assert is_artifact_content_type(int) is False

    def test_optional_string_not_artifact(self):
        """Optional[str] should NOT be detected."""
        assert is_artifact_content_type(Optional[str]) is False

    def test_union_string_int_not_artifact(self):
        """Union[str, int] should NOT be detected."""
        assert is_artifact_content_type(Union[str, int]) is False

    # String annotations for complex types
    def test_string_annotation_list_artifact_content(self):
        """String 'List[ArtifactContent]' should be detected."""
        assert is_artifact_content_type("List[ArtifactContent]") is True

    def test_string_annotation_optional_artifact_content(self):
        """String 'Optional[ArtifactContent]' should be detected."""
        assert is_artifact_content_type("Optional[ArtifactContent]") is True


class TestGetArtifactContentInfo:
    """Test cases for get_artifact_content_info function."""

    # Single artifact
    def test_single_artifact_info(self):
        """Direct ArtifactContent should return correct info."""
        info = get_artifact_content_info(ArtifactContent)
        assert info.is_artifact is True
        assert info.is_list is False
        assert info.is_optional is False

    # List artifact
    def test_list_artifact_info(self):
        """List[ArtifactContent] should return is_list=True."""
        info = get_artifact_content_info(List[ArtifactContent])
        assert info.is_artifact is True
        assert info.is_list is True
        assert info.is_optional is False

    # Optional variations
    def test_optional_artifact_info(self):
        """Optional[ArtifactContent] should return is_optional=True."""
        info = get_artifact_content_info(Optional[ArtifactContent])
        assert info.is_artifact is True
        assert info.is_list is False
        assert info.is_optional is True

    def test_optional_list_artifact_info(self):
        """Optional[List[ArtifactContent]] should return both is_list and is_optional=True."""
        info = get_artifact_content_info(Optional[List[ArtifactContent]])
        assert info.is_artifact is True
        assert info.is_list is True
        assert info.is_optional is True

    def test_union_artifact_none_info(self):
        """Union[ArtifactContent, None] should be detected as optional."""
        info = get_artifact_content_info(Union[ArtifactContent, None])
        assert info.is_artifact is True
        assert info.is_list is False
        assert info.is_optional is True

    # Non-artifact types
    def test_regular_type_returns_not_artifact(self):
        """Regular types should return is_artifact=False."""
        info = get_artifact_content_info(str)
        assert info.is_artifact is False
        assert info.is_list is False
        assert info.is_optional is False

    def test_none_returns_not_artifact(self):
        """None should return is_artifact=False."""
        info = get_artifact_content_info(None)
        assert info.is_artifact is False
        assert info.is_list is False
        assert info.is_optional is False

    def test_list_string_returns_not_artifact(self):
        """List[str] should return is_artifact=False."""
        info = get_artifact_content_info(List[str])
        assert info.is_artifact is False

    def test_optional_string_returns_not_artifact(self):
        """Optional[str] should return is_artifact=False."""
        info = get_artifact_content_info(Optional[str])
        assert info.is_artifact is False

    # String annotations
    def test_string_annotation_single(self):
        """String 'ArtifactContent' should return correct info."""
        info = get_artifact_content_info("ArtifactContent")
        assert info.is_artifact is True
        assert info.is_list is False
        assert info.is_optional is False

    def test_string_annotation_list(self):
        """String 'List[ArtifactContent]' should return correct info."""
        info = get_artifact_content_info("List[ArtifactContent]")
        assert info.is_artifact is True
        assert info.is_list is True
        assert info.is_optional is False

    def test_string_annotation_optional(self):
        """String 'Optional[ArtifactContent]' should return correct info."""
        info = get_artifact_content_info("Optional[ArtifactContent]")
        assert info.is_artifact is True
        assert info.is_list is False
        assert info.is_optional is True

    def test_string_annotation_optional_list(self):
        """String 'Optional[List[ArtifactContent]]' should return correct info."""
        info = get_artifact_content_info("Optional[List[ArtifactContent]]")
        assert info.is_artifact is True
        assert info.is_list is True
        assert info.is_optional is True

    def test_string_regular_type_not_artifact(self):
        """String 'str' should return is_artifact=False."""
        info = get_artifact_content_info("str")
        assert info.is_artifact is False


class TestArtifactContentInfoRepr:
    """Test cases for ArtifactContentInfo repr."""

    def test_repr_basic(self):
        """ArtifactContentInfo should have readable repr."""
        info = ArtifactContentInfo(is_artifact=True, is_list=False, is_optional=False)
        repr_str = repr(info)
        assert "is_artifact=True" in repr_str
        assert "is_list=False" in repr_str
        assert "is_optional=False" in repr_str

    def test_repr_full(self):
        """ArtifactContentInfo with all True should have readable repr."""
        info = ArtifactContentInfo(is_artifact=True, is_list=True, is_optional=True)
        repr_str = repr(info)
        assert "is_artifact=True" in repr_str
        assert "is_list=True" in repr_str
        assert "is_optional=True" in repr_str


class TestIsArtifactMetadataType:
    """Test cases for is_artifact_metadata_type function."""

    def test_direct_artifact_metadata_type(self):
        """Direct ArtifactMetadata type should be detected."""
        assert is_artifact_metadata_type(ArtifactMetadata) is True

    def test_string_annotation_artifact_metadata(self):
        """String annotation 'ArtifactMetadata' should be detected."""
        assert is_artifact_metadata_type("ArtifactMetadata") is True

    def test_artifact_content_not_metadata(self):
        """ArtifactContent should NOT be detected as ArtifactMetadata."""
        assert is_artifact_metadata_type(ArtifactContent) is False

    def test_none_not_metadata(self):
        """None should NOT be detected as ArtifactMetadata."""
        assert is_artifact_metadata_type(None) is False

    def test_regular_dict_not_metadata(self):
        """Regular dict should NOT be detected as ArtifactMetadata."""
        assert is_artifact_metadata_type(dict) is False
