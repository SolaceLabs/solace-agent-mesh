"""
Router for handling authentication-related endpoints.
"""

from fastapi import (
    APIRouter,
    Request as FastAPIRequest,
    Depends,
    HTTPException,
    Response,
)
from fastapi.responses import RedirectResponse
import httpx
import secrets
from urllib.parse import urlencode

from ...http_sse.dependencies import get_sac_component, get_api_config
from solace_ai_connector.common.log import log

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
