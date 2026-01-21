"""
Platform Service health check router.

Provides health status endpoint for monitoring and load balancer health checks.
"""

import logging
from fastapi import APIRouter

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    """
    Platform Service health check endpoint.

    This endpoint is used by:
    - Kubernetes liveness/readiness probes
    - Load balancer health checks (ALB, NGINX)
    - External monitoring systems

    Returns:
        dict: Health status with service name.
            - status (str): "healthy" if service is operational
            - service (str): Service identifier
    """
    log.debug("Health check endpoint '/api/v1/platform/health' called")
    return {"status": "healthy", "service": "Platform Service"}
