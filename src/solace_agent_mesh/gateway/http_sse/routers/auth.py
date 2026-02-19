"""
Router for handling authentication-related endpoints.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request as FastAPIRequest,
    Response,
)
from fastapi.responses import HTMLResponse

from ...http_sse.dependencies import (
    get_api_config,
    get_authorization_service,
    get_sac_component,
)

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/auth/login")
async def initiate_login(
    request: FastAPIRequest, config: dict = Depends(get_api_config)
):
    """
    Initiates the login flow by redirecting to the external authorization service.
    """
    try:
        from solace_agent_mesh_enterprise.gateway.auth import handle_login_initiation

        return await handle_login_initiation(request, config)
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="OAuth authentication requires enterprise package. "
            "Install: pip install solace-agent-mesh-enterprise",
        )


@router.get("/csrf-token")
async def get_csrf_token(
    response: Response, component: "WebUIBackendComponent" = Depends(get_sac_component)
):
    """
    Generates and returns a CSRF token, setting it as a readable cookie and returning it in the response.
    """
    csrf_token = secrets.token_urlsafe(32)

    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=False,
        samesite="lax",
        max_age=3600,
    )

    return {"message": "CSRF token set", "csrf_token": csrf_token}


@router.get("/auth/callback")
async def auth_callback(
    request: FastAPIRequest,
    config: dict = Depends(get_api_config),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    authorization_service = Depends(get_authorization_service),
):
    """
    Handles the callback from the OIDC provider by calling an external exchange service.
    """
    try:
        from solace_agent_mesh_enterprise.gateway.auth import handle_auth_callback

        return await handle_auth_callback(
            request, config, component, authorization_service
        )
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="OAuth authentication requires enterprise package. "
            "Install: pip install solace-agent-mesh-enterprise",
        )


@router.post("/auth/logout")
async def logout(
    request: FastAPIRequest,
    response: Response,
    component: "WebUIBackendComponent" = Depends(get_sac_component),
):
    """
    Logout endpoint - clears server-side session and access token.

    This endpoint:
    - Clears the access_token from the session storage
    - Clears all session data
    - Returns success even if already logged out (idempotent)

    The session cookie will be invalidated, requiring re-authentication
    on the next request.
    """
    try:
        # Clear access token from session storage
        if hasattr(request, 'session') and 'access_token' in request.session:
            del request.session['access_token']
            log.debug("Cleared access_token from session")

        # Clear refresh token if present
        if hasattr(request, 'session') and 'refresh_token' in request.session:
            del request.session['refresh_token']
            log.debug("Cleared refresh_token from session")

        # Clear all other session data
        if hasattr(request, 'session'):
            request.session.clear()
            log.debug("Cleared all session data")

        # Clear the session cookie from response so FE cannot use it
        use_secure = bool(component.ssl_keyfile and component.ssl_certfile)

        response.delete_cookie(
            key="session",      # SessionMiddleware default
            path="/",           # SessionMiddleware default
            samesite="lax",     # SessionMiddleware default
            httponly=True,      # Always set by SessionMiddleware
            secure=use_secure,  # Match SSL configuration
        )
        log.debug(f"Deleted session cookie (httponly=True, secure={use_secure})")

        log.info("User logged out successfully")
        return {"success": True, "message": "Logged out successfully"}

    except Exception as e:
        log.error(f"Error during logout: {e}")
        # Still return success - logout should be idempotent
        return {"success": True, "message": "Logged out successfully"}


@router.post("/auth/refresh")
async def refresh_token(
    request: FastAPIRequest,
    config: dict = Depends(get_api_config),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    authorization_service = Depends(get_authorization_service),
):
    """
    Refreshes an access token using the external authorization service.
    """
    try:
        from solace_agent_mesh_enterprise.gateway.auth import handle_token_refresh

        return await handle_token_refresh(
            request, config, component, authorization_service
        )
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="OAuth authentication requires enterprise package. "
            "Install: pip install solace-agent-mesh-enterprise",
        )


@router.get("/auth/tool/callback")
async def auth_tool_callback(
    request: FastAPIRequest,
    component: "WebUIBackendComponent" = Depends(get_sac_component),
):
    """
    Handles OAuth2 authorization code grant response for tool authentication.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    error_description = request.query_params.get("error_description")

    if error:
        log.error(f"OAuth2 tool callback received error: {error} - {error_description}")
        return HTMLResponse(
            content=f"""
            <html>
                <head>
                    <title>Authorization Error</title>
                </head>
                <body>
                    <h2>Authorization Error</h2>
                    <p>Error: {error}</p>
                    <p>Description: {error_description or 'No description provided'}</p>
                    <p>Please close this window and try again.</p>
                </body>
            </html>
            """,
            status_code=400
        )

    # Get the current request URL for logging/debugging
    url = str(request.url)


    if not code:
        log.warning("OAuth2 tool callback received without authorization code")
        return HTMLResponse(
            content="""
            <html>
                <head>
                    <title>Authorization Error</title>
                </head>
                <body>
                    <h2>Authorization Error</h2>
                    <p>No authorization code received. Please close this window and try again.</p>
                </body>
            </html>
            """,
            status_code=400
        )

    log.info(f"OAuth2 tool callback received authorization code: {code}")

    try:
        from solace_agent_mesh_enterprise.auth.input_required import process_auth_grant_response
        await process_auth_grant_response(component, code, state, url)
    except ImportError:
        pass

    # Return simple HTML page instructing user to close the window
    return HTMLResponse(
        content="""
        <html>
            <head>
                <title>Authorization Complete</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 50px;
                        background-color: #f5f5f5;
                    }
                    .container {
                        background: white;
                        padding: 30px;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        display: inline-block;
                    }
                    h2 { color: #28a745; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>✓ Authorization Complete</h2>
                    <p>You have successfully authorized the tool access.</p>
                    <p><strong>Please close this window.</strong></p>
                </div>
            </body>
        </html>
        """
    )
