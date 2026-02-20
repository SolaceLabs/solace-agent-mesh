"""
Unit tests for artifact_types.py

Tests for the Artifact class and type detection functions that identify Artifact
type annotations for automatic artifact pre-loading.
"""

import pytest
from typing import List, Optional, Union

# Import directly from the module to avoid package-level import issues
from solace_agent_mesh.agent.tools.artifact_types import (
    Artifact,
    is_artifact_type,
    get_artifact_info,
    ArtifactTypeInfo,
)


class TestArtifactClass:
    """Test cases for the Artifact dataclass."""

    def test_artifact_creation_with_bytes(self):
        """Artifact can be created with bytes content."""
        artifact = Artifact(
            content=b"test content",
            filename="test.txt",
            version=1,
            mime_type="text/plain",
            metadata={"key": "value"},
        )
        assert artifact.content == b"test content"
        assert artifact.filename == "test.txt"
        assert artifact.version == 1
        assert artifact.mime_type == "text/plain"
        assert artifact.metadata == {"key": "value"}

    def test_artifact_creation_with_string(self):
        """Artifact can be created with string content."""
        artifact = Artifact(
            content="test content",
            filename="test.txt",
            version=0,
            mime_type="text/plain",
        )
        assert artifact.content == "test content"
        assert artifact.filename == "test.txt"
        assert artifact.version == 0
        assert artifact.mime_type == "text/plain"
        assert artifact.metadata == {}  # Default empty dict

    def test_as_text_from_bytes(self):
        """as_text() converts bytes to string."""
        artifact = Artifact(
            content=b"hello world",
            filename="test.txt",
            version=1,
            mime_type="text/plain",
        )
        assert artifact.as_text() == "hello world"

    def test_as_text_from_string(self):
        """as_text() returns string as-is."""
        artifact = Artifact(
            content="hello world",
            filename="test.txt",
            version=1,
            mime_type="text/plain",
        )
        assert artifact.as_text() == "hello world"

    def test_as_text_with_custom_encoding(self):
        """as_text() supports custom encoding."""
        content = "héllo wörld"
        artifact = Artifact(
            content=content.encode("latin-1"),
            filename="test.txt",
            version=1,
            mime_type="text/plain",
        )
        assert artifact.as_text(encoding="latin-1") == "héllo wörld"

    def test_as_bytes_from_string(self):
        """as_bytes() converts string to bytes."""
        artifact = Artifact(
            content="hello world",
            filename="test.txt",
            version=1,
            mime_type="text/plain",
        )
        assert artifact.as_bytes() == b"hello world"

    def test_as_bytes_from_bytes(self):
        """as_bytes() returns bytes as-is."""
        artifact = Artifact(
            content=b"hello world",
            filename="test.txt",
            version=1,
            mime_type="text/plain",
        )
        assert artifact.as_bytes() == b"hello world"

    def test_as_bytes_with_custom_encoding(self):
        """as_bytes() supports custom encoding."""
        artifact = Artifact(
            content="héllo wörld",
            filename="test.txt",
            version=1,
            mime_type="text/plain",
        )
        assert artifact.as_bytes(encoding="latin-1") == "héllo wörld".encode("latin-1")


class TestIsArtifactType:
    """Test cases for is_artifact_type function."""

    # Direct type checks
    def test_direct_artifact_type(self):
        """Direct Artifact type should be detected."""
        assert is_artifact_type(Artifact) is True

    def test_string_annotation_artifact(self):
        """String annotation 'Artifact' should be detected."""
        assert is_artifact_type("Artifact") is True

    def test_string_annotation_with_whitespace(self):
        """String annotation with whitespace should be detected."""
        assert is_artifact_type("  Artifact  ") is True

    # List types
    def test_list_artifact(self):
        """List[Artifact] should be detected."""
        assert is_artifact_type(List[Artifact]) is True

    def test_list_string_not_artifact(self):
        """List[str] should NOT be detected as artifact type."""
        assert is_artifact_type(List[str]) is False

    def test_list_int_not_artifact(self):
        """List[int] should NOT be detected as artifact type."""
        assert is_artifact_type(List[int]) is False

    # Optional types
    def test_optional_artifact(self):
        """Optional[Artifact] should be detected."""
        assert is_artifact_type(Optional[Artifact]) is True

    def test_union_artifact_none(self):
        """Union[Artifact, None] should be detected."""
        assert is_artifact_type(Union[Artifact, None]) is True

    # Negative cases
    def test_regular_string_type(self):
        """Regular str type should NOT be detected."""
        assert is_artifact_type(str) is False

    def test_regular_bytes_type(self):
        """Regular bytes type should NOT be detected."""
        assert is_artifact_type(bytes) is False

    def test_regular_list_type(self):
        """Plain list type should NOT be detected."""
        assert is_artifact_type(list) is False

    def test_none_annotation(self):
        """None annotation should NOT be detected."""
        assert is_artifact_type(None) is False

    def test_regular_int_type(self):
        """Regular int type should NOT be detected."""
        assert is_artifact_type(int) is False

    def test_optional_string_not_artifact(self):
        """Optional[str] should NOT be detected."""
        assert is_artifact_type(Optional[str]) is False

    def test_union_string_int_not_artifact(self):
        """Union[str, int] should NOT be detected."""
        assert is_artifact_type(Union[str, int]) is False

    # String annotations for complex types
    def test_string_annotation_list_artifact(self):
        """String 'List[Artifact]' should be detected."""
        assert is_artifact_type("List[Artifact]") is True

    def test_string_annotation_optional_artifact(self):
        """String 'Optional[Artifact]' should be detected."""
        assert is_artifact_type("Optional[Artifact]") is True

    # Ensure ArtifactContent doesn't match (old name)
    def test_string_artifact_content_not_matched(self):
        """String 'ArtifactContent' should NOT match Artifact type."""
        assert is_artifact_type("ArtifactContent") is False


class TestGetArtifactInfo:
    """Test cases for get_artifact_info function."""

    # Single artifact
    def test_single_artifact_info(self):
        """Direct Artifact should return correct info."""
        info = get_artifact_info(Artifact)
        assert info.is_artifact is True
        assert info.is_list is False
        assert info.is_optional is False

    # List artifact
    def test_list_artifact_info(self):
        """List[Artifact] should return is_list=True."""
        info = get_artifact_info(List[Artifact])
        assert info.is_artifact is True
        assert info.is_list is True
        assert info.is_optional is False

    # Optional variations
    def test_optional_artifact_info(self):
        """Optional[Artifact] should return is_optional=True."""
        info = get_artifact_info(Optional[Artifact])
        assert info.is_artifact is True
        assert info.is_list is False
        assert info.is_optional is True

    def test_optional_list_artifact_info(self):
        """Optional[List[Artifact]] should return both is_list and is_optional=True."""
        info = get_artifact_info(Optional[List[Artifact]])
        assert info.is_artifact is True
        assert info.is_list is True
        assert info.is_optional is True

    def test_union_artifact_none_info(self):
        """Union[Artifact, None] should be detected as optional."""
        info = get_artifact_info(Union[Artifact, None])
        assert info.is_artifact is True
        assert info.is_list is False
        assert info.is_optional is True

    # Non-artifact types
    def test_regular_type_returns_not_artifact(self):
        """Regular types should return is_artifact=False."""
        info = get_artifact_info(str)
        assert info.is_artifact is False
        assert info.is_list is False
        assert info.is_optional is False

    def test_none_returns_not_artifact(self):
        """None should return is_artifact=False."""
        info = get_artifact_info(None)
        assert info.is_artifact is False
        assert info.is_list is False
        assert info.is_optional is False

    def test_list_string_returns_not_artifact(self):
        """List[str] should return is_artifact=False."""
        info = get_artifact_info(List[str])
        assert info.is_artifact is False

    def test_optional_string_returns_not_artifact(self):
        """Optional[str] should return is_artifact=False."""
        info = get_artifact_info(Optional[str])
        assert info.is_artifact is False

    # String annotations
    def test_string_annotation_single(self):
        """String 'Artifact' should return correct info."""
        info = get_artifact_info("Artifact")
        assert info.is_artifact is True
        assert info.is_list is False
        assert info.is_optional is False

    def test_string_annotation_list(self):
        """String 'List[Artifact]' should return correct info."""
        info = get_artifact_info("List[Artifact]")
        assert info.is_artifact is True
        assert info.is_list is True
        assert info.is_optional is False

    def test_string_annotation_optional(self):
        """String 'Optional[Artifact]' should return correct info."""
        info = get_artifact_info("Optional[Artifact]")
        assert info.is_artifact is True
        assert info.is_list is False
        assert info.is_optional is True

    def test_string_regular_type_not_artifact(self):
        """String 'str' should return is_artifact=False."""
        info = get_artifact_info("str")
        assert info.is_artifact is False


class TestArtifactTypeInfoRepr:
    """Test cases for ArtifactTypeInfo repr."""

    def test_repr_basic(self):
        """ArtifactTypeInfo should have readable repr."""
        info = ArtifactTypeInfo(is_artifact=True, is_list=False, is_optional=False)
        repr_str = repr(info)
        assert "is_artifact=True" in repr_str
        assert "is_list=False" in repr_str
        assert "is_optional=False" in repr_str

    def test_repr_full(self):
        """ArtifactTypeInfo with all True should have readable repr."""
        info = ArtifactTypeInfo(is_artifact=True, is_list=True, is_optional=True)
        repr_str = repr(info)
        assert "is_artifact=True" in repr_str
        assert "is_list=True" in repr_str
        assert "is_optional=True" in repr_str
