"""
Community platform routers for Platform Service.

Phase 1: Empty - no community endpoints yet.
Future phases will add routers as needed.
"""


def get_community_platform_routers() -> list:
    """
    Return list of community platform routers.

    Phase 1: Returns empty list (no community endpoints).
    Future phases will return router configurations in the format:
    [
        {
            "router": router_instance,
            "prefix": "/api/v1/platform",
            "tags": ["Platform"]
        },
        ...
    ]

    Returns:
        Empty list for Phase 1.
    """
    return []
