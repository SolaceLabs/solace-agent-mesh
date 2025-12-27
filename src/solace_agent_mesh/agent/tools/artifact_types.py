"""
Defines type hints for artifact pre-loading in tool parameters.

When a tool parameter is annotated with `ArtifactContent`, the framework will:
1. Accept a filename string from the LLM
2. Load the artifact content before invoking the tool
3. Pass the actual content (bytes or str) to the tool instead of the filename

This allows tools to work directly with artifact data without needing to
manually load artifacts, and is especially useful for Lambda/HTTP executors
that cannot access the artifact store directly.

Supported type annotations:
    - ArtifactContent: Single artifact, LLM provides filename string
    - List[ArtifactContent]: Multiple artifacts, LLM provides list of filenames
    - Optional[ArtifactContent]: Optional single artifact

Example usage:
    from solace_agent_mesh.agent.tools import ArtifactContent
    from typing import List, Optional

    async def process_data(
        input_file: ArtifactContent,  # Framework loads, tool receives content
        output_name: str,              # Regular string passed through
    ) -> ToolResult:
        # input_file is already the artifact content (str or bytes)
        result = analyze(input_file)
        return ToolResult.ok("Done", data={"summary": result})

    async def merge_files(
        input_files: List[ArtifactContent],  # Framework loads all, tool receives list of content
        output_name: str,
    ) -> ToolResult:
        # input_files is a list of artifact contents
        merged = b"".join(input_files)
        return ToolResult.ok("Merged", data={"size": len(merged)})

Schema translation:
    - ArtifactContent -> LLM sees: string (artifact filename)
    - List[ArtifactContent] -> LLM sees: array of strings (artifact filenames)
    - Tool receives: actual artifact content(s) as str/bytes or list thereof
"""

from typing import Union, NewType, List, Optional, get_origin, get_args


# Type hint that triggers artifact pre-loading
# LLM schema translation: ArtifactContent -> string (artifact filename)
# The framework intercepts this parameter, loads the artifact, and replaces
# the filename with the actual content before calling the tool.
ArtifactContent = NewType("ArtifactContent", Union[bytes, str])

# Optional: For loading only metadata without content
# Useful when tools need artifact info but not the full content
ArtifactMetadata = NewType("ArtifactMetadata", dict)


# Sentinel object to identify ArtifactContent type at runtime
# Used by the framework to detect which parameters need pre-loading
class _ArtifactContentMarker:
    """Internal marker class for runtime type detection."""
    pass


def _is_direct_artifact_content(annotation) -> bool:
    """Check if annotation is directly ArtifactContent (not wrapped in List/Optional)."""
    if annotation is None:
        return False

    # Direct type reference
    if annotation is ArtifactContent:
        return True

    # String annotation (forward reference)
    if isinstance(annotation, str):
        # Check for exact match or simple annotation
        stripped = annotation.strip()
        if stripped == "ArtifactContent":
            return True

    # NewType creates a callable, check its __supertype__
    if hasattr(annotation, "__supertype__"):
        if getattr(annotation, "__name__", None) == "ArtifactContent":
            return True

    return False


def is_artifact_content_type(annotation) -> bool:
    """
    Check if a type annotation represents an ArtifactContent parameter.

    Handles various forms of type annotations:
    - Direct ArtifactContent reference
    - List[ArtifactContent] - list of artifacts
    - Optional[ArtifactContent] - optional artifact
    - String annotation "ArtifactContent"
    - Forward reference containing "ArtifactContent"

    Args:
        annotation: The type annotation to check

    Returns:
        True if the annotation represents ArtifactContent (possibly wrapped)
    """
    if annotation is None:
        return False

    # Check direct match first
    if _is_direct_artifact_content(annotation):
        return True

    # String annotation containing ArtifactContent (e.g., "List[ArtifactContent]")
    if isinstance(annotation, str):
        return "ArtifactContent" in annotation

    # Check for generic types (List[ArtifactContent], Optional[ArtifactContent], etc.)
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        if args:
            # For List[ArtifactContent]
            if origin is list:
                return _is_direct_artifact_content(args[0])

            # For Optional[ArtifactContent] (which is Union[ArtifactContent, None])
            if origin is Union:
                # Check if any non-None arg is ArtifactContent
                for arg in args:
                    if arg is not type(None) and _is_direct_artifact_content(arg):
                        return True

    return False


class ArtifactContentInfo:
    """Information about an ArtifactContent type annotation."""

    def __init__(
        self,
        is_artifact: bool = False,
        is_list: bool = False,
        is_optional: bool = False,
    ):
        self.is_artifact = is_artifact
        self.is_list = is_list
        self.is_optional = is_optional

    def __repr__(self):
        return f"ArtifactContentInfo(is_artifact={self.is_artifact}, is_list={self.is_list}, is_optional={self.is_optional})"


def get_artifact_content_info(annotation) -> ArtifactContentInfo:
    """
    Get detailed information about an ArtifactContent type annotation.

    This function analyzes the type annotation to determine:
    - Whether it's an ArtifactContent type at all
    - Whether it's a list (List[ArtifactContent])
    - Whether it's optional (Optional[ArtifactContent])

    Args:
        annotation: The type annotation to analyze

    Returns:
        ArtifactContentInfo with details about the annotation

    Examples:
        get_artifact_content_info(ArtifactContent)
        # -> ArtifactContentInfo(is_artifact=True, is_list=False, is_optional=False)

        get_artifact_content_info(List[ArtifactContent])
        # -> ArtifactContentInfo(is_artifact=True, is_list=True, is_optional=False)

        get_artifact_content_info(Optional[ArtifactContent])
        # -> ArtifactContentInfo(is_artifact=True, is_list=False, is_optional=True)
    """
    if annotation is None:
        return ArtifactContentInfo()

    # Check direct match
    if _is_direct_artifact_content(annotation):
        return ArtifactContentInfo(is_artifact=True)

    # String annotation
    if isinstance(annotation, str):
        if "ArtifactContent" not in annotation:
            return ArtifactContentInfo()
        # Parse string annotation
        is_list = "List[" in annotation or "list[" in annotation
        is_optional = "Optional[" in annotation or "None" in annotation
        return ArtifactContentInfo(
            is_artifact=True, is_list=is_list, is_optional=is_optional
        )

    # Check for generic types
    origin = get_origin(annotation)
    if origin is None:
        return ArtifactContentInfo()

    args = get_args(annotation)
    if not args:
        return ArtifactContentInfo()

    # For List[ArtifactContent]
    if origin is list:
        if _is_direct_artifact_content(args[0]):
            return ArtifactContentInfo(is_artifact=True, is_list=True)
        return ArtifactContentInfo()

    # For Optional[ArtifactContent] (Union[ArtifactContent, None])
    if origin is Union:
        # Check if this is Optional (has None as one arg)
        has_none = type(None) in args
        for arg in args:
            if arg is not type(None):
                if _is_direct_artifact_content(arg):
                    return ArtifactContentInfo(
                        is_artifact=True, is_list=False, is_optional=has_none
                    )
                # Check for Optional[List[ArtifactContent]]
                inner_origin = get_origin(arg)
                if inner_origin is list:
                    inner_args = get_args(arg)
                    if inner_args and _is_direct_artifact_content(inner_args[0]):
                        return ArtifactContentInfo(
                            is_artifact=True, is_list=True, is_optional=has_none
                        )

    return ArtifactContentInfo()


def is_artifact_metadata_type(annotation) -> bool:
    """
    Check if a type annotation represents an ArtifactMetadata parameter.

    Args:
        annotation: The type annotation to check

    Returns:
        True if the annotation represents ArtifactMetadata
    """
    if annotation is None:
        return False

    # Direct type reference
    if annotation is ArtifactMetadata:
        return True

    # String annotation (forward reference)
    if isinstance(annotation, str):
        return "ArtifactMetadata" in annotation

    # NewType check
    if hasattr(annotation, "__supertype__"):
        if getattr(annotation, "__name__", None) == "ArtifactMetadata":
            return True

    return False
