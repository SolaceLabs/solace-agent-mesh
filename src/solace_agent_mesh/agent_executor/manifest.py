"""Agent manifest — reads and watches the JSON manifest synced from S3."""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Optional

log = logging.getLogger(__name__)


@dataclass
class AgentEntry:
    agent_id: str
    desired_state: str
    config_yaml: str
    values: Dict[str, str] = field(default_factory=dict)
    checksum: str = ""
    deployment_id: str = ""


class AgentManifest:
    """Loads and watches a manifest.json file for agent definitions.

    Uses mtime-based change detection, same pattern as sandbox ToolManifest.
    """

    def __init__(self, manifest_path: str):
        self._path = manifest_path
        self._entries: Dict[str, AgentEntry] = {}
        self._last_mtime: float = 0.0
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            log.warning("Manifest not found at %s — starting with empty manifest", self._path)
            self._entries = {}
            return

        try:
            mtime = os.path.getmtime(self._path)
            with open(self._path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.error("Failed to read manifest %s: %s", self._path, e)
            return

        self._last_mtime = mtime
        agents = data.get("agents", {})
        self._entries = {}
        for agent_id, entry_data in agents.items():
            self._entries[agent_id] = AgentEntry(
                agent_id=agent_id,
                desired_state=entry_data.get("desired_state", "stopped"),
                config_yaml=entry_data.get("config_yaml", ""),
                values=entry_data.get("values", {}),
                checksum=entry_data.get("checksum", ""),
                deployment_id=entry_data.get("deployment_id", ""),
            )
        log.info("Loaded manifest with %d agent(s)", len(self._entries))

    def has_changed(self) -> bool:
        if not os.path.exists(self._path):
            return False
        try:
            return os.path.getmtime(self._path) > self._last_mtime
        except OSError:
            return False

    def reload_if_changed(self) -> bool:
        if self.has_changed():
            self._load()
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[AgentEntry]:
        return self._entries.get(agent_id)

    def get_all_agents(self) -> Dict[str, AgentEntry]:
        return dict(self._entries)

    def get_desired_running(self) -> Dict[str, AgentEntry]:
        return {
            aid: entry
            for aid, entry in self._entries.items()
            if entry.desired_state == "running"
        }
