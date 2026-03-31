"""
Community platform routers for Platform Service.

Provides foundational platform service endpoints available to all deployments.
"""

import logging

log = logging.getLogger(__name__)


def get_community_platform_routers() -> list:
    """
    Return list of community platform routers.

    Format:
    [
        {
            "router": router_instance,
            "tags": ["Platform"]
        },
        ...
    ]

    Note: The prefix "/api/v1/platform" is applied by main.py when mounting these routers.
    All routers are always mounted. Feature flags are checked internally in endpoints
    and return 501 Not Implemented if the feature is disabled.

    Returns:
        Community platform routers list.
    """
    from .health_router import router as health_router
    from .model_configurations_router import router as model_configurations_router

    routers = [
        {
            "router": health_router,
            "tags": ["Health"],
        },
        {
            "router": model_configurations_router,
            "tags": ["Models"],
        },
    ]

    return routers
