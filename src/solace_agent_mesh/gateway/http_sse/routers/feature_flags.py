"""
Config API router for feature flag inspection.

Provides a read-only view of every registered feature flag and its current
evaluated state. Flags can only be toggled via the SAM_FEATURE_<KEY>
environment variable; there are no write endpoints.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status

from ....gateway.http_sse.dependencies import get_sac_component
from .dto.responses.feature_flag_responses import FeatureFlagResponse

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/config/features", response_model=list[FeatureFlagResponse])
async def get_feature_flags(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> list[FeatureFlagResponse]:
    """
    Return the evaluated state of every registered feature flag.

    Each entry includes the resolved on/off value, whether an environment
    variable override is active, and the registry-declared default.
    """
    log_prefix = "[GET /api/v1/config/features] "
    log.debug("%sRequest received.", log_prefix)

    try:
        checker = component.feature_checker
        result = [
            FeatureFlagResponse(
                key=defn.key,
                name=defn.name,
                release_phase=defn.release_phase.value,
                resolved=checker.is_enabled(defn.key),
                has_env_override=checker.has_env_override(defn.key),
                registry_default=defn.default_enabled,
                description=defn.description,
            )
            for defn in checker.registry.all()
        ]
        log.debug("%sReturning %d flag(s).", log_prefix, len(result))
        return result
    except Exception as e:
        log.exception("%sError retrieving feature flags: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feature flags",
        ) from e
