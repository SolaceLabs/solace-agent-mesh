"""
SAM feature flag framework — public API.

Usage example:
    from openfeature import api as openfeature_api

    if openfeature_api.get_client().get_boolean_value("my_flag", False):
        # feature enabled
"""

from .checker import FeatureChecker
from .provider import SamFeatureProvider
from .registry import FeatureDefinition, FeatureRegistry, ReleasePhase
from .core import (
    get_registry,
    has_env_override,
    initialize,
    is_known_flag,
    load_flags_from_yaml,
)

__all__ = [
    "FeatureChecker",
    "FeatureDefinition",
    "FeatureRegistry",
    "ReleasePhase",
    "SamFeatureProvider",
    "get_registry",
    "has_env_override",
    "initialize",
    "is_known_flag",
    "load_flags_from_yaml",
]
