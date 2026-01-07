"""
Platform Service gateway monitoring router.

Provides endpoints for gateway discovery and health monitoring.
This is the control plane API for monitoring gateway fleet status.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Path
from typing import List

from a2a.types import AgentCard
from solace_agent_mesh.common.gateway_registry import GatewayRegistry
from ..dependencies import get_gateway_registry

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/gateways", response_model=List[AgentCard], tags=["Gateways"])
async def list_gateways(
    gateway_registry: GatewayRegistry = Depends(get_gateway_registry),
):
    """
    List all discovered gateways.

    Returns gateway discovery cards for all gateways publishing heartbeats
    to the discovery topic. Used for monitoring the gateway fleet.

    Returns:
        List of AgentCard objects representing discovered gateways.
    """
    log_prefix = "[GET /api/v1/platform/gateways] "
    log.info("%sRequest received", log_prefix)

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


@router.get("/gateways/health", tags=["Gateways"])
async def get_gateways_health(
    gateway_registry: GatewayRegistry = Depends(get_gateway_registry),
    ttl_seconds: int = 90,
):
    """
    Get health status for all discovered gateways.

    Platform monitoring endpoint for gateway fleet health. Returns health
    status based on heartbeat TTL threshold.

    Args:
        ttl_seconds: Time-to-live threshold in seconds (default: 90).
                     Gateways with heartbeats older than this are marked unhealthy.

    Returns:
        dict: Health status summary with gateway details
            - total_gateways (int): Total number of gateways
            - healthy_count (int): Count of healthy gateways
            - unhealthy_count (int): Count of unhealthy gateways
            - ttl_seconds (int): TTL threshold used
            - gateways (list): Detailed health info for each gateway
    """
    log_prefix = "[GET /api/v1/platform/gateways/health] "
    log.info("%sRequest received (TTL: %ds)", log_prefix, ttl_seconds)

    if not gateway_registry:
        log.error("%sGatewayRegistry not available", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway registry not initialized"
        )

    try:
        gateway_ids = gateway_registry.get_gateway_ids()
        health_info = []

        for gid in gateway_ids:
            is_expired, seconds_since = gateway_registry.check_ttl_expired(gid, ttl_seconds)
            last_seen = gateway_registry.get_last_seen(gid)
            gateway_type = gateway_registry.get_gateway_type(gid)
            namespace = gateway_registry.get_gateway_namespace(gid)
            deployment_id = gateway_registry.get_deployment_id(gid)

            health_info.append({
                "gateway_id": gid,
                "gateway_type": gateway_type,
                "namespace": namespace,
                "deployment_id": deployment_id,
                "health_status": "unhealthy" if is_expired else "healthy",
                "last_seen": last_seen,
                "seconds_since_last_seen": seconds_since,
            })

        healthy_count = sum(1 for g in health_info if g["health_status"] == "healthy")
        unhealthy_count = len(health_info) - healthy_count

        log.info(
            "%sReturning health for %d gateways (healthy: %d, unhealthy: %d)",
            log_prefix,
            len(health_info),
            healthy_count,
            unhealthy_count,
        )

        return {
            "total_gateways": len(health_info),
            "healthy_count": healthy_count,
            "unhealthy_count": unhealthy_count,
            "ttl_seconds": ttl_seconds,
            "gateways": health_info,
        }

    except Exception as e:
        log.exception("%sError retrieving gateway health: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving gateway health"
        )


@router.get("/gateways/{gateway_id}/health", tags=["Gateways"])
async def get_gateway_health(
    gateway_id: str = Path(..., description="The gateway ID to check"),
    gateway_registry: GatewayRegistry = Depends(get_gateway_registry),
    ttl_seconds: int = 90,
):
    """
    Get health status for a specific gateway.

    Platform monitoring endpoint for individual gateway health status.

    Args:
        gateway_id: The gateway ID to check.
        ttl_seconds: Time-to-live threshold in seconds (default: 90).

    Returns:
        dict: Gateway health details
            - gateway_id (str): Gateway identifier
            - gateway_type (str): Gateway type (http_sse, slack, rest, teams)
            - namespace (str): A2A namespace
            - deployment_id (str|None): Deployment identifier if available
            - health_status (str): "healthy" or "unhealthy"
            - last_seen (float): Unix timestamp of last heartbeat
            - seconds_since_last_seen (int): Seconds since last heartbeat
            - ttl_seconds (int): TTL threshold used

    Raises:
        HTTPException: 404 if gateway not found in registry.
    """
    log_prefix = f"[GET /api/v1/platform/gateways/{gateway_id}/health] "
    log.info("%sRequest received", log_prefix)

    if not gateway_registry:
        log.error("%sGatewayRegistry not available", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway registry not initialized"
        )

    try:
        gateway_card = gateway_registry.get_gateway(gateway_id)
        if not gateway_card:
            log.warning("%sGateway not found: %s", log_prefix, gateway_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Gateway '{gateway_id}' not found in registry"
            )

        is_expired, seconds_since = gateway_registry.check_ttl_expired(gateway_id, ttl_seconds)
        last_seen = gateway_registry.get_last_seen(gateway_id)
        gateway_type = gateway_registry.get_gateway_type(gateway_id)
        namespace = gateway_registry.get_gateway_namespace(gateway_id)
        deployment_id = gateway_registry.get_deployment_id(gateway_id)

        health_status = "unhealthy" if is_expired else "healthy"

        log.info(
            "%sGateway health: %s (last seen: %ds ago)",
            log_prefix,
            health_status,
            seconds_since,
        )

        return {
            "gateway_id": gateway_id,
            "gateway_type": gateway_type,
            "namespace": namespace,
            "deployment_id": deployment_id,
            "health_status": health_status,
            "last_seen": last_seen,
            "seconds_since_last_seen": seconds_since,
            "ttl_seconds": ttl_seconds,
        }

    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError retrieving gateway health: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving gateway health"
        )
