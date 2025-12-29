"""
Workspace Context Injector Callback

Automatically injects content from workspace files into the conversation
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
from google.genai import types as adk_types

log = logging.getLogger(__name__)

# Marker to identify injected context messages in history
CONTEXT_MARKER = "[AUTO-INJECTED APP CONTEXT - Updated each turn]"


class WorkspaceContextInjector:
    """
    Injects content from workspace files into the conversation before LLM calls.

    Configuration example in YAML:
    ```yaml
    workspace_context_injection:
      workspace_base: "${HOME}/.claude-workspaces"
      files:
        - path: "APP_CONTEXT.md"
          header: "## Current Application State"
          required: false
          max_size: 50000  # Optional: max chars to inject
    ```

    How it works:
    1. On each LLM request, checks if app_id exists in a2a_context
    2. If yes, reads specified files from workspace path
    3. Injects as first message pair in conversation history
    4. On subsequent calls, updates the context message in place
    5. Files are re-read on each call, ensuring latest version is always used

    Benefits:
    - Context sent once per conversation, benefits from prompt caching
    - Always provides latest workspace context (updated in place each turn)
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
        log.info(
            f"[WorkspaceContextInjector] Initialized with {len(self.files)} file(s), "
            f"base: {self.workspace_base}"
        )

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

    def _build_context_blocks(self, workspace_path: Path) -> list[str]:
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

            log.debug(
                f"[WorkspaceContextInjector] Prepared {file_rel_path} "
                f"({len(content)} chars) from {workspace_path.name}"
            )

        return injected_blocks

    def _find_context_message_index(self, contents: list) -> Optional[int]:
        """
        Find the index of an existing injected context message.

        Args:
            contents: List of Content objects in the conversation

        Returns:
            Index of the context message, or None if not found
        """
        if not contents:
            return None

        for i, content in enumerate(contents):
            if content.role == "user" and content.parts:
                for part in content.parts:
                    if hasattr(part, "text") and part.text and CONTEXT_MARKER in part.text:
                        return i
        return None

    def _inject_into_history(self, request: LlmRequest, workspace_context: str) -> None:
        """
        Inject context into conversation history.

        Strategy:
        1. Check if we already have an injected context message (identified by marker)
        2. If yes, update it in place with latest content
        3. If no, insert new user/assistant message pair at the start

        Args:
            request: LLM request object (modified in-place)
            workspace_context: The context content to inject
        """
        if request.contents is None:
            request.contents = []

        # Format the context message with marker
        context_message = f"{CONTEXT_MARKER}\n\nThis is the current state of the application. It is automatically updated before each interaction.\n\n---\n\n{workspace_context}"

        # Check if we already have an injected context
        existing_idx = self._find_context_message_index(request.contents)

        if existing_idx is not None:
            # Update existing context message in place
            request.contents[existing_idx] = adk_types.Content(
                role="user",
                parts=[adk_types.Part(text=context_message)],
            )
            log.info(
                f"[WorkspaceContextInjector] Updated existing context at position {existing_idx} "
                f"({len(workspace_context)} chars)"
            )
        else:
            # Insert new context message pair at the start
            # User message with context
            context_user_content = adk_types.Content(
                role="user",
                parts=[adk_types.Part(text=context_message)],
            )

            # Brief assistant acknowledgment
            context_assistant_content = adk_types.Content(
                role="model",
                parts=[adk_types.Part(text="I've reviewed the current application state and am ready to help.")],
            )

            # Insert at the beginning (assistant response first since we insert at 0 twice)
            request.contents.insert(0, context_assistant_content)
            request.contents.insert(0, context_user_content)

            log.info(
                f"[WorkspaceContextInjector] Inserted context message pair at start of history "
                f"({len(workspace_context)} chars)"
            )

    def on_llm_request(self, request: LlmRequest, context: Any) -> None:
        """
        Callback invoked before each LLM request.

        Injects workspace file content at the start of conversation history.

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

        # Read and prepare context blocks
        context_blocks = self._build_context_blocks(workspace_path)

        if not context_blocks:
            log.debug(f"[WorkspaceContextInjector] No files to inject for {workspace_path.name}")
            return

        # Combine blocks and inject into history
        workspace_context = "\n\n---\n\n".join(context_blocks)
        self._inject_into_history(request, workspace_context)
