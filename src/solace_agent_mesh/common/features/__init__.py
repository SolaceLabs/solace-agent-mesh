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

__all__ = [
    "FeatureChecker",
    "FeatureDefinition",
    "FeatureRegistry",
    "ReleasePhase",
    "SamFeatureProvider",
]
