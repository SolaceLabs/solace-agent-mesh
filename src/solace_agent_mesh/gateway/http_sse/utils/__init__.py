"""Utilities for the HTTP SSE Gateway."""

# SAM token helpers (stub in base, full implementation in enterprise)
from solace_agent_mesh.gateway.http_sse.utils.sam_token_helpers import (
    SamTokenResult,
    is_sam_token_enabled,
    prepare_and_mint_sam_token,
)

# Note: claim_mapping removed from base repo - enterprise only

__all__ = [
    "is_sam_token_enabled",
    "SamTokenResult",
    "prepare_and_mint_sam_token",
]
