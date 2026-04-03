"""
Re-export auth utilities from the main shared module.
"""

from solace_agent_mesh.shared.api.auth_utils import get_current_user

__all__ = [
    "get_current_user",
]
