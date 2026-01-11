"""
Re-exports Artifact types from the shared agent_tools package.

This module provides backward compatibility for existing code that imports
from `solace_agent_mesh.agent.tools.artifact_types`. All types are now defined
in the shared `agent_tools` package to enable use in both SAM and Lambda.

Usage (unchanged):
    from solace_agent_mesh.agent.tools.artifact_types import (
        Artifact,
        ArtifactTypeInfo,
        is_artifact_type,
        get_artifact_info,
    )

    # Or from the shared package directly:
    from agent_tools import Artifact, ArtifactTypeInfo, is_artifact_type, get_artifact_info
"""

# Re-export from shared package
from agent_tools import (
    Artifact,
    ArtifactTypeInfo,
    is_artifact_type,
    get_artifact_info,
)

# Re-export for backward compatibility
__all__ = [
    "Artifact",
    "ArtifactTypeInfo",
    "is_artifact_type",
    "get_artifact_info",
]
