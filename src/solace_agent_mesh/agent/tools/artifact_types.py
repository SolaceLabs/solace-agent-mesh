"""
Defines type hints for artifact pre-loading in tool parameters.

When a tool parameter is annotated with `Artifact`, the framework will:
1. Accept a filename string (optionally with version as filename:version) from the LLM
2. Load the artifact content and metadata before invoking the tool
3. Pass an Artifact object containing content and all metadata to the tool

This allows tools to work directly with artifact data without needing to
manually load artifacts, and is especially useful for Lambda executors
that cannot access the artifact store directly.

Supported type annotations:
    - Artifact: Single artifact, LLM provides filename string
    - List[Artifact]: Multiple artifacts, LLM provides list of filenames
    - Optional[Artifact]: Optional single artifact

Example usage:
    from solace_agent_mesh.agent.tools import Artifact
    from typing import List, Optional

    async def process_data(
        input_file: Artifact,      # Framework loads, tool receives Artifact object
        output_name: str,          # Regular string passed through
    ) -> ToolResult:
        # input_file is an Artifact with content and metadata
        content = input_file.as_text()
        print(f"Processing {input_file.filename} v{input_file.version}")
        print(f"MIME type: {input_file.mime_type}")
        result = analyze(content)
        return ToolResult.ok("Done", data={"summary": result})

    async def merge_files(
        input_files: List[Artifact],  # Framework loads all artifacts
        output_name: str,
    ) -> ToolResult:
        # input_files is a list of Artifact objects
        merged = b"".join(f.as_bytes() for f in input_files)
        return ToolResult.ok("Merged", data={"size": len(merged)})

Schema translation:
    - Artifact -> LLM sees: string (artifact filename, optionally with :version)
    - List[Artifact] -> LLM sees: array of strings (artifact filenames)
    - Tool receives: Artifact object(s) with content and full metadata
"""

from dataclasses import dataclass, field
from typing import Union, List, Optional, get_origin, get_args, Any, Dict


@dataclass
class Artifact:
    """
    A loaded artifact with content and metadata.

    When a tool parameter is type-hinted with `Artifact`, the framework automatically
    loads the artifact before invoking the tool. The tool receives this object instead
    of just the filename, giving access to both the content and all metadata.

    Attributes:
        content: The actual artifact data (bytes or str)
        filename: Original filename of the artifact
        version: Version number that was loaded
        mime_type: MIME type of the content (e.g., "text/plain", "image/png")
        metadata: Custom metadata dictionary associated with the artifact

    Example:
        async def process_file(data: Artifact) -> ToolResult:
            # Access content as text
            text = data.as_text()

            # Or as bytes
            raw = data.as_bytes()

            # Access metadata
            print(f"File: {data.filename}, Version: {data.version}")
            print(f"Type: {data.mime_type}")
            print(f"Custom metadata: {data.metadata}")

            return ToolResult.ok("Processed")
    """

    content: Union[str, bytes]
    filename: str
    version: int
    mime_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_text(self, encoding: str = "utf-8") -> str:
        """
        Get content as a text string.

        Args:
            encoding: Character encoding to use when decoding bytes. Defaults to UTF-8.

        Returns:
            The content as a string.
        """
        if isinstance(self.content, bytes):
            return self.content.decode(encoding)
        return self.content

    def as_bytes(self, encoding: str = "utf-8") -> bytes:
        """
        Get content as bytes.

        Args:
            encoding: Character encoding to use when encoding string. Defaults to UTF-8.

        Returns:
            The content as bytes.
        """
        if isinstance(self.content, str):
            return self.content.encode(encoding)
        return self.content


def _is_direct_artifact_type(annotation) -> bool:
    """Check if annotation is directly Artifact (not wrapped in List/Optional)."""
    if annotation is None:
        return False

    # Direct type reference
    if annotation is Artifact:
        return True

    # String annotation (forward reference)
    if isinstance(annotation, str):
        stripped = annotation.strip()
        if stripped == "Artifact":
            return True

    return False


def is_artifact_type(annotation) -> bool:
    """
    Check if a type annotation represents an Artifact parameter.

    Handles various forms of type annotations:
    - Direct Artifact reference
    - List[Artifact] - list of artifacts
    - Optional[Artifact] - optional artifact
    - String annotation "Artifact"
    - Forward reference containing "Artifact"

    Args:
        annotation: The type annotation to check

    Returns:
        True if the annotation represents Artifact (possibly wrapped)
    """
    if annotation is None:
        return False

    # Check direct match first
    if _is_direct_artifact_type(annotation):
        return True

    # String annotation containing Artifact (e.g., "List[Artifact]")
    if isinstance(annotation, str):
        # Be careful not to match "ArtifactContent" or other partial matches
        # Check for standalone "Artifact" or as a type parameter
        stripped = annotation.strip()
        if stripped == "Artifact":
            return True
        # Check for List[Artifact], Optional[Artifact], etc.
        if "List[Artifact]" in annotation or "list[Artifact]" in annotation:
            return True
        if "Optional[Artifact]" in annotation:
            return True
        return False

    # Check for generic types (List[Artifact], Optional[Artifact], etc.)
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        if args:
            # For List[Artifact]
            if origin is list:
                return _is_direct_artifact_type(args[0])

            # For Optional[Artifact] (which is Union[Artifact, None])
            if origin is Union:
                # Check if any non-None arg is Artifact
                for arg in args:
                    if arg is not type(None) and _is_direct_artifact_type(arg):
                        return True

    return False


@dataclass
class ArtifactTypeInfo:
    """Information about an Artifact type annotation."""

    is_artifact: bool = False
    is_list: bool = False
    is_optional: bool = False

    def __repr__(self):
        return f"ArtifactTypeInfo(is_artifact={self.is_artifact}, is_list={self.is_list}, is_optional={self.is_optional})"


def get_artifact_info(annotation) -> ArtifactTypeInfo:
    """
    Get detailed information about an Artifact type annotation.

    This function analyzes the type annotation to determine:
    - Whether it's an Artifact type at all
    - Whether it's a list (List[Artifact])
    - Whether it's optional (Optional[Artifact])

    Args:
        annotation: The type annotation to analyze

    Returns:
        ArtifactTypeInfo with details about the annotation

    Examples:
        get_artifact_info(Artifact)
        # -> ArtifactTypeInfo(is_artifact=True, is_list=False, is_optional=False)

        get_artifact_info(List[Artifact])
        # -> ArtifactTypeInfo(is_artifact=True, is_list=True, is_optional=False)

        get_artifact_info(Optional[Artifact])
        # -> ArtifactTypeInfo(is_artifact=True, is_list=False, is_optional=True)
    """
    if annotation is None:
        return ArtifactTypeInfo()

    # Check direct match
    if _is_direct_artifact_type(annotation):
        return ArtifactTypeInfo(is_artifact=True)

    # String annotation
    if isinstance(annotation, str):
        stripped = annotation.strip()
        if stripped == "Artifact":
            return ArtifactTypeInfo(is_artifact=True)
        # Parse string annotation for List/Optional
        if "Artifact" not in annotation:
            return ArtifactTypeInfo()
        is_list = "List[Artifact]" in annotation or "list[Artifact]" in annotation
        is_optional = "Optional[Artifact]" in annotation or (
            "Artifact" in annotation and "None" in annotation
        )
        if is_list or is_optional or stripped == "Artifact":
            return ArtifactTypeInfo(
                is_artifact=True, is_list=is_list, is_optional=is_optional
            )
        return ArtifactTypeInfo()

    # Check for generic types
    origin = get_origin(annotation)
    if origin is None:
        return ArtifactTypeInfo()

    args = get_args(annotation)
    if not args:
        return ArtifactTypeInfo()

    # For List[Artifact]
    if origin is list:
        if _is_direct_artifact_type(args[0]):
            return ArtifactTypeInfo(is_artifact=True, is_list=True)
        return ArtifactTypeInfo()

    # For Optional[Artifact] (Union[Artifact, None])
    if origin is Union:
        # Check if this is Optional (has None as one arg)
        has_none = type(None) in args
        for arg in args:
            if arg is not type(None):
                if _is_direct_artifact_type(arg):
                    return ArtifactTypeInfo(
                        is_artifact=True, is_list=False, is_optional=has_none
                    )
                # Check for Optional[List[Artifact]]
                inner_origin = get_origin(arg)
                if inner_origin is list:
                    inner_args = get_args(arg)
                    if inner_args and _is_direct_artifact_type(inner_args[0]):
                        return ArtifactTypeInfo(
                            is_artifact=True, is_list=True, is_optional=has_none
                        )

    return ArtifactTypeInfo()
