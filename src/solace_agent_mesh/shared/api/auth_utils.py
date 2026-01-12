"""
Authentication utilities for the FastAPI application.

This module provides common authentication functions used across controllers.
"""

from fastapi import Depends, Request as FastAPIRequest


async def get_current_user(request: FastAPIRequest) -> dict:
    """
    Extracts the current user from the request state.
    
    This function is used as a FastAPI dependency to get the authenticated user
    information that was set by the AuthMiddleware.
    
    Args:
        request: The FastAPI request object with user state
        
    Returns:
        dict: User information dictionary containing id, name, email, etc.
    """
    return getattr(request.state, "user", {
        "id": "anonymous",
        "name": "Anonymous User",
        "email": "anonymous@localhost",
        "authenticated": False,
        "auth_method": "none"
    })