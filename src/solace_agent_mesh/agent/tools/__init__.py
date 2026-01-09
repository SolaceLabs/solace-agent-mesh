"""
This __init__.py file ensures that all built-in tool modules are imported
when the 'tools' package is loaded. This is crucial for the declarative
tool registration pattern, as it triggers the `tool_registry.register()`
calls within each tool module.
"""

from . import builtin_artifact_tools
from . import builtin_data_analysis_tools
from . import general_agent_tools
from . import audio_tools
from . import image_tools
from . import web_tools
from . import time_tools
from . import test_tools
from . import deep_research_tools
from . import web_search_tools
from . import dynamic_tool

# Export ToolResult abstraction for tool authors
from .tool_result import ToolResult, DataObject, DataDisposition

# Export artifact types for tool authors
from .artifact_types import (
    Artifact,
    ArtifactTypeInfo,
    get_artifact_info,
)

__all__ = [
    "ToolResult",
    "DataObject",
    "DataDisposition",
    "Artifact",
    "ArtifactTypeInfo",
    "get_artifact_info",
]
