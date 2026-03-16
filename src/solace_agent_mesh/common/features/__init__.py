"""
SAM feature flag framework — public API.

Usage example:
    from openfeature import api as openfeature_api

    if openfeature_api.get_client().get_boolean_value("my_flag", False):
        # feature enabled
"""

import logging
from importlib.resources import files as pkg_files

from .checker import FeatureChecker
from .provider import SamFeatureProvider
from .registry import FeatureDefinition, FeatureRegistry, ReleasePhase

__all__ = [
    "FeatureChecker",
    "FeatureDefinition",
    "FeatureRegistry",
    "ReleasePhase",
    "SamFeatureProvider",
    "init_features",
]

_logger = logging.getLogger(__name__)
_feature_checker: FeatureChecker | None = None


def init_features(log_identifier: str = "") -> FeatureChecker:
    """
    Initialize the feature flag system globally.

    Loads feature definitions from the community features.yaml, creates the
    FeatureChecker, and registers it with OpenFeature. Enterprise flags are
    automatically merged if the enterprise package is available.

    This function is idempotent — it only initializes once, even if called
    multiple times. Subsequent calls return the already-initialized FeatureChecker.

    Args:
        log_identifier: Optional log identifier for debug logging (e.g., component name)

    Returns:
        The initialized FeatureChecker instance
    """
    global _feature_checker
    from openfeature import api as openfeature_api

    # Return existing instance if already initialized
    if _feature_checker is not None:
        _logger.debug(
            "%s Feature flags already initialized, returning existing instance.",
            log_identifier,
        )
        return _feature_checker

    registry = FeatureRegistry()

    features_yaml = str(
        pkg_files("solace_agent_mesh.common.features").joinpath("features.yaml")
    )
    registry.load_from_yaml(features_yaml)

    _feature_checker = FeatureChecker(registry=registry)

    openfeature_api.set_provider(SamFeatureProvider(_feature_checker))

    try:
        from solace_agent_mesh_enterprise.init_enterprise import (
            _register_enterprise_feature_flags,
        )
        _register_enterprise_feature_flags()
        _logger.debug(
            "%s Enterprise feature flags registered.",
            log_identifier,
        )
    except ImportError:
        _logger.debug("%s Enterprise feature flags not available.", log_identifier)

    _logger.info(
        "%s Feature flags initialized (%d flags).",
        log_identifier,
        len(registry.keys()),
    )

    return _feature_checker
