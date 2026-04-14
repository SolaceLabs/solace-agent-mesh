"""
SAM feature flag initialisation and introspection utilities.

The OpenFeature client is the single source of truth for flag *evaluation*.
This module handles two concerns that OpenFeature does not cover:

1. Initialisation — loading ``features.yaml``, wiring the registry/checker,
   and registering ``SamFeatureProvider`` with OpenFeature.  Done once,
   lazily, in a thread-safe way.

2. Introspection — ``is_known_flag()``, ``has_env_override()``, and
   ``get_registry()`` expose internal registry state that OpenFeature has
   no equivalent for (used by the admin API endpoint).

For flag *evaluation* everywhere else, use the OpenFeature client directly:

    from openfeature import api as openfeature_api

    if openfeature_api.get_client().get_boolean_value("my_feature", False):
        ...
"""

from __future__ import annotations

import logging
import threading
from importlib.resources import files as pkg_files
from typing import Optional

from openfeature import api as openfeature_api

from .checker import FeatureChecker
from .provider import SamFeatureProvider
from .registry import FeatureRegistry

logger = logging.getLogger(__name__)

_checker: Optional[FeatureChecker] = None
_initialized = False
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def initialize() -> None:
    """Load community ``features.yaml`` and register the OpenFeature provider.

    Idempotent and thread-safe — only the first call performs work.
    """
    if _initialized:
        return
    with _lock:
        if _initialized:
            return
        _do_initialize()


def _do_initialize() -> None:
    global _checker, _initialized
    registry = FeatureRegistry()
    features_yaml = str(
        pkg_files("solace_agent_mesh.common.features").joinpath("features.yaml")
    )
    registry.load_from_yaml(features_yaml)
    _checker = FeatureChecker(registry=registry)
    openfeature_api.set_provider(SamFeatureProvider(_checker))
    # Set True before enterprise loading to prevent recursion: enterprise calls
    # load_flags_from_yaml() → _ensure_initialized() → initialize().  The trade-off
    # is that a concurrent caller whose first _initialized check races between this
    # line and the end of enterprise loading may return slightly early, but the
    # registry is already usable for community flags at this point and the enterprise
    # load window is tiny.  Using a separate recursion guard would add complexity
    # without meaningful benefit given the narrow race window.
    _initialized = True
    logger.debug("Feature flags initialised with community features.yaml")
    try:
        from solace_agent_mesh_enterprise.init_enterprise import (  # pylint: disable=import-outside-toplevel
            _register_enterprise_feature_flags,
        )
        _register_enterprise_feature_flags()
        logger.debug("Enterprise feature flags loaded.")
    except ImportError:
        pass


def _ensure_initialized() -> None:
    if not _initialized:
        initialize()


def load_flags_from_yaml(path: str) -> None:
    """Merge additional flag definitions from a YAML file into the registry.

    Used by enterprise to register enterprise-specific flags after community
    flags are loaded.
    """
    _ensure_initialized()
    _checker.load_from_yaml(path)


# ---------------------------------------------------------------------------
# Introspection — not available through the OpenFeature client
# ---------------------------------------------------------------------------

def is_known_flag(key: str) -> bool:
    """Return True if *key* is registered in the feature registry."""
    _ensure_initialized()
    return _checker.is_known_flag(key)


def has_env_override(key: str) -> bool:
    """Return True if a ``SAM_FEATURE_<KEY>`` env var is set for *key*."""
    _ensure_initialized()
    return _checker.has_env_override(key)


def get_registry() -> FeatureRegistry:
    """Return the underlying ``FeatureRegistry``."""
    _ensure_initialized()
    return _checker.registry


# ---------------------------------------------------------------------------
# Test support
# ---------------------------------------------------------------------------

def _reset_for_testing() -> None:
    """Reset all module state for test isolation.

    Clears the checker, initialized flag, and the OpenFeature global provider
    so state never leaks between test files.
    """
    global _checker, _initialized
    with _lock:
        _checker = None
        _initialized = False
    openfeature_api.clear_providers()


def _initialize_for_testing(path: str) -> None:
    """Reset and initialize from a custom YAML path, for test use only.

    Used by test infrastructure that needs to substitute a test-only
    ``features.yaml`` instead of the bundled community one.
    """
    global _checker, _initialized
    with _lock:
        _checker = None
        _initialized = False
    openfeature_api.clear_providers()
    registry = FeatureRegistry()
    registry.load_from_yaml(path)
    _checker = FeatureChecker(registry=registry)
    openfeature_api.set_provider(SamFeatureProvider(_checker))
    _initialized = True

