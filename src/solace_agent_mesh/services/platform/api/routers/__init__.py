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
    The model_configurations router is only included if the model_config_ui feature flag is enabled.

    Returns:
        Community platform routers list.
    """
    from .health_router import router as health_router
    from openfeature import api as openfeature_api

    routers = [
        {
            "router": health_router,
            "tags": ["Health"],
        },
    ]

    # Conditionally include model configurations router based on feature flag
    if openfeature_api.get_client().get_boolean_value("model_config_ui", False):
        from .model_configurations_router import router as model_configurations_router

        routers.append({
            "router": model_configurations_router,
            "tags": ["Models"],
        })
        log.info("Model configurations router included (feature flag enabled)")
    else:
        log.info("Model configurations router excluded (feature flag disabled)")

    return routers
