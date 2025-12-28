"""
Test support module for testing Artifact type hint artifact pre-loading.

These tools use Artifact and List[Artifact] type hints to verify
that the framework correctly pre-loads artifact objects before tool execution.
"""

from typing import List, Optional

from google.adk.tools import ToolContext

from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool, DynamicToolProvider
from solace_agent_mesh.agent.tools.artifact_types import Artifact


class ArtifactContentToolProvider(DynamicToolProvider):
    """
    Provider for tools that test Artifact type hint pre-loading.
    """

    def create_tools(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        # Decorated tools are automatically included by the framework
        return []


@ArtifactContentToolProvider.register_tool
async def process_single_artifact(
    self,
    input_content: Artifact,
    input_filename: str,
    tool_context: ToolContext = None,
) -> dict:
    """
    Test tool that receives a single Artifact parameter.

    The framework should pre-load the artifact based on the filename
    provided by the LLM and pass an Artifact object to this function.

    Args:
        input_content: The artifact object (pre-loaded by framework)
        input_filename: The filename (passed through as-is)

    Returns:
        Dict with received artifact info for verification
    """
    # Get content as text
    content_str = input_content.as_text()

    return {
        "status": "success",
        "received_content": content_str,
        "received_content_type": "bytes" if isinstance(input_content.content, bytes) else "str",
        "received_content_length": len(content_str),
        "received_filename": input_filename,
        # Include metadata from Artifact object
        "artifact_filename": input_content.filename,
        "artifact_version": input_content.version,
        "artifact_mime_type": input_content.mime_type,
    }


@ArtifactContentToolProvider.register_tool
async def process_multiple_artifacts(
    self,
    input_files: List[Artifact],
    tool_context: ToolContext = None,
) -> dict:
    """
    Test tool that receives a List[Artifact] parameter.

    The framework should pre-load all artifacts based on the filenames
    provided by the LLM and pass a list of Artifact objects to this function.

    Args:
        input_files: List of artifact objects (pre-loaded by framework)

    Returns:
        Dict with received artifacts info for verification
    """
    contents = []
    for artifact in input_files:
        contents.append(artifact.as_text())

    return {
        "status": "success",
        "received_count": len(contents),
        "received_contents": contents,
    }


@ArtifactContentToolProvider.register_tool
async def process_optional_artifact(
    self,
    input_content: Optional[Artifact] = None,
    fallback_value: str = "default",
    tool_context: ToolContext = None,
) -> dict:
    """
    Test tool that receives an Optional[Artifact] parameter.

    Args:
        input_content: Optional artifact (pre-loaded if provided)
        fallback_value: Value to use if no artifact provided

    Returns:
        Dict with received content info for verification
    """
    if input_content is None:
        return {
            "status": "success",
            "used_fallback": True,
            "received_content": fallback_value,
        }

    content_str = input_content.as_text()

    return {
        "status": "success",
        "used_fallback": False,
        "received_content": content_str,
    }


@ArtifactContentToolProvider.register_tool
async def process_mixed_params(
    self,
    input_content: Artifact,
    output_filename: str,
    max_length: int = 1000,
    include_metadata: bool = False,
    tool_context: ToolContext = None,
) -> dict:
    """
    Test tool with mixed Artifact and regular parameters.

    Args:
        input_content: Artifact object (pre-loaded by framework)
        output_filename: Output filename (regular string)
        max_length: Maximum content length to process
        include_metadata: Whether to include metadata

    Returns:
        Dict with all received parameters for verification
    """
    content_str = input_content.as_text()

    # Truncate if needed
    truncated = len(content_str) > max_length
    if truncated:
        content_str = content_str[:max_length]

    result = {
        "status": "success",
        "received_content": content_str,
        "received_output_filename": output_filename,
        "received_max_length": max_length,
        "received_include_metadata": include_metadata,
        "was_truncated": truncated,
    }

    if include_metadata:
        result["metadata"] = {
            "original_length": len(input_content.as_text()),
            "truncated": truncated,
            "artifact_filename": input_content.filename,
            "artifact_version": input_content.version,
            "artifact_mime_type": input_content.mime_type,
        }

    return result
