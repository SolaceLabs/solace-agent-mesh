"""
Feature registry: definitions and loader for the SAM feature flag system.

Feature definitions live in a YAML file (features.yaml) that is loaded at startup.
The registry supports multiple YAML loads so that enterprise can merge additional
flag definitions without modifying community code. Later loads win on key conflicts,
allowing enterprise to override community defaults.

YAML schema (see features.yaml for annotated examples):

    features:
      - key:             <str>   # Required. Unique snake_case identifier used in code.
        name:            <str>   # Required. Human-readable label for admin UI.
        release_phase:   <str>   # Required. One of:
                                 #   early_access | beta | experimental | ga
        default_enabled: <bool>  # Required. Baseline on/off; env-var overrides this.
        jira_epic:       <str>   # Required. Jira epic key (e.g. DATAGO-118673).
        description:     <str>   # Optional. Brief explanation shown in admin UI.

Evaluation priority (highest wins):
  1. SAM_FEATURE_<UPPER_KEY> environment variable
  2. default_enabled
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class ReleasePhase(str, Enum):
    """Lifecycle release phase for a feature flag."""

    EARLY_ACCESS = "early_access"
    BETA = "beta"
    EXPERIMENTAL = "experimental"
    GA = "ga"


@dataclass
class FeatureDefinition:
    """Describes a single feature flag."""

    key: str
    name: str
    release_phase: ReleasePhase
    default_enabled: bool
    jira_epic: str
    description: str = ""


class FeatureRegistry:
    """
    In-memory store of FeatureDefinition objects.

    Load community flags via load_from_yaml(), then optionally call
    load_from_yaml() again with an enterprise YAML to merge additional
    definitions. Later loads win on key conflicts so enterprise can
    override community defaults.
    """

    def __init__(self) -> None:
        self._definitions: dict[str, FeatureDefinition] = {}

    def load_from_yaml(self, path: str | Path) -> None:
        """Parse a features YAML file and merge its definitions into the registry."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Features YAML not found: {path}")

        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

        features_list = data.get("features", [])
        if not isinstance(features_list, list):
            raise ValueError(f"'features' key in {path} must be a list")

        for raw in features_list:
            definition = self._parse_definition(raw, path)
            if definition.key in self._definitions:
                logger.debug(
                    "Feature '%s' redefined by %s — using new definition",
                    definition.key,
                    path,
                )
            self._definitions[definition.key] = definition

        logger.info(
            "Loaded %d feature definition(s) from %s", len(features_list), path
        )

    def register(self, definition: FeatureDefinition) -> None:
        """Register a single FeatureDefinition programmatically."""
        self._definitions[definition.key] = definition

    def get(self, key: str) -> Optional[FeatureDefinition]:
        """Return the FeatureDefinition for key, or None if not registered."""
        return self._definitions.get(key)

    def all(self) -> list[FeatureDefinition]:
        """Return all registered definitions in insertion order."""
        return list(self._definitions.values())

    def keys(self) -> list[str]:
        return list(self._definitions.keys())

    @staticmethod
    def _parse_definition(raw: dict, source: Path) -> FeatureDefinition:
        if not isinstance(raw, dict):
            raise ValueError(
                f"Each feature entry must be a mapping in {source}; got: {raw!r}"
            )

        required = ("key", "name", "release_phase", "default_enabled", "jira_epic")
        missing = [f for f in required if f not in raw]
        if missing:
            missing_str = ", ".join(missing)
            raise ValueError(
                f"Feature definition in {source} is missing required "
                f"field(s): {missing_str}. Entry: {raw!r}"
            )

        try:
            key = raw["key"]
            if not isinstance(key, str) or not key:
                raise ValueError(f"'key' must be a non-empty string; got: {key!r}")

            name = raw["name"]
            if not isinstance(name, str) or not name:
                raise ValueError(f"'name' must be a non-empty string; got: {name!r}")

            try:
                release_phase = ReleasePhase(raw["release_phase"])
            except ValueError as exc:
                valid = ", ".join(p.value for p in ReleasePhase)
                got = raw["release_phase"]
                raise ValueError(
                    f"'release_phase' must be one of [{valid}]; got: {got!r}"
                ) from exc

            default_enabled = raw["default_enabled"]
            if not isinstance(default_enabled, bool):
                raise ValueError(
                    f"'default_enabled' must be a boolean; got: {default_enabled!r}"
                )

            jira_epic = raw["jira_epic"]
            if not isinstance(jira_epic, str) or not jira_epic:
                raise ValueError(
                    f"'jira_epic' must be a non-empty string; got: {jira_epic!r}"
                )

            description = raw.get("description", "")
            if not isinstance(description, str):
                raise ValueError(
                    f"'description' must be a string; got: {description!r}"
                )

            return FeatureDefinition(
                key=key,
                name=name,
                release_phase=release_phase,
                default_enabled=default_enabled,
                jira_epic=jira_epic,
                description=description,
            )
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(
                f"Invalid feature definition in {source}: {raw!r}"
            ) from exc
