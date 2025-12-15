"""
Workspace type definitions and configuration dataclasses.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class WorkspaceType(Enum):
    """Types of workspaces supported by WorkspaceManager."""

    APP = "app"
    """SAM App Builder workspace - React apps with template initialization."""

    REPO = "repo"
    """GitHub repository workspace - for issue resolution (future)."""

    GENERIC = "generic"
    """Generic workspace - minimal initialization."""


@dataclass
class AppWorkspaceConfig:
    """Configuration for APP workspace type."""

    sync_dist: bool = True
    """Whether to sync dist/ to app storage after Claude Code completes."""

    template_path: str = "/template"
    """Path to template in container (for initialization)."""


@dataclass
class RepoWorkspaceConfig:
    """Configuration for REPO workspace type (future)."""

    repo_url: str = ""
    """Git repository URL to clone."""

    branch: str = "main"
    """Branch to checkout."""

    issue_number: Optional[int] = None
    """GitHub issue number being worked on."""

    # Note: Credentials (GITHUB_TOKEN) passed via environment


@dataclass
class WorkspaceConfig:
    """
    Configuration for a workspace lifecycle.

    This is passed to WorkspaceManager to control how the workspace
    is initialized, executed, and finalized.
    """

    type: WorkspaceType
    """Type of workspace - determines init/finalize behavior."""

    user_id: str
    """User identifier for storage paths."""

    workspace_id: str
    """Workspace identifier (e.g., app_id, repo_slug)."""

    workspace_name: str
    """Human-readable name for the workspace."""

    ephemeral: bool = False
    """If True, workspace is deleted after finalization."""

    # Type-specific configuration
    app_config: Optional[AppWorkspaceConfig] = None
    """Configuration for APP workspace type."""

    repo_config: Optional[RepoWorkspaceConfig] = None
    """Configuration for REPO workspace type."""

    # Initialization state
    is_new_workspace: bool = field(default=False, init=False)
    """Set during initialization if this is a new workspace."""

    def __post_init__(self):
        """Validate configuration."""
        if self.type == WorkspaceType.APP and self.app_config is None:
            self.app_config = AppWorkspaceConfig()

        if self.type == WorkspaceType.REPO and self.repo_config is None:
            raise ValueError("repo_config is required for REPO workspace type")
