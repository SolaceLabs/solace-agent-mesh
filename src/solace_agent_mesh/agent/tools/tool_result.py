"""
Re-exports ToolResult types from the shared agent_tools package.

This module provides backward compatibility for existing code that imports
from `solace_agent_mesh.agent.tools.tool_result`. All types are now defined
in the shared `agent_tools` package to enable use in both SAM and Lambda.

Usage (unchanged):
    from solace_agent_mesh.agent.tools.tool_result import (
        ToolResult,
        DataObject,
        DataDisposition,
    )

    # Or from the shared package directly:
    from agent_tools import ToolResult, DataObject, DataDisposition
"""

# Re-export from shared package
from agent_tools import (
    ToolResult,
    DataObject,
    DataDisposition,
    TOOL_RESULT_SCHEMA_VERSION,
)

# Re-export for backward compatibility
__all__ = [
    "ToolResult",
    "DataObject",
    "DataDisposition",
    "TOOL_RESULT_SCHEMA_VERSION",
]
