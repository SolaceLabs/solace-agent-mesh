"""
API Router for gateway discovery and health monitoring.
Provides endpoints to query discovered gateways and their health status.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Path
from typing import Any, Dict, List, Optional

from ....common.gateway_registry import GatewayRegistry
from a2a.types import AgentCard
from ..dependencies import get_gateway_registry, get_user_config

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/gatewayCards", response_model=List[AgentCard])
async def get_discovered_gateway_cards(
    gateway_registry: GatewayRegistry = Depends(get_gateway_registry),
    user_config: Dict[str, Any] = Depends(get_user_config),
):
    """
    Retrieves a list of discovered A2A gateways.

    Returns gateway discovery cards for all gateways publishing heartbeats
    to the discovery topic. This enables monitoring of the gateway fleet.

    Returns:
        List of AgentCard objects representing discovered gateways
    """
    log_prefix = "[GET /api/v1/gatewayCards] "
    log.info("%sRequest received.", log_prefix)
    try:
        gateway_ids = gateway_registry.get_gateway_ids()
        all_gateways = [
            gateway_registry.get_gateway(gid)
            for gid in gateway_ids
            if gateway_registry.get_gateway(gid)
        ]

        log.debug(
            "%sReturning %d discovered gateways.",
            log_prefix,
            len(all_gateways),
        )
        return all_gateways
    except Exception as e:
        log.exception("%sError retrieving discovered gateway cards: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving gateway list.",
        )


@router.get("/gateways/health")
async def get_all_gateways_health(
    gateway_registry: GatewayRegistry = Depends(get_gateway_registry),
    ttl_seconds: int = 90,
):
    """
    Get health status for all discovered gateways.

    Args:
        ttl_seconds: Time-to-live threshold in seconds (default: 90)

    Returns:
        Dict with lists of healthy and unhealthy gateway IDs
    """
    log_prefix = "[GET /api/v1/gateways/health] "
    log.info("%sRequest received (TTL: %ds).", log_prefix, ttl_seconds)

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

        log.debug(
            "%sReturning health for %d gateways (healthy: %d, unhealthy: %d).",
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
            detail="Internal server error retrieving gateway health.",
        )


@router.get("/gateways/{gateway_id}/health")
async def get_gateway_health(
    gateway_id: str = Path(..., description="The gateway ID to check"),
    gateway_registry: GatewayRegistry = Depends(get_gateway_registry),
    ttl_seconds: int = 90,
):
    """
    Get health status for a specific gateway.

    Args:
        gateway_id: The gateway ID to check
        ttl_seconds: Time-to-live threshold in seconds (default: 90)

    Returns:
        Health status information for the gateway
    """
    log_prefix = f"[GET /api/v1/gateways/{gateway_id}/health] "
    log.info("%sRequest received.", log_prefix)

    try:
        gateway_card = gateway_registry.get_gateway(gateway_id)
        if not gateway_card:
            log.warning("%sGateway not found: %s", log_prefix, gateway_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Gateway '{gateway_id}' not found in registry.",
            )

        is_expired, seconds_since = gateway_registry.check_ttl_expired(gateway_id, ttl_seconds)
        last_seen = gateway_registry.get_last_seen(gateway_id)
        gateway_type = gateway_registry.get_gateway_type(gateway_id)
        namespace = gateway_registry.get_gateway_namespace(gateway_id)
        deployment_id = gateway_registry.get_deployment_id(gateway_id)

        health_status = "unhealthy" if is_expired else "healthy"

        log.debug(
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
            detail="Internal server error retrieving gateway health.",
        )
