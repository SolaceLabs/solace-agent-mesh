"""
Workspace Context Injector Callback

Automatically injects content from workspace files into the system instruction
before each LLM call. This ensures agents always have the latest context from
workspace documentation files without requiring explicit file reads.

Use Cases:
- App Agent: Inject APP_CONTEXT.md for application state awareness
- Project-based agents: Inject ARCHITECTURE.md, TODO.md, etc.
- Any agent that needs workspace-specific context
"""

import logging
from pathlib import Path
from typing import Any, Optional

from google.adk.models.llm_request import LlmRequest

log = logging.getLogger(__name__)


class WorkspaceContextInjector:
    """
    Injects content from workspace files into system instruction before LLM calls.

    Configuration example in YAML:
    ```yaml
    callbacks:
      - type: workspace_context_injector
        workspace_base: "${HOME}/.claude-workspaces"
        files:
          - path: "APP_CONTEXT.md"
            header: "## Current Application State (Auto-Updated)"
            required: false
            max_size: 50000  # Optional: max chars to inject
          - path: "ARCHITECTURE.md"
            header: "## Architecture Documentation"
            required: false
    ```

    How it works:
    1. On each LLM request, checks if app_id exists in a2a_context
    2. If yes, reads specified files from workspace path
    3. Injects file content into system instruction with headers
    4. Files are re-read on each call, ensuring latest version is always used

    Benefits:
    - Always provides latest workspace context
    - More efficient than LLM file reads (single injection vs multiple tool calls)
    - Works across multiple sessions (each session gets current state)
    - Generic: works for any agent with workspace-based context
    """

    def __init__(self, config: dict):
        """
        Initialize the workspace context injector.

        Args:
            config: Configuration dict with:
                - workspace_base: Base path for workspaces (default: ~/.claude-workspaces)
                - files: List of files to inject, each with:
                    - path: Relative path within workspace
                    - header: Header to prepend to content
                    - required: Whether to warn if file missing (default: False)
                    - max_size: Max characters to inject (default: None/unlimited)
        """
        super().__init__()
        self.files = config.get("files", [])
        self.workspace_base = Path(config.get("workspace_base", "~/.claude-workspaces")).expanduser()
        log.info(f"[WorkspaceContextInjector] Initialized with {len(self.files)} file(s), base: {self.workspace_base}")

    def _get_workspace_path(self, a2a_context: dict) -> Optional[Path]:
        """
        Determine workspace path from a2a_context.

        Args:
            a2a_context: A2A context dict containing app_id and user_id

        Returns:
            Path to workspace, or None if not in app mode
        """
        app_id = a2a_context.get("app_id")
        user_id = a2a_context.get("user_id")

        if not app_id:
            log.debug("[WorkspaceContextInjector] No app_id in context, skipping injection")
            return None

        if not user_id:
            log.warning("[WorkspaceContextInjector] app_id present but no user_id, cannot determine workspace path")
            return None

        # Construct workspace path: {base}/{user_id}/apps/{app_id}
        workspace_path = self.workspace_base / user_id / "apps" / app_id
        return workspace_path

    def _read_file_content(self, file_path: Path, max_size: Optional[int] = None) -> Optional[str]:
        """
        Read file content with optional size limit.

        Args:
            file_path: Path to file
            max_size: Maximum characters to read (None = unlimited)

        Returns:
            File content or None if read failed
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Truncate if too large
            if max_size and len(content) > max_size:
                log.warning(
                    f"[WorkspaceContextInjector] File {file_path.name} is {len(content)} chars, "
                    f"truncating to {max_size}"
                )
                content = content[:max_size] + f"\n\n[... truncated, total size: {len(content)} chars]"

            return content

        except Exception as e:
            log.error(f"[WorkspaceContextInjector] Failed to read {file_path}: {e}")
            return None

    def _inject_files(self, workspace_path: Path) -> list[str]:
        """
        Read and prepare content blocks from configured files.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            List of formatted content blocks to inject
        """
        injected_blocks = []

        for file_config in self.files:
            file_rel_path = file_config["path"]
            file_path = workspace_path / file_rel_path

            # Check if file exists
            if not file_path.exists():
                if file_config.get("required", False):
                    log.warning(f"[WorkspaceContextInjector] Required file not found: {file_path}")
                else:
                    log.debug(f"[WorkspaceContextInjector] Optional file not found: {file_path}")
                continue

            # Read file content
            max_size = file_config.get("max_size")
            content = self._read_file_content(file_path, max_size)

            if not content:
                continue  # Read failed, skip this file

            # Format block with header
            header = file_config.get("header", f"## {file_rel_path}")
            block = f"{header}\n\n{content}"
            injected_blocks.append(block)

            log.info(
                f"[WorkspaceContextInjector] Injected {file_rel_path} "
                f"({len(content)} chars) from {workspace_path.name}"
            )

        return injected_blocks

    def on_llm_request(self, request: LlmRequest, context: Any) -> None:
        """
        Callback invoked before each LLM request.

        Injects workspace file content into system instruction.

        Args:
            request: LLM request object (modified in-place)
            context: Invocation context containing a2a_context
        """
        # Get a2a_context from tool context state
        if not hasattr(context, "state"):
            log.debug("[WorkspaceContextInjector] Context has no state, skipping")
            return

        a2a_context = context.state.get("a2a_context", {})

        # Determine workspace path
        workspace_path = self._get_workspace_path(a2a_context)
        if not workspace_path:
            return  # Not in app mode or missing required info

        # Check if workspace exists
        if not workspace_path.exists():
            log.debug(f"[WorkspaceContextInjector] Workspace does not exist yet: {workspace_path}")
            return

        # Read and inject files
        injected_blocks = self._inject_files(workspace_path)

        if not injected_blocks:
            log.debug(f"[WorkspaceContextInjector] No files to inject for {workspace_path.name}")
            return

        # Inject into system instruction
        current_instruction = request.config.system_instruction or ""
        workspace_context = "\n\n---\n\n".join(injected_blocks)

        # Append workspace context to system instruction
        request.config.system_instruction = f"{current_instruction}\n\n---\n\n{workspace_context}"

        log.info(
            f"[WorkspaceContextInjector] Injected {len(injected_blocks)} file(s) "
            f"({len(workspace_context)} chars) into system instruction"
        )
