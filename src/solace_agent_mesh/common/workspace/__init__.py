"""
Workspace management services for SAM.

Provides filesystem workspace abstraction for tools that need persistent
directories mountable into containers (e.g., Claude Code, git operations).
"""

from .base_workspace_service import BaseWorkspaceService
from .local_filesystem_workspace import LocalFilesystemWorkspaceService

__all__ = [
    "BaseWorkspaceService",
    "LocalFilesystemWorkspaceService",
]
