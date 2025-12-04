"""
OAuth2 authentication middleware for Platform Service.

Phase 1: Stub implementation for testing.
Phase 2: Will be replaced with real OAuth2 token validation.
"""

import logging

from fastapi import Request

log = logging.getLogger(__name__)


async def oauth2_stub_middleware(request: Request, call_next):
    """
    STUB OAuth2 middleware for Phase 1 development and testing.

    This middleware always sets a fake authenticated user for testing purposes.
    It allows the Platform Service to start and accept requests without requiring
    a real OAuth2 service during initial development.

    **TODO Phase 2:** Replace this with real OAuth2 token validation:
    1. Extract token from Authorization header
    2. Validate token with external OAuth2 service
    3. Parse user info from token validation response
    4. Set request.state.user with real user details
    5. Raise HTTPException(401) if token is invalid/missing

    Args:
        request: FastAPI Request object.
        call_next: Next middleware/handler in the chain.

    Returns:
        Response from the next handler.
    """
    # Set stub user data (always authenticated for Phase 1)
    request.state.user = {
        "id": "stub_user",
        "user_id": "stub_user",
        "email": "stub@example.com",
        "name": "Stub User (Phase 1)",
    }

    log.debug(
        "OAuth2 stub middleware: Set stub user (Phase 1 - REPLACE IN PHASE 2 WITH REAL VALIDATION)"
    )

    # Call the next handler
    response = await call_next(request)
    return response
