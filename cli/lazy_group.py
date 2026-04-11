"""
Lazy-loading Click group for deferring heavy imports until command invocation.

This module provides ``LazyGroup``, a drop-in replacement for ``click.Group``
that avoids importing subcommand modules at CLI startup.  Instead, each
subcommand is described by a lightweight ``(import_path, help_text)`` tuple;
the real module is only loaded when the user actually invokes (or requests
``--help`` for) that specific subcommand.


Usage
-----
::

    from solace_agent_mesh.cli.lazy_group import LazyGroup

    _COMMANDS = {
        "run":  ("cli.commands.run_cmd:run",   "Run the application."),
        "init": ("cli.commands.init_cmd:init", "Initialize a project."),
    }

    @click.group(cls=LazyGroup, lazy_commands=_COMMANDS)
    def cli():
        pass
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, Optional, Tuple

import click

log = logging.getLogger(__name__)


class LazyGroup(click.Group):
    """A :class:`click.Group` that defers subcommand imports until invocation.

    Parameters
    ----------
    lazy_commands:
        Mapping of ``{command_name: (import_path, short_help)}`` where
        *import_path* has the form ``"dotted.module:attribute"``.
    """

    def __init__(
        self,
        *args: Any,
        lazy_commands: Optional[Dict[str, Tuple[str, str]]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._lazy_commands: Dict[str, Tuple[str, str]] = lazy_commands or {}
        self._lazy_cache: Dict[str, click.BaseCommand] = {}

    # ------------------------------------------------------------------
    # click.Group interface
    # ------------------------------------------------------------------

    def list_commands(self, ctx: click.Context) -> list[str]:
        """Return sorted union of eager + lazy command names."""
        names = set(super().list_commands(ctx))
        names.update(self._lazy_commands)
        return sorted(names)

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.BaseCommand]:
        """Load a lazy command on first access; cache for subsequent calls."""
        # 1. Already resolved
        if cmd_name in self._lazy_cache:
            return self._lazy_cache[cmd_name]

        # 2. Known lazy command — import now
        if cmd_name in self._lazy_commands:
            import_path, _ = self._lazy_commands[cmd_name]
            cmd = self._resolve_import(cmd_name, import_path)
            if cmd is not None:
                self._lazy_cache[cmd_name] = cmd
            return cmd

        # 3. Fall back to eagerly registered commands
        return super().get_command(ctx, cmd_name)

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Render the command table using cached help text — no imports needed."""
        rows: list[tuple[str, str]] = []
        for name in self.list_commands(ctx):
            if name in self._lazy_commands:
                _, help_text = self._lazy_commands[name]
                rows.append((name, help_text))
            else:
                cmd = self.get_command(ctx, name)
                if cmd is None or getattr(cmd, "hidden", False):
                    continue
                rows.append((name, cmd.get_short_help_str(limit=150)))

        if rows:
            limit = formatter.width - 6 - max(len(r[0]) for r in rows)
            rows = [
                (name, text if len(text) <= limit else text[: limit - 3] + "...")
                for name, text in rows
            ]
            with formatter.section("Commands"):
                formatter.write_dl(rows)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_import(cmd_name: str, import_path: str) -> Optional[click.BaseCommand]:
        """Import *import_path* (``'module.path:attr'``) and return the Click command."""
        module_path, _, attr_name = import_path.rpartition(":")
        if not module_path or not attr_name:
            log.error("Invalid lazy import path for '%s': '%s'", cmd_name, import_path)
            return None
        try:
            mod = importlib.import_module(module_path)
            return getattr(mod, attr_name)
        except Exception:
            log.exception("Failed to load command '%s' from '%s'", cmd_name, import_path)
            return None
