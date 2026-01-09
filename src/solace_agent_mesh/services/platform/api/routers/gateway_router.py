"""
Platform Service gateway discovery router.

Provides endpoint for listing discovered gateways.
Matches the pattern of /agentCards endpoint for consistency.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from a2a.types import AgentCard
from solace_agent_mesh.common.gateway_registry import GatewayRegistry
from solace_agent_mesh.shared.auth.dependencies import ValidatedUserConfig
from ..dependencies import get_gateway_registry

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/gatewayCards", response_model=List[AgentCard], tags=["Gateways"])
async def get_discovered_gateway_cards(
    gateway_registry: GatewayRegistry = Depends(get_gateway_registry),
    user_config: dict = Depends(ValidatedUserConfig(["sam:gateways:read"])),
):
    """
    Retrieves a list of discovered gateways.

    Returns gateway discovery cards for all gateways publishing heartbeats
    to the discovery topic. Used for monitoring gateway deployment status.

    Requires scope: sam:gateways:read

    Returns:
        List of AgentCard objects representing discovered gateways.
    """
    log_prefix = "[GET /api/v1/platform/gatewayCards] "
    user_id = user_config.get("user_profile", {}).get("id")
    log.info("%sRequest received from user '%s'", log_prefix, user_id)

    if not gateway_registry:
        log.error("%sGatewayRegistry not available", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway registry not initialized"
        )

    try:
        gateway_ids = gateway_registry.get_gateway_ids()
        gateways = [
            gateway_registry.get_gateway(gid)
            for gid in gateway_ids
            if gateway_registry.get_gateway(gid)
        ]

        log.info("%sReturning %d discovered gateways", log_prefix, len(gateways))
        return gateways

    except Exception as e:
        log.exception("%sError retrieving gateways: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving gateway list"
        )
