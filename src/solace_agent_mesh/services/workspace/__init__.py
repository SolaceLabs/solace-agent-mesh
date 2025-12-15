"""
Workspace Management Service.

Provides workspace lifecycle management for Claude Code execution:
- Download/upload workspace tarballs from artifact service
- Type-specific initialization (app template, git clone)
- Type-specific finalization (sync dist/, cleanup)
"""

from .types import (
    WorkspaceType,
    WorkspaceConfig,
    AppWorkspaceConfig,
    RepoWorkspaceConfig,
)
from .manager import WorkspaceManager

__all__ = [
    "WorkspaceType",
    "WorkspaceConfig",
    "AppWorkspaceConfig",
    "RepoWorkspaceConfig",
    "WorkspaceManager",
]
