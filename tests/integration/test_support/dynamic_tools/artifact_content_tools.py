"""
Test support module for testing ArtifactContent type hint artifact pre-loading.

These tools use ArtifactContent and List[ArtifactContent] type hints to verify
that the framework correctly pre-loads artifact content before tool execution.
"""

from typing import List, Optional

from google.adk.tools import ToolContext

from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool, DynamicToolProvider
from solace_agent_mesh.agent.tools.artifact_types import ArtifactContent


class ArtifactContentToolProvider(DynamicToolProvider):
    """
    Provider for tools that test ArtifactContent type hint pre-loading.
    """

    def create_tools(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        # Decorated tools are automatically included by the framework
        return []


@ArtifactContentToolProvider.register_tool
async def process_single_artifact(
    self,
    input_content: ArtifactContent,
    input_filename: str,
    tool_context: ToolContext = None,
) -> dict:
    """
    Test tool that receives a single ArtifactContent parameter.

    The framework should pre-load the artifact content based on the filename
    provided by the LLM and pass the actual content to this function.

    Args:
        input_content: The artifact content (pre-loaded by framework)
        input_filename: The filename (passed through as-is)

    Returns:
        Dict with received content info for verification
    """
    # Decode bytes to string if needed
    if isinstance(input_content, bytes):
        content_str = input_content.decode("utf-8")
        content_type = "bytes"
    else:
        content_str = str(input_content)
        content_type = "str"

    return {
        "status": "success",
        "received_content": content_str,
        "received_content_type": content_type,
        "received_content_length": len(content_str),
        "received_filename": input_filename,
    }


@ArtifactContentToolProvider.register_tool
async def process_multiple_artifacts(
    self,
    input_files: List[ArtifactContent],
    tool_context: ToolContext = None,
) -> dict:
    """
    Test tool that receives a List[ArtifactContent] parameter.

    The framework should pre-load all artifact contents based on the filenames
    provided by the LLM and pass a list of actual contents to this function.

    Args:
        input_files: List of artifact contents (pre-loaded by framework)

    Returns:
        Dict with received contents info for verification
    """
    contents = []
    for content in input_files:
        if isinstance(content, bytes):
            contents.append(content.decode("utf-8"))
        else:
            contents.append(str(content))

    return {
        "status": "success",
        "received_count": len(contents),
        "received_contents": contents,
    }


@ArtifactContentToolProvider.register_tool
async def process_optional_artifact(
    self,
    input_content: Optional[ArtifactContent] = None,
    fallback_value: str = "default",
    tool_context: ToolContext = None,
) -> dict:
    """
    Test tool that receives an Optional[ArtifactContent] parameter.

    Args:
        input_content: Optional artifact content (pre-loaded if provided)
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

    if isinstance(input_content, bytes):
        content_str = input_content.decode("utf-8")
    else:
        content_str = str(input_content)

    return {
        "status": "success",
        "used_fallback": False,
        "received_content": content_str,
    }


@ArtifactContentToolProvider.register_tool
async def process_mixed_params(
    self,
    input_content: ArtifactContent,
    output_filename: str,
    max_length: int = 1000,
    include_metadata: bool = False,
    tool_context: ToolContext = None,
) -> dict:
    """
    Test tool with mixed ArtifactContent and regular parameters.

    Args:
        input_content: Artifact content (pre-loaded by framework)
        output_filename: Output filename (regular string)
        max_length: Maximum content length to process
        include_metadata: Whether to include metadata

    Returns:
        Dict with all received parameters for verification
    """
    if isinstance(input_content, bytes):
        content_str = input_content.decode("utf-8")
    else:
        content_str = str(input_content)

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
            "original_length": len(content_str) if not truncated else "unknown",
            "truncated": truncated,
        }

    return result
