"""
SAM Access Token helper stubs for base repository.

ENTERPRISE FEATURE: The full implementation of sam_access_token helpers
is in the enterprise package. This module provides stubs for graceful
degradation when enterprise is not available.

Base repo components that need these functions (like auth middleware)
will gracefully handle the case where the feature is not available.
"""

import logging
from typing import Any

log = logging.getLogger(__name__)

# For backward compatibility, try to import from enterprise if available
try:
    from solace_agent_mesh_enterprise.gateway.auth.utils import (
        SamTokenResult,
        get_sam_token_config,
        is_sam_token_enabled,
        prepare_and_mint_sam_token,
    )

    log.debug("Enterprise sam_token_helpers loaded successfully")

except ImportError:
    log.debug("Enterprise package not available - sam_token helpers not loaded")

    # Provide minimal stubs for type checking
    class SamTokenResult:
        """Stub class for when enterprise is not available."""

        pass

    def get_sam_token_config(component: Any):
        """Stub: Returns None when enterprise not available."""
        return None

    def is_sam_token_enabled(component: Any) -> bool:
        """Stub: Always returns False when enterprise not available."""
        return False

    async def prepare_and_mint_sam_token(*args, **kwargs):
        """Stub: Returns empty SamTokenResult when enterprise not available."""
        return SamTokenResult()
