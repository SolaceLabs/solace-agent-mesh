"""
Utility functions for A2A protocol operations.
"""

from typing import Dict, Any, Optional
import logging

from a2a.types import AgentCard

log = logging.getLogger(__name__)


def is_gateway_card(agent_card: AgentCard) -> bool:
    """
    Check if an AgentCard represents a gateway.

    Gateways are identified by the presence of the gateway-role extension:
    https://solace.com/a2a/extensions/sam/gateway-role

    Args:
        agent_card: The AgentCard to check

    Returns:
        True if this is a gateway card, False otherwise (agent card)
    """
    if not agent_card:
        return False

    if not agent_card.capabilities:
        return False

    # Handle both dict and AgentCapabilities object
    if isinstance(agent_card.capabilities, dict):
        extensions = agent_card.capabilities.get("extensions")
    else:
        extensions = agent_card.capabilities.extensions

    if not extensions:
        return False

    for ext in extensions:
        ext_uri = ext.uri if hasattr(ext, 'uri') else ext.get('uri')
        if ext_uri == "https://solace.com/a2a/extensions/sam/gateway-role":
            return True

    return False


def extract_gateway_info(agent_card: AgentCard) -> Optional[Dict[str, Any]]:
    """
    Extract gateway-specific information from AgentCard extensions.

    Extracts information from:
    - gateway-role extension: gateway_id, gateway_type, namespace
    - deployment extension: deployment_id (optional)

    Args:
        agent_card: The AgentCard to extract info from

    Returns:
        Dict with gateway_id, gateway_type, namespace, and optionally deployment_id
        Returns None if not a gateway card
    """
    if not is_gateway_card(agent_card):
        return None

    info = {}

    # Handle both dict and AgentCapabilities object
    if isinstance(agent_card.capabilities, dict):
        extensions = agent_card.capabilities.get("extensions", [])
    else:
        extensions = agent_card.capabilities.extensions or []

    for ext in extensions:
        # Handle both dict and AgentExtension object
        ext_uri = ext.uri if hasattr(ext, 'uri') else ext.get('uri')
        ext_params = ext.params if hasattr(ext, 'params') else ext.get('params', {})

        if ext_uri == "https://solace.com/a2a/extensions/sam/gateway-role":
            info.update({
                "gateway_id": ext_params.get("gateway_id"),
                "gateway_type": ext_params.get("gateway_type"),
                "namespace": ext_params.get("namespace"),
            })
        elif ext_uri == "https://solace.com/a2a/extensions/sam/deployment":
            info["deployment_id"] = ext_params.get("deployment_id")

    return info
