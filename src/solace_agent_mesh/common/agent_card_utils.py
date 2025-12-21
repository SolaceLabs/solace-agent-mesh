"""
Utility functions for working with A2A Agent Cards.
"""

from typing import Optional, Dict, Tuple
from a2a.types import AgentCard

from .constants import EXTENSION_URI_SCHEMAS


def get_schemas_from_agent_card(
    agent_card: Optional[AgentCard],
) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Extract input and output schemas from an agent card's extensions.

    Args:
        agent_card: The agent card to extract schemas from

    Returns:
        Tuple of (input_schema, output_schema). Either or both may be None.
    """
    if (
        not agent_card
        or not agent_card.capabilities
        or not agent_card.capabilities.extensions
    ):
        return None, None

    for ext in agent_card.capabilities.extensions:
        if ext.uri == EXTENSION_URI_SCHEMAS:
            params = ext.params or {}
            return params.get("input_schema"), params.get("output_schema")

    return None, None
