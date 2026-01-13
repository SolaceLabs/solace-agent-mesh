"""
Shared utilities for the HTTP SSE gateway.

Re-exports commonly used utilities from the main shared module for convenience.
"""

from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from solace_agent_mesh.shared.utils.types import UserId

__all__ = [
    "now_epoch_ms",
    "UserId",
]
