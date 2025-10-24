"""
Router for handling authentication-related endpoints.
"""

import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request as FastAPIRequest,
    Response,
)
from fastapi.responses import HTMLResponse, RedirectResponse

from ...http_sse.dependencies import get_api_config, get_sac_component

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/auth/login")
async def initiate_login(
    request: FastAPIRequest, config: dict = Depends(get_api_config)
):
    """
    Initiates the login flow by redirecting to the external authorization service.
    """
    external_auth_url = config.get("external_auth_service_url", "http://localhost:8080")
    callback_url = config.get(
        "external_auth_callback_uri", "http://localhost:8000/api/v1/auth/callback"
    )

    params = {
        "provider": config.get("external_auth_provider", "azure"),
        "redirect_uri": callback_url,
    }

    login_url = f"{external_auth_url}/login?{urlencode(params)}"
    log.info(f"Redirecting to external authorization service: {login_url}")

    return RedirectResponse(url=login_url)


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
):
    """
    Handles the callback from the OIDC provider by calling an external exchange service.
    """
    code = request.query_params.get("code")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    external_auth_url = config.get("external_auth_service_url", "http://localhost:8080")
    exchange_url = f"{external_auth_url}/exchange-code"
    redirect_uri = config.get(
        "external_auth_callback_uri", "http://localhost:8000/api/v1/auth/callback"
    )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                exchange_url,
                json={
                    "code": code,
                    "provider": config.get("external_auth_provider", "azure"),
                    "redirect_uri": redirect_uri,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            token_data = response.json()
        except httpx.HTTPStatusError as e:
            log.error(f"Failed to exchange code: {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to exchange code: {e.response.text}",
            )
        except Exception as e:
            log.error(f"Error during code exchange: {e}")
            raise HTTPException(status_code=500, detail="Error during code exchange")

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not access_token:
        raise HTTPException(
            status_code=400, detail="Access token not in response from exchange service"
        )

    request.session["access_token"] = access_token
    if refresh_token:
        request.session["refresh_token"] = refresh_token
    log.debug("Tokens stored directly in session.")

    try:
        async with httpx.AsyncClient() as client:
            user_info_response = await client.get(
                f"{external_auth_url}/user_info",
                params={"provider": config.get("external_auth_provider", "azure")},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_info_response.raise_for_status()
            user_info = user_info_response.json()

            user_id = user_info.get("email", "authenticated_user")
            if user_id:
                session_manager = component.get_session_manager()
                session_manager.store_user_id(request, user_id)
            else:
                log.warning("Could not find 'email' in user info response.")

    except httpx.HTTPStatusError as e:
        log.error(f"Failed to get user info: {e.response.text}")

    except Exception as e:
        log.error(f"Error getting user info: {e}")

    frontend_base_url = config.get("frontend_redirect_url", "http://localhost:3000")

    hash_params = {"access_token": access_token}
    if refresh_token:
        hash_params["refresh_token"] = refresh_token

    hash_fragment = urlencode(hash_params)

    frontend_redirect_url = f"{frontend_base_url}/auth-callback.html#{hash_fragment}"
    return RedirectResponse(url=frontend_redirect_url)


@router.post("/auth/refresh")
async def refresh_token(
    request: FastAPIRequest,
    config: dict = Depends(get_api_config),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
):
    """
    Refreshes an access token using the external authorization service.
    """
    data = await request.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Missing refresh_token")

    external_auth_url = config.get("external_auth_service_url", "http://localhost:8080")
    refresh_url = f"{external_auth_url}/refresh_token"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                refresh_url,
                json={
                    "refresh_token": refresh_token,
                    "provider": config.get("external_auth_provider", "azure"),
                },
                timeout=20.0,
            )
            response.raise_for_status()
            token_data = response.json()
        except httpx.HTTPStatusError as e:
            log.error(f"Failed to refresh token: {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to refresh token: {e.response.text}",
            )
        except Exception as e:
            log.error(f"Error during token refresh: {e}")
            raise HTTPException(status_code=500, detail="Error during token refresh")

    access_token = token_data.get("access_token")
    new_refresh_token = token_data.get("refresh_token")

    if not access_token:
        raise HTTPException(
            status_code=400, detail="Access token not in response from refresh service"
        )

    session_manager = component.get_session_manager()
    session_manager.store_auth_tokens(request, access_token, new_refresh_token)
    log.info("Successfully refreshed and updated tokens in session.")

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
    }


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
