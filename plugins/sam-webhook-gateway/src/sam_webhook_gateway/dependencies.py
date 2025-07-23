"""
Defines FastAPI dependency injectors to access shared resources
managed by the WebhookGatewayComponent.
"""

from fastapi import HTTPException, status
from typing import TYPE_CHECKING

from solace_ai_connector.common.log import log

if TYPE_CHECKING:
    from .component import WebhookGatewayComponent

sac_component_instance: "WebhookGatewayComponent" = None


def set_component_instance(component: "WebhookGatewayComponent"):
    """Called by the WebhookGatewayComponent during its startup to provide its instance."""
    global sac_component_instance
    if sac_component_instance is None:
        sac_component_instance = component
        log.info(
            "[Webhook Dependencies] SAC Component instance (WebhookGatewayComponent) provided."
        )
    else:
        log.warning(
            "[Webhook Dependencies] SAC Component instance (WebhookGatewayComponent) already set."
        )


def get_sac_component() -> "WebhookGatewayComponent":
    """FastAPI dependency to get the WebhookGatewayComponent instance."""
    if sac_component_instance is None:
        log.critical(
            "[Webhook Dependencies] WebhookGatewayComponent instance accessed before it was set!"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook Gateway backend component not yet initialized.",
        )
    return sac_component_instance
