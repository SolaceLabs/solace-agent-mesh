"""
Config API router for feature flag inspection.

Provides a read-only view of every registered feature flag and its current
evaluated state. Flags can only be toggled via the SAM_FEATURE_<KEY>
environment variable; there are no write endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from openfeature import api as openfeature_api

from ....common.features.core import get_registry, has_env_override
from .dto.responses.feature_flag_responses import FeatureFlagResponse

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/config/features", response_model=list[FeatureFlagResponse])
async def get_feature_flags() -> list[FeatureFlagResponse]:
    """
    Return the evaluated state of every registered feature flag.

    Each entry includes the resolved on/off value, whether an environment
    variable override is active, and the registry-declared default.
    """
    log_prefix = "[GET /api/v1/config/features] "
    log.debug("%sRequest received.", log_prefix)

    try:
        client = openfeature_api.get_client()
        result = [
            FeatureFlagResponse(
                key=defn.key,
                name=defn.name,
                release_phase=defn.release_phase.value,
                resolved=client.get_boolean_value(defn.key, False),
                has_env_override=has_env_override(defn.key),
                registry_default=defn.default,
                description=defn.description,
            )
            for defn in get_registry().all()
        ]
        log.debug("%sReturning %d flag(s).", log_prefix, len(result))
        return result
    except Exception as e:
        log.exception("%sError retrieving feature flags.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feature flags",
        ) from e
