"""
FeatureChecker: two-tier feature flag evaluation.

Evaluation priority (highest to lowest):
  1. Environment variable  SAM_FEATURE_<UPPER_KEY>=true|false
  2. Registry default      FeatureDefinition.default_enabled
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .registry import FeatureRegistry

logger = logging.getLogger(__name__)

# Prefix for environment variable overrides (e.g., SAM_FEATURE_MY_FLAG=true)
_FLAG_PREFIX = "SAM_FEATURE_"


class FeatureChecker:
    """
    Evaluates feature flags according to the two-tier priority chain.

    Parameters
    ----------
    registry:
        The FeatureRegistry holding all known FeatureDefinition objects.
    """

    def __init__(self, registry: "FeatureRegistry") -> None:
        self._registry = registry

    def is_known_flag(self, key: str) -> bool:
        """Return True if key is registered in the registry."""
        return self._registry.get(key) is not None

    def is_enabled(self, key: str) -> bool:
        """
        Return True if the feature identified by key is currently enabled.

        Unknown keys always return False with a warning log.
        """
        definition = self._registry.get(key)
        if definition is None:
            logger.warning("is_enabled() called for unknown feature key '%s'", key)
            return False

        env_value = self._check_env_var(key)
        if env_value is not None:
            logger.debug("Feature '%s' resolved from env var: %s", key, env_value)
            return env_value

        logger.debug(
            "Feature '%s' resolved from registry default: %s",
            key,
            definition.default_enabled,
        )
        return definition.default_enabled

    def all_flags(self) -> dict[str, bool]:
        """Return {key: is_enabled(key)} for every registered feature."""
        return {defn.key: self.is_enabled(defn.key) for defn in self._registry.all()}

    @property
    def registry(self) -> "FeatureRegistry":
        """Return the underlying FeatureRegistry."""
        return self._registry

    def has_env_override(self, key: str) -> bool:
        """Return True if a SAM_FEATURE_<KEY> env var is set for key."""
        return self._check_env_var(key) is not None

    def load_from_yaml(self, yaml_path) -> None:
        """Load additional flag definitions from a YAML file into the registry."""
        self._registry.load_from_yaml(yaml_path)

    @staticmethod
    def _check_env_var(key: str) -> Optional[bool]:
        """
        Look up SAM_FEATURE_<UPPER_KEY> in the environment.

        Returns None when the variable is absent so callers can fall through.
        Recognised truthy values: 1, true (case-insensitive).
        Everything else is treated as false.
        """
        env_key = _FLAG_PREFIX + key.upper().replace("-", "_")
        raw = os.environ.get(env_key)
        if raw is None:
            return None
        return raw.strip().lower() in {"1", "true"}
