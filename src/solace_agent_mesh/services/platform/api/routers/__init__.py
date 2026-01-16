"""
Community platform routers for Platform Service.

Provides foundational platform service endpoints available to all deployments.
"""


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

    Returns:
        Community platform routers list.
    """
    from .health_router import router as health_router

    return [
        {
            "router": health_router,
            "tags": ["Health"],
        },
    ]
