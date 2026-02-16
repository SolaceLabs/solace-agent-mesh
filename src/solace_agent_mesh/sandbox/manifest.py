"""
Tool Manifest for Sandbox Worker.

This module provides the ToolManifest class which loads and caches
tool definitions from a YAML manifest file. It supports:
- Auto-reload when the manifest file changes (mtime-based)
- Optional package installation via uv/pip
- Runtime extensibility for future non-Python tools
"""

import importlib
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

log = logging.getLogger(__name__)


@dataclass
class ManifestEntry:
    """A single tool's manifest entry."""

    tool_name: str
    runtime: str = "python"
    module: Optional[str] = None
    function: Optional[str] = None
    class_name: Optional[str] = None
    package: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    timeout_seconds: Optional[int] = None
    sandbox_profile: Optional[str] = None


class ToolManifest:
    """
    Loads and caches tool manifest from a YAML file.

    The manifest file declares what tools are available in this sandbox worker
    and how to execute them. It supports auto-reload when the file changes
    (checked via mtime on each access).

    Manifest format:
        version: 1
        tools:
          tool_name:
            runtime: python
            module: my_module
            function: my_function
            package: my-pip-package      # optional
            version: ">=1.0"             # optional
            description: "..."           # optional
            timeout_seconds: 300         # optional override
            sandbox_profile: standard    # optional override
    """

    def __init__(self, manifest_path: str):
        self._path = manifest_path
        self._entries: Dict[str, ManifestEntry] = {}
        self._last_mtime: float = 0.0
        self._load()

    def _load(self) -> None:
        """Load the manifest from disk."""
        path = Path(self._path)
        if not path.exists():
            log.warning("Manifest file not found: %s", self._path)
            self._entries = {}
            return

        try:
            self._last_mtime = path.stat().st_mtime
            raw = yaml.safe_load(path.read_text())

            if not isinstance(raw, dict):
                log.error("Invalid manifest format (expected dict): %s", self._path)
                self._entries = {}
                return

            version = raw.get("version", 1)
            if version != 1:
                log.warning(
                    "Unknown manifest version %s in %s, attempting to parse anyway",
                    version,
                    self._path,
                )

            tools_dict = raw.get("tools", {})
            if not isinstance(tools_dict, dict):
                log.error("Invalid 'tools' section in manifest (expected dict)")
                self._entries = {}
                return

            entries: Dict[str, ManifestEntry] = {}
            for tool_name, tool_def in tools_dict.items():
                if not isinstance(tool_def, dict):
                    log.warning("Skipping invalid tool entry: %s", tool_name)
                    continue

                entry = ManifestEntry(
                    tool_name=tool_name,
                    runtime=tool_def.get("runtime", "python"),
                    module=tool_def.get("module"),
                    function=tool_def.get("function"),
                    class_name=tool_def.get("class_name"),
                    package=tool_def.get("package"),
                    version=tool_def.get("version"),
                    description=tool_def.get("description"),
                    timeout_seconds=tool_def.get("timeout_seconds"),
                    sandbox_profile=tool_def.get("sandbox_profile"),
                )

                # Validate python tools have module and either function or class_name
                if entry.runtime == "python":
                    if not entry.module or (not entry.function and not entry.class_name):
                        log.error(
                            "Python tool '%s' missing required 'module' or "
                            "'function'/'class_name'",
                            tool_name,
                        )
                        continue

                entries[tool_name] = entry

            self._entries = entries
            log.info(
                "Loaded manifest from %s: %d tools (%s)",
                self._path,
                len(entries),
                ", ".join(entries.keys()),
            )

        except yaml.YAMLError as e:
            log.error("Failed to parse manifest YAML %s: %s", self._path, e)
            self._entries = {}
        except Exception as e:
            log.error("Failed to load manifest %s: %s", self._path, e)
            self._entries = {}

    def _maybe_reload(self) -> None:
        """Check mtime and reload if the file has changed."""
        try:
            path = Path(self._path)
            if not path.exists():
                if self._entries:
                    log.warning("Manifest file removed: %s", self._path)
                    self._entries = {}
                    self._last_mtime = 0.0
                return

            current_mtime = path.stat().st_mtime
            if current_mtime != self._last_mtime:
                log.info("Manifest file changed, reloading: %s", self._path)
                self._load()
        except Exception as e:
            log.warning("Error checking manifest mtime: %s", e)

    def get_tool(self, tool_name: str) -> Optional[ManifestEntry]:
        """Get a tool entry by name. Checks for file changes first."""
        self._maybe_reload()
        return self._entries.get(tool_name)

    def list_tools(self) -> List[ManifestEntry]:
        """List all tool entries. Checks for file changes first."""
        self._maybe_reload()
        return list(self._entries.values())

    def get_tool_names(self) -> Set[str]:
        """Get the set of all tool names. Checks for file changes first."""
        self._maybe_reload()
        return set(self._entries.keys())

    def has_changed(self) -> bool:
        """Check if the manifest file has been modified since last load."""
        try:
            path = Path(self._path)
            if not path.exists():
                return bool(self._entries)
            return path.stat().st_mtime != self._last_mtime
        except Exception:
            return False

    def ensure_packages_installed(self) -> None:
        """Install any missing packages declared in the manifest."""
        for entry in self._entries.values():
            if entry.package:
                if not self._is_package_installed(entry.package):
                    self._install_package(entry.package, entry.version)

    def _is_package_installed(self, package: str) -> bool:
        """Check if a package is importable."""
        module_name = package.replace("-", "_")
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False

    def _install_package(
        self, package: str, version: Optional[str] = None
    ) -> None:
        """Install a package using uv pip install (falls back to pip)."""
        spec = package
        if version:
            spec = f"{package}{version}"

        log.info("Installing package: %s", spec)

        # Try uv first, fall back to pip
        for installer in [["uv", "pip", "install"], ["pip", "install"]]:
            try:
                result = subprocess.run(
                    [*installer, spec],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    log.info("Successfully installed package: %s", spec)
                    return
                else:
                    log.warning(
                        "Package install failed with %s: %s",
                        installer[0],
                        result.stderr[:500],
                    )
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                log.error("Package install timed out: %s", spec)
                return

        log.error("Failed to install package %s (no installer available)", spec)
