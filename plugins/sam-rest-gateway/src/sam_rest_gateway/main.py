"""
Defines the FastAPI application instance for the REST Gateway.
"""

from fastapi import FastAPI, Request as FastAPIRequest, HTTPException
from solace_ai_connector.common.log import log
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .component import RestGatewayComponent

from . import dependencies

app = FastAPI(
    title="SAM REST API Gateway",
    version="0.1.0",
    description="REST API Gateway for the Solace Agent Mesh.",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


import httpx
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from solace_agent_mesh.common.types import (
    JSONRPCResponse as A2AJSONRPCResponse,
    InternalError,
    InvalidRequestError,
)


def setup_dependencies(component: "RestGatewayComponent"):
    """
    Sets up the component instance reference for dependency injection.
    """
    log.info("Setting up FastAPI dependencies for REST Gateway...")
    dependencies.set_component_instance(component)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class AuthMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            request = FastAPIRequest(scope, receive)
            enforce_auth = component.get_config("enforce_authentication", False)
            auth_service_url = component.get_config("external_auth_service_url")
            auth_service_provider = component.get_config(
                "external_auth_service_provider", "azure"
            )

            if request.url.path.startswith(
                (
                    "/health",
                    "/api/health",
                    "/api/v1/docs",
                    "/api/v2/docs",
                    "/api/v1/openapi.json",
                    "/api/v2/openapi.json",
                )
            ):
                await self.app(scope, receive, send)
                return

            if enforce_auth:
                if not auth_service_url:
                    log.error(
                        "Authentication is enforced, but 'external_auth_service_url' is not configured."
                    )
                    response = JSONResponse(
                        status_code=500,
                        content={"detail": "Authentication service not configured."},
                    )
                    await response(scope, receive, send)
                    return

                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("Bearer "):
                    response = JSONResponse(
                        status_code=401,
                        content={"detail": "Bearer token not provided."},
                    )
                    await response(scope, receive, send)
                    return

                token = auth_header.split(" ")[1]
                try:
                    async with httpx.AsyncClient() as client:
                        validation_response = await client.post(
                            f"{auth_service_url}/is_token_valid",
                            json={"provider": auth_service_provider},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        if validation_response.status_code != 200:
                            response = JSONResponse(
                                status_code=401,
                                content={"detail": "Invalid or expired token."},
                            )
                            await response(scope, receive, send)
                            return

                        user_info_response = await client.get(
                            f"{auth_service_url}/user_info",
                            params={"provider": auth_service_provider},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        user_info_response.raise_for_status()
                        user_info = user_info_response.json()

                    email_from_auth = user_info.get("email")
                    if not email_from_auth:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User email not provided by auth provider",
                        )

                    identity_service = component.identity_service
                    if not identity_service:
                        log.warning(
                            "AuthMiddleware: Internal IdentityService not configured. Falling back to using email as ID."
                        )
                        request.state.user = {
                            "id": email_from_auth,
                            "email": email_from_auth,
                            "name": user_info.get("name", email_from_auth),
                        }
                    else:
                        lookup_key = getattr(identity_service, "lookup_key", "id")
                        user_profile = await identity_service.get_user_profile(
                            {lookup_key: email_from_auth}
                        )
                        if not user_profile:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="User not authorized for this application",
                            )
                        request.state.user = user_profile

                except httpx.RequestError as exc:
                    log.error(f"Error calling auth service: {exc}")
                    response = JSONResponse(
                        status_code=503,
                        content={"detail": "Authentication service is unavailable."},
                    )
                    await response(scope, receive, send)
                    return
                except httpx.HTTPStatusError as exc:
                    log.warning(
                        f"Auth service returned an error: {exc.response.status_code} {exc.response.text}"
                    )
                    response = JSONResponse(
                        status_code=401, content={"detail": "Authentication failed."}
                    )
                    await response(scope, receive, send)
                    return
                except HTTPException as exc:
                    raise exc
                except Exception as exc:
                    log.exception(
                        f"An unexpected error occurred in auth middleware: {exc}"
                    )
                    response = JSONResponse(
                        status_code=500,
                        content={
                            "detail": "An internal error occurred during authentication."
                        },
                    )
                    await response(scope, receive, send)
                    return

            await self.app(scope, receive, send)

    app.add_middleware(AuthMiddleware)
    log.info("CORS and Auth middleware added.")

    from .routers import v1, v2, artifacts

    app.include_router(v1.router, prefix="/api/v1", tags=["v1 (Legacy)"])
    app.include_router(v2.router, prefix="/api/v2", tags=["v2"])
    app.include_router(
        artifacts.router, prefix="/api/v2/artifacts", tags=["v2 - Artifacts"]
    )
    log.info("Included v1, v2, and artifacts API routers.")


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"], include_in_schema=False)
async def health_check(request: FastAPIRequest):
    """
    Basic health check endpoint. Available at both `/health` and `/api/health`.
    The `/api/health` endpoint is for backward compatibility and is not shown in OpenAPI docs.
    """
    log.debug("Health check endpoint called for path: %s", request.url.path)
    return {"status": "ok"}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: FastAPIRequest, exc: HTTPException):
    """Handles FastAPI's built-in HTTPExceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: FastAPIRequest, exc: RequestValidationError
):
    """Handles Pydantic validation errors."""
    error_obj = InvalidRequestError(
        message="Invalid request parameters", data=exc.errors()
    )
    response = A2AJSONRPCResponse(error=error_obj)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(exclude_none=True),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: FastAPIRequest, exc: Exception):
    """Handles any other unexpected exceptions."""
    log.exception(
        "Unhandled Exception: %s, Request: %s %s", exc, request.method, request.url
    )
    error_obj = InternalError(
        message=f"An unexpected server error occurred: {type(exc).__name__}"
    )
    response = A2AJSONRPCResponse(error=error_obj)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(exclude_none=True),
    )


v1_openapi_schema = None
v2_openapi_schema = None


def _filter_openapi_schema(full_schema: dict, allowed_tags: list[str]) -> dict:
    """Filters an OpenAPI schema to only include paths with allowed tags."""
    filtered_schema = full_schema.copy()

    filtered_paths = {}
    for path, path_item in full_schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if any(tag in allowed_tags for tag in operation.get("tags", [])):
                if path not in filtered_paths:
                    filtered_paths[path] = {}
                filtered_paths[path][method] = operation

    filtered_schema["paths"] = filtered_paths
    return filtered_schema


@app.get("/api/v1/openapi.json", include_in_schema=False)
async def get_v1_openapi_schema():
    """Generates and returns the OpenAPI schema for the v1 API."""
    global v1_openapi_schema
    if v1_openapi_schema is None:
        full_schema = get_openapi(
            title="SAM REST API Gateway - v1 (Legacy)",
            version="1.0.0",
            routes=app.routes,
        )
        v1_openapi_schema = _filter_openapi_schema(full_schema, ["v1 (Legacy)"])
    return v1_openapi_schema


@app.get("/api/v2/openapi.json", include_in_schema=False)
async def get_v2_openapi_schema():
    """Generates and returns the OpenAPI schema for the v2 API."""
    global v2_openapi_schema
    if v2_openapi_schema is None:
        full_schema = get_openapi(
            title="SAM REST API Gateway - v2",
            version="2.0.0",
            routes=app.routes,
        )
        v2_openapi_schema = _filter_openapi_schema(
            full_schema, ["v2", "v2 - Artifacts"]
        )
    return v2_openapi_schema


@app.get("/api/v1/docs", response_class=HTMLResponse, include_in_schema=False)
async def get_v1_api_docs():
    """Serves the Swagger UI for the v1 API."""
    return get_swagger_ui_html(
        openapi_url="/api/v1/openapi.json",
        title="SAM REST API Gateway - v1 (Legacy)",
    )


@app.get("/api/v2/docs", response_class=HTMLResponse, include_in_schema=False)
async def get_v2_api_docs():
    """Serves the Swagger UI for the v2 API."""
    return get_swagger_ui_html(
        openapi_url="/api/v2/openapi.json",
        title="SAM REST API Gateway - v2",
    )


log.info("FastAPI application instance for REST Gateway created.")
