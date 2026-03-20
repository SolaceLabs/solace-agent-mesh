"""
FastAPI dependency helpers for feature flag gating.

These helpers wrap the OpenFeature client for use as FastAPI ``Depends``
injectors. They are framework-specific and live here rather than in
``core.py`` to keep the core module framework-agnostic.

Usage::

    from solace_agent_mesh.common.features.fastapi import (
        require_feature,
        get_feature_value,
    )

    # Hard-gate an entire endpoint — returns 404 when flag is off:
    @router.get("/my-endpoint")
    async def my_endpoint(_: None = Depends(require_feature("my_flag"))):
        ...

    # Inject the flag value for soft behaviour changes:
    @router.get("/my-endpoint")
    async def my_endpoint(flag: bool = Depends(get_feature_value("my_flag"))):
        if flag:
            ...
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, status
from openfeature import api as openfeature_api


def require_feature(key: str) -> Callable:
    """
    FastAPI dependency factory that hard-gates an endpoint on a feature flag.

    Raises HTTP 404 when the flag is disabled so that the endpoint appears
    non-existent to callers. Use when the entire endpoint should be
    unavailable while the flag is off.

    For soft behaviour changes based on a flag, use :func:`get_feature_value`.
    """
    def _check() -> None:
        if not openfeature_api.get_client().get_boolean_value(key, False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature '{key}' is not enabled.",
            )
    return _check


def get_feature_value(key: str) -> Callable:
    """
    FastAPI dependency factory that injects the current boolean value of a
    feature flag into an endpoint without raising on disabled.

    Use when the endpoint should remain accessible but needs to vary its
    behaviour based on whether the flag is on or off.
    """
    def _resolve() -> bool:
        return openfeature_api.get_client().get_boolean_value(key, False)
    return _resolve
