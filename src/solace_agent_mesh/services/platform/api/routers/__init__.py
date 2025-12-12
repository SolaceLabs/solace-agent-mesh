"""
Community platform routers for Platform Service.

Currently empty - no community endpoints yet.
"""


def get_community_platform_routers() -> list:
    """
    Return list of community platform routers.

    [
        {
            "router": router_instance,
            "prefix": "/api/v1/platform",
            "tags": ["Platform"]
        },
        ...
    ]

    Returns:
        Community platform routers list.
    """
    return []
