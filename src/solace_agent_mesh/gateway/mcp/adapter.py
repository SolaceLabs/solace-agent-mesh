"""
MCP Gateway Adapter for the Generic Gateway Framework.

This adapter exposes SAM agents as MCP (Model Context Protocol) tools using FastMCP.
Agents are dynamically discovered from the agent registry and exposed as callable tools.
"""

import asyncio
import base64
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from a2a.types import AgentCard, AgentSkill
from fastmcp import FastMCP, Context as McpContext
from mcp.types import (
    AudioContent,
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    ResourceLink,
    TextContent,
    TextResourceContents,
)
from pydantic import BaseModel, Field

from ...common.utils.mime_helpers import is_text_based_file
from ..adapter.base import GatewayAdapter
from ..adapter.types import (
    AuthClaims,
    GatewayContext,
    ResponseContext,
    SamDataPart,
    SamError,
    SamFilePart,
    SamTask,
    SamTextPart,
    SamUpdate,
)
from .utils import sanitize_tool_name, format_agent_skill_description

log = logging.getLogger(__name__)

# Sentinel value to signal stream completion
STREAM_COMPLETE = object()


class McpAdapterConfig(BaseModel):
    """Configuration model for the McpAdapter."""

    mcp_server_name: str = Field(
        default="SAM MCP Gateway", description="Name of the MCP server"
    )
    mcp_server_description: str = Field(
        default="Model Context Protocol gateway to Solace Agent Mesh",
        description="Description of the MCP server",
    )
    transport: str = Field(
        default="http", description="Transport type: 'http' or 'stdio'"
    )
    port: int = Field(default=8000, description="Port for HTTP transport")
    host: str = Field(default="0.0.0.0", description="Host for HTTP transport")
    default_user_identity: str = Field(
        default="mcp_user", description="Default user identity for authentication"
    )
    stream_responses: bool = Field(
        default=True, description="Whether to stream responses back to MCP client"
    )
    task_timeout_seconds: int = Field(
        default=300,
        description="Timeout in seconds for waiting for agent task completion (default 5 minutes)",
    )

    # OAuth Authentication Configuration
    enable_auth: bool = Field(
        default=False,
        description="Enable OAuth authentication. Requires HTTP transport and external OAuth2 service.",
    )
    external_auth_service_url: str = Field(
        default="http://localhost:8050",
        description="URL of SAM's OAuth2 service (enterprise feature)",
    )
    external_auth_provider: str = Field(
        default="azure",
        description="OAuth provider configured in OAuth2 service (e.g., 'azure', 'google')",
    )
    dev_mode: bool = Field(
        default=False,
        description="Development mode - bypass auth and use default_user_identity (WARNING: insecure, dev only)",
    )
    user_id_claim: str = Field(
        default="email",
        description="OAuth claim to use as user ID for SAM audit logs (options: 'email', 'sub', 'upn', 'preferred_username')",
    )
    oauth_proxy_url: str = Field(
        default="http://localhost:8000",
        description="URL of WebUI gateway OAuth proxy for triple-redirect flow (MCP → WebUI → Azure)",
    )
    session_secret_key: Optional[str] = Field(
        default=None,
        description="Secret key for session encryption (auto-generated if not provided)",
    )
    require_pkce: bool = Field(
        default=True,
        description="Require PKCE (Proof Key for Code Exchange, RFC 7636) for all OAuth flows. "
                    "STRONGLY recommended for security. Disable only for legacy client compatibility.",
    )

    # File handling configuration
    inline_image_max_bytes: int = Field(
        default=5_242_880,  # 5MB
        description="Maximum size in bytes for inline image returns (larger images become resource links)",
    )
    inline_audio_max_bytes: int = Field(
        default=10_485_760,  # 10MB
        description="Maximum size in bytes for inline audio returns (larger audio becomes resource links)",
    )
    inline_text_max_bytes: int = Field(
        default=1_048_576,  # 1MB
        description="Maximum size in bytes for inline text file returns (larger text files become resource links)",
    )
    inline_binary_max_bytes: int = Field(
        default=524_288,  # 512KB
        description="Maximum size in bytes for inline binary returns (larger binaries become resource links)",
    )

    # Resource configuration
    resource_uri_prefix: str = Field(
        default="artifact",
        description="URI prefix for artifact resources (e.g., 'artifact://session_id/filename')",
    )
    enable_artifact_resources: bool = Field(
        default=True,
        description="Whether to expose artifacts as MCP resources",
    )


class McpAdapter(GatewayAdapter):
    """
    MCP Gateway Adapter that exposes SAM agents as MCP tools.

    This adapter:
    - Discovers agents from the agent registry
    - Creates MCP tools dynamically based on agent skills
    - Handles streaming responses from SAM agents
    - Maps MCP tool calls to SAM tasks
    """

    ConfigModel = McpAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.mcp_server: Optional[FastMCP] = None
        self.tool_to_agent_map: Dict[str, tuple[str, str]] = (
            {}
        )  # tool_name -> (agent_name, skill_id)
        self.active_tasks: Dict[str, str] = {}  # task_id -> tool_name (for correlation)
        self.task_buffers: Dict[str, List[str]] = {}  # task_id -> list of text chunks
        self.task_futures: Dict[str, asyncio.Future] = (
            {}
        )  # task_id -> Future for completion
        self.task_errors: Dict[str, SamError] = {}  # task_id -> error if failed
        self.task_queues: Dict[str, asyncio.Queue] = (
            {}
        )  # task_id -> Queue for streaming chunks
        self.agent_to_tools: Dict[str, List[str]] = (
            {}
        )  # agent_name -> list of tool names

        # Store MCP context for enterprise authentication
        # Enterprise auth extractors will access this to extract tokens
        self._current_mcp_context: Optional[Any] = None

        # Resource management for artifact access
        # Track which artifacts exist per session for resource listing
        self.session_artifacts: Dict[str, Dict[str, Dict[str, Any]]] = (
            {}
        )  # session_id -> {filename -> metadata}

        # OAuth authorization codes for triple-redirect flow
        # Maps authorization code -> {tokens, created_at, code_challenge, redirect_uri}
        # Note: code_challenge is required when require_pkce is enabled (default)
        self.oauth_codes: Dict[str, Dict[str, Any]] = {}

        # OAuth state storage for authorize -> callback flow
        # Maps internal_state -> {client_redirect_uri, client_state, code_challenge, code_challenge_method, created_at, ttl_seconds}
        # Note: code_challenge and code_challenge_method are required when require_pkce is enabled (default)
        self.oauth_states: Dict[str, Dict[str, Any]] = {}

    async def init(self, context: GatewayContext) -> None:
        """Initialize the MCP server and register tools from discovered agents."""
        self.context = context
        config: McpAdapterConfig = self.context.adapter_config

        log.info("Initializing MCP Gateway Adapter...")

        # Validate OAuth configuration
        if config.enable_auth:
            if config.transport == "stdio":
                raise ValueError(
                    "OAuth authentication requires HTTP transport. "
                    "Set transport='http' in configuration when enable_auth=True."
                )
            if config.dev_mode:
                log.warning(
                    "⚠️  DEV MODE ENABLED: Authentication is bypassed! "
                    "This is insecure and should NEVER be used in production."
                )
            log.info(
                "OAuth authentication enabled: service=%s, provider=%s",
                config.external_auth_service_url,
                config.external_auth_provider,
            )
        elif config.dev_mode:
            log.warning(
                "⚠️  DEV MODE ENABLED with auth disabled: Using default_user_identity=%s",
                config.default_user_identity,
            )
        else:
            log.info(
                "OAuth authentication disabled, using default_user_identity=%s",
                config.default_user_identity,
            )

        # OAuth authentication is handled by the generic gateway's auth_handler
        # (enterprise feature, see GenericGatewayComponent._setup_auth)

        # Create FastMCP server with OAuth info in description if enabled
        server_description = config.mcp_server_description
        if config.enable_auth and not config.dev_mode:
            oauth_authorize_url = f"http://{config.host}:{config.port}/oauth/authorize"
            oauth_metadata_url = f"http://{config.host}:{config.port}/.well-known/oauth-authorization-server"
            server_description = (
                f"{config.mcp_server_description}\n\n"
                f"🔒 Authentication: OAuth 2.0 required\n"
                f"📋 Metadata: {oauth_metadata_url}\n"
                f"🔐 Authorize: {oauth_authorize_url}"
            )

        self.mcp_server = FastMCP(
            name=config.mcp_server_name,
            instructions=server_description
        )

        # Register artifact resource template if enabled
        if config.enable_artifact_resources:
            self._register_artifact_resource_template()

        # Register OAuth endpoints if authentication is enabled and handler is available
        if config.enable_auth and hasattr(self.context, 'auth_handler') and self.context.auth_handler:
            self._register_oauth_endpoints()

        # Register tools dynamically from agent registry
        await self._register_tools_from_agents()

        # Start the MCP server in the background
        asyncio.create_task(self._run_mcp_server())

        log.info(
            "MCP Gateway Adapter initialized with %d tools", len(self.tool_to_agent_map)
        )

    async def _register_tools_from_agents(self):
        """Query agent registry and register MCP tools for each agent's skills."""
        try:
            agents: List[AgentCard] = self.context.list_agents()
            log.info("Discovered %d agents from registry", len(agents))

            for agent_card in agents:
                if not agent_card.skills:
                    log.debug("Agent %s has no skills, skipping", agent_card.name)
                    continue

                for skill in agent_card.skills:
                    self._register_tool_for_skill(agent_card, skill)

        except Exception as e:
            log.exception("Error registering tools from agents: %s", e)

    def _register_artifact_resource_template(self):
        """
        Register a resource template for artifacts.

        This allows MCP clients to access artifacts via URIs like:
        artifact://{session_id}/{filename}

        The template handler will dynamically load artifacts from the artifact service.
        """
        config: McpAdapterConfig = self.context.adapter_config

        @self.mcp_server.resource(
            uri=f"{config.resource_uri_prefix}://{{session_id}}/{{filename}}",
            name="artifact_template",
            description="Access artifacts created during tool execution",
        )
        async def artifact_resource_handler(session_id: str, filename: str):
            """
            Handles MCP resource read requests for artifacts.

            Args:
                session_id: The session ID (e.g., "mcp-client-abc123")
                filename: The artifact filename

            Returns:
                TextResourceContents or BlobResourceContents
            """
            return await self._handle_artifact_resource_read(session_id, filename)

        log.info(
            f"Registered artifact resource template: {config.resource_uri_prefix}://{{session_id}}/{{filename}}"
        )

    def _register_oauth_endpoints(self):
        """
        Register OAuth endpoints with the FastMCP server.

        OAuth endpoints are added to the underlying Starlette app in _run_mcp_server().
        This method serves as documentation of the endpoints that will be exposed.

        OAuth endpoints that will be exposed:
        - GET /oauth/authorize - Initiates OAuth flow (via enterprise auth handler)
        - GET /oauth/callback - Handles OAuth callback (via enterprise auth handler)
        - GET /.well-known/oauth-authorization-server - OAuth metadata

        The actual OAuth logic is handled by the enterprise SAMOAuth2Handler,
        these routes just delegate to it.
        """
        if not self.context.auth_handler:
            return

        log.info(
            "OAuth endpoints will be added to HTTP server: "
            "/oauth/authorize, /oauth/callback, /.well-known/oauth-authorization-server"
        )

    def _cleanup_expired_oauth_states(self):
        """
        Remove expired OAuth states to prevent memory leaks.
        Called at the start of each authorize request.
        """
        import time
        now = time.time()
        expired = [
            state for state, data in self.oauth_states.items()
            if now - data['created_at'] > data['ttl_seconds']
        ]
        for state in expired:
            del self.oauth_states[state]
        if expired:
            log.debug("Cleaned up %d expired OAuth states", len(expired))

    async def _handle_oauth_authorize(self, request):
        """
        Handle GET /oauth/authorize - Initiates triple-redirect OAuth flow.

        Triple-redirect flow (MCP-specific):
        1. MCP Client → MCP /oauth/authorize
        2. MCP → WebUI /gateway-oauth/authorize
        3. WebUI → Azure AD (handled by WebUI)
        4. Azure → WebUI callback
        5. WebUI → MCP /oauth/callback (with gateway code)
        6. MCP redirects to client's redirect_uri (with authorization code)

        Query params from MCP client:
            response_type: "code" (required)
            client_id: Client ID from registration
            redirect_uri: Client's callback URI (e.g., http://127.0.0.1:PORT/callback)
            scope: Requested scopes
            state: CSRF protection token
            code_challenge: PKCE challenge (required, RFC 7636)
            code_challenge_method: Must be "S256" (required)

        Returns:
            Redirect to WebUI OAuth proxy
        """
        from starlette.responses import RedirectResponse
        from urllib.parse import urlencode
        import secrets
        import time

        config: McpAdapterConfig = self.context.adapter_config

        # Extract query parameters from MCP client
        query_params = dict(request.query_params)
        redirect_uri = query_params.get("redirect_uri")
        state = query_params.get("state")
        code_challenge = query_params.get("code_challenge")
        code_challenge_method = query_params.get("code_challenge_method")

        if not redirect_uri:
            from starlette.responses import JSONResponse
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Missing redirect_uri"},
                status_code=400
            )

        # Enforce PKCE requirement (RFC 7636)
        if config.require_pkce:
            if not code_challenge:
                log.error("MCP OAuth: code_challenge required but not provided")
                return JSONResponse(
                    {"error": "invalid_request"},
                    status_code=400
                )

            if not code_challenge_method:
                log.error("MCP OAuth: code_challenge_method required but not provided")
                return JSONResponse(
                    {"error": "invalid_request"},
                    status_code=400
                )

            if code_challenge_method != "S256":
                log.error("MCP OAuth: Unsupported code_challenge_method: %s", code_challenge_method)
                return JSONResponse(
                    {"error": "invalid_request"},
                    status_code=400
                )

        # Clean up expired OAuth states
        self._cleanup_expired_oauth_states()

        # Log successful PKCE validation
        if config.require_pkce:
            log.info(
                "MCP OAuth authorize: PKCE enforced, method=%s, redirect_uri=%s",
                code_challenge_method,
                redirect_uri
            )

        # Store client's OAuth request in memory for callback
        # Generate internal state to correlate callback with this request
        internal_state = secrets.token_urlsafe(32)

        self.oauth_states[internal_state] = {
            'client_redirect_uri': redirect_uri,
            'client_state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': code_challenge_method,
            'created_at': time.time(),
            'ttl_seconds': 300  # 5 minutes
        }

        log.info("Stored OAuth state for internal_state=%s", internal_state)

        # Build MCP's callback URI (where WebUI will send gateway code)
        mcp_callback_uri = f"http://{config.host}:{config.port}/oauth/callback"

        # Redirect to WebUI OAuth proxy with internal state
        proxy_params = {
            "gateway_uri": mcp_callback_uri,
            "state": internal_state
        }

        proxy_url = f"{config.oauth_proxy_url}/api/v1/gateway-oauth/authorize?{urlencode(proxy_params)}"

        log.info(
            "MCP OAuth: Redirecting to WebUI proxy for triple-redirect flow. Client redirect_uri=%s",
            redirect_uri
        )

        return RedirectResponse(url=proxy_url, status_code=302)

    async def _handle_oauth_callback(self, request):
        """
        Handle GET /oauth/callback - OAuth callback from WebUI OAuth proxy.

        This is step 5 in the triple-redirect flow:
        1. MCP Client → MCP /oauth/authorize
        2. MCP → WebUI /gateway-oauth/authorize
        3. WebUI → Azure AD (handled by WebUI)
        4. Azure → WebUI callback
        5. **WebUI → MCP /oauth/callback (with gateway code)** ← WE ARE HERE
        6. MCP redirects to client's redirect_uri (with authorization code)

        Query params from WebUI:
            code: Gateway code (single-use, short-lived)
            state: Internal state we sent in step 2

        Returns:
            Redirect to client's redirect_uri with authorization code
        """
        from starlette.responses import JSONResponse, RedirectResponse
        from urllib.parse import urlencode
        import secrets
        import httpx
        import time

        config: McpAdapterConfig = self.context.adapter_config

        # Extract gateway code and state from WebUI
        gateway_code = request.query_params.get("code")
        returned_state = request.query_params.get("state")

        if not gateway_code:
            log.error("MCP OAuth callback: Missing gateway code from WebUI")
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Missing code parameter"},
                status_code=400
            )

        # Look up OAuth state from in-memory storage
        state_data = self.oauth_states.get(returned_state)
        if not state_data:
            log.error("MCP OAuth callback: Invalid or expired state parameter: %s", returned_state)
            return JSONResponse(
                {"error": "invalid_request"},
                status_code=400
            )

        # Check expiration
        age = time.time() - state_data['created_at']
        if age > state_data['ttl_seconds']:
            log.error("MCP OAuth callback: State expired (age=%.1fs)", age)
            del self.oauth_states[returned_state]
            return JSONResponse(
                {"error": "invalid_request"},
                status_code=400
            )

        # Get client's redirect info from stored state
        client_redirect_uri = state_data['client_redirect_uri']
        client_state = state_data['client_state']
        code_challenge = state_data['code_challenge']
        code_challenge_method = state_data['code_challenge_method']

        # Delete state (one-time use)
        del self.oauth_states[returned_state]

        log.info("Retrieved OAuth state for internal_state=%s, client_redirect_uri=%s",
                 returned_state, client_redirect_uri)

        try:
            # Exchange gateway code for actual OAuth tokens from WebUI proxy
            mcp_callback_uri = f"http://{config.host}:{config.port}/oauth/callback"

            async with httpx.AsyncClient(timeout=10.0) as client:
                exchange_response = await client.post(
                    f"{config.oauth_proxy_url}/api/v1/gateway-oauth/exchange",
                    json={
                        "code": gateway_code,
                        "gateway_uri": mcp_callback_uri
                    }
                )

                if exchange_response.status_code != 200:
                    log.error(
                        "MCP OAuth: Gateway code exchange failed: %d %s",
                        exchange_response.status_code,
                        exchange_response.text
                    )
                    return JSONResponse(
                        {"error": "server_error"},
                        status_code=502
                    )

                tokens = exchange_response.json()
                access_token = tokens.get("access_token")
                refresh_token = tokens.get("refresh_token")

            if not access_token:
                log.error("MCP OAuth: No access token in exchange response")
                return JSONResponse(
                    {"error": "server_error"},
                    status_code=502
                )

            # Generate authorization code for MCP client
            # This code will be exchanged for tokens via /oauth/token endpoint
            authorization_code = secrets.token_urlsafe(32)

            # Store tokens associated with this authorization code (short-lived)
            self.oauth_codes[authorization_code] = {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'created_at': time.time(),
                'code_challenge': code_challenge,
                'redirect_uri': client_redirect_uri,
                'ttl_seconds': 300  # 5 minutes
            }

            # Build redirect to client with authorization code
            params = {"code": authorization_code}
            if client_state:
                params["state"] = client_state

            separator = '&' if '?' in client_redirect_uri else '?'
            redirect_url = f"{client_redirect_uri}{separator}{urlencode(params)}"

            log.info(
                "MCP OAuth: Successfully exchanged gateway code, redirecting to client at %s",
                client_redirect_uri
            )

            return RedirectResponse(url=redirect_url, status_code=302)

        except httpx.RequestError as e:
            log.error("MCP OAuth: Failed to connect to WebUI proxy for code exchange: %s", e)
            return JSONResponse(
                {"error": "server_error"},
                status_code=503
            )
        except Exception as e:
            log.error("MCP OAuth callback error: %s", e, exc_info=True)
            return JSONResponse(
                {"error": "server_error"},
                status_code=500
            )

    async def _handle_oauth_metadata(self, request):
        """
        Handle GET /.well-known/oauth-authorization-server - OAuth metadata.

        Returns RFC 8414 compliant OAuth 2.0 Authorization Server Metadata.

        IMPORTANT: This server REQUIRES PKCE (RFC 7636) for all authorization code grants
        when require_pkce is enabled (default). Clients must include code_challenge with method S256.
        """
        from starlette.responses import JSONResponse

        config: McpAdapterConfig = self.context.adapter_config

        metadata = {
            "issuer": f"http://{config.host}:{config.port}",
            "authorization_endpoint": f"http://{config.host}:{config.port}/oauth/authorize",
            "token_endpoint": f"http://{config.host}:{config.port}/oauth/token",
            "registration_endpoint": f"http://{config.host}:{config.port}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic", "none"],
            "code_challenge_methods_supported": ["S256"],
        }

        # Add PKCE requirement indicator if enforced
        if config.require_pkce:
            metadata["require_pkce"] = True  # Non-standard but informative

        return JSONResponse(metadata)

    async def _handle_oauth_register(self, request):
        """
        Handle POST /oauth/register - Dynamic client registration (RFC 7591).

        For MCP gateways with pre-configured OAuth, we accept any registration
        and return a success response. The actual OAuth flow uses the gateway's
        pre-configured credentials with the OAuth2 service.

        NOTE: This server requires PKCE when require_pkce is enabled (default).
        """
        from starlette.responses import JSONResponse
        import secrets

        config: McpAdapterConfig = self.context.adapter_config

        try:
            # Parse the registration request (if provided)
            body = await request.json() if request.method == "POST" else {}

            # Generate client credentials (these are for Claude Code's records only,
            # the actual OAuth flow uses the gateway's pre-configured credentials)
            client_id = secrets.token_urlsafe(16)
            client_secret = secrets.token_urlsafe(32)

            # Return RFC 7591 compliant registration response
            response = {
                "client_id": client_id,
                "client_secret": client_secret,
                "client_id_issued_at": int(datetime.now(timezone.utc).timestamp()),
                "client_secret_expires_at": 0,  # Never expires
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",  # PKCE required, no client secret needed
            }

            # Add PKCE requirement indicator if enforced
            if config.require_pkce:
                response["require_pkce"] = True  # Inform client that PKCE is mandatory

            # Include any requested redirect URIs
            if "redirect_uris" in body:
                response["redirect_uris"] = body["redirect_uris"]

            log.info("Dynamic client registration: client_id=%s", client_id)
            return JSONResponse(response, status_code=201)

        except Exception as e:
            log.error("Client registration error: %s", e)
            return JSONResponse(
                {"error": "invalid_request", "error_description": str(e)},
                status_code=400,
            )

    async def _handle_oauth_token(self, request):
        """
        Handle POST /oauth/token - Token exchange endpoint.

        This is the final step of the triple-redirect OAuth flow where Claude Code
        exchanges the authorization code for access/refresh tokens.

        Request body (form-urlencoded):
            grant_type: "authorization_code" or "refresh_token"
            code: Authorization code (for authorization_code grant)
            redirect_uri: Must match the redirect_uri from /oauth/authorize
            code_verifier: PKCE code verifier (required when require_pkce is enabled, RFC 7636)
            refresh_token: Refresh token (for refresh_token grant)

        Returns:
            JSON with tokens:
            {
                "access_token": "...",
                "refresh_token": "...",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        """
        from starlette.responses import JSONResponse
        import time
        import hashlib
        import base64

        try:
            # Parse form-urlencoded body
            body = await request.form()
            grant_type = body.get("grant_type")
            code = body.get("code")
            redirect_uri = body.get("redirect_uri")
            code_verifier = body.get("code_verifier")
            refresh_token = body.get("refresh_token")

            if grant_type == "authorization_code":
                # Validate required parameters
                if not code:
                    return JSONResponse(
                        {"error": "invalid_request"},
                        status_code=400
                    )

                # Look up authorization code
                if not hasattr(self, 'oauth_codes') or code not in self.oauth_codes:
                    log.warning("MCP OAuth token: Invalid or expired authorization code")
                    return JSONResponse(
                        {"error": "invalid_grant"},
                        status_code=400
                    )

                code_data = self.oauth_codes[code]

                # Check expiration
                age = time.time() - code_data['created_at']
                if age > code_data['ttl_seconds']:
                    log.warning("MCP OAuth token: Authorization code expired (age: %.1fs)", age)
                    del self.oauth_codes[code]
                    return JSONResponse(
                        {"error": "invalid_grant"},
                        status_code=400
                    )

                # Validate redirect_uri matches
                if redirect_uri != code_data['redirect_uri']:
                    log.error(
                        "MCP OAuth token: Redirect URI mismatch. Expected=%s, Got=%s",
                        code_data['redirect_uri'],
                        redirect_uri
                    )
                    return JSONResponse(
                        {"error": "invalid_grant"},
                        status_code=400
                    )

                # Validate PKCE (required when require_pkce is enabled)
                code_challenge = code_data.get('code_challenge')

                if config.require_pkce:
                    # PKCE is mandatory
                    if not code_challenge:
                        log.error("MCP OAuth token: Authorization code missing code_challenge (config violation)")
                        return JSONResponse(
                            {"error": "invalid_grant"},
                            status_code=400
                        )

                    if not code_verifier:
                        log.error("MCP OAuth token: Missing code_verifier for PKCE")
                        return JSONResponse(
                            {"error": "invalid_grant"},
                            status_code=400
                        )

                    # Verify code_challenge = BASE64URL(SHA256(code_verifier))
                    verifier_hash = hashlib.sha256(code_verifier.encode('ascii')).digest()
                    computed_challenge = base64.urlsafe_b64encode(verifier_hash).decode('ascii').rstrip('=')

                    if computed_challenge != code_challenge:
                        log.error("MCP OAuth token: PKCE verification failed")
                        return JSONResponse(
                            {"error": "invalid_grant"},
                            status_code=400
                        )

                    log.info("MCP OAuth token: PKCE verification successful")

                elif code_challenge:
                    # PKCE is optional but was used - validate it
                    if not code_verifier:
                        log.error("MCP OAuth token: Missing code_verifier for PKCE")
                        return JSONResponse(
                            {"error": "invalid_grant"},
                            status_code=400
                        )

                    # Verify code_challenge = BASE64URL(SHA256(code_verifier))
                    verifier_hash = hashlib.sha256(code_verifier.encode('ascii')).digest()
                    computed_challenge = base64.urlsafe_b64encode(verifier_hash).decode('ascii').rstrip('=')

                    if computed_challenge != code_challenge:
                        log.error("MCP OAuth token: PKCE verification failed")
                        return JSONResponse(
                            {"error": "invalid_grant"},
                            status_code=400
                        )

                    log.debug("MCP OAuth token: Optional PKCE verification successful")

                # Get tokens and delete code (one-time use)
                access_token = code_data['access_token']
                refresh_token = code_data['refresh_token']
                del self.oauth_codes[code]

                log.info("MCP OAuth: Successfully exchanged authorization code for tokens")

                return JSONResponse({
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "Bearer",
                    "expires_in": 3600  # 1 hour (this is just a hint, actual expiry managed by OAuth2 service)
                })

            elif grant_type == "refresh_token":
                # For refresh token grant, we need to call the OAuth2 service to get new tokens
                # This requires the WebUI proxy to support refresh token exchange
                log.warning("MCP OAuth: Refresh token grant not yet implemented")
                return JSONResponse(
                    {"error": "unsupported_grant_type"},
                    status_code=400
                )

            else:
                log.warning("MCP OAuth token: Unsupported grant_type: %s", grant_type)
                return JSONResponse(
                    {"error": "unsupported_grant_type"},
                    status_code=400
                )

        except Exception as e:
            log.error("MCP OAuth token error: %s", e, exc_info=True)
            return JSONResponse(
                {"error": "server_error"},
                status_code=500
            )

    def _register_tool_for_skill(self, agent_card: AgentCard, skill: AgentSkill):
        """
        Register a single MCP tool for an agent skill.

        If the tool already exists, it will be removed and re-registered
        with the updated information.
        """
        # Create tool name: agent_skill format
        tool_name = sanitize_tool_name(f"{agent_card.name}_{skill.name}")

        # Check if tool already exists (handle re-registration)
        if tool_name in self.tool_to_agent_map:
            log.debug(
                "Tool %s already registered, removing old version before re-registering...",
                tool_name,
            )
            try:
                self.mcp_server.remove_tool(tool_name)
            except Exception as e:
                # If removal fails, log but continue with registration
                log.warning(f"Failed to remove existing tool {tool_name}: {e}")

        # Store mapping
        self.tool_to_agent_map[tool_name] = (agent_card.name, skill.id)

        # Create tool description from skill
        tool_description = format_agent_skill_description(skill)

        # Register the tool with FastMCP
        # We create a closure to capture the agent and skill info
        async def tool_handler(message: str, ctx: McpContext):
            """
            Handler for MCP tool invocation.

            Args:
                message: The input message text
                ctx: FastMCP Context for streaming updates
            """
            return await self._handle_tool_call(
                tool_name=tool_name, message=message, mcp_context=ctx
            )

        # Set function metadata for FastMCP introspection
        tool_handler.__name__ = tool_name
        tool_handler.__doc__ = tool_description

        # Register with decorator pattern
        # This automatically sends tool_list_changed notification to MCP clients
        self.mcp_server.tool(tool_handler)

        log.debug(
            "Registered MCP tool: %s -> %s/%s", tool_name, agent_card.name, skill.id
        )

    async def _handle_tool_call(
        self, tool_name: str, message: str, mcp_context: McpContext
    ) -> str:
        """
        Handle an MCP tool invocation by routing to the appropriate SAM agent.

        This method:
        1. Creates a Future and Queue for the task
        2. Starts a consumer coroutine to stream updates to MCP client
        3. Submits the task to SAM
        4. Waits for the task to complete (with timeout)
        5. Returns the final assembled response

        Args:
            tool_name: The name of the tool being called
            message: The message text from the MCP client
            mcp_context: FastMCP context for streaming updates (stays in this scope)

        Returns:
            Final response text from the agent
        """
        if tool_name not in self.tool_to_agent_map:
            error_msg = f"Tool {tool_name} not found in mapping"
            log.error(error_msg)
            return f"Error: {error_msg}"

        agent_name, skill_id = self.tool_to_agent_map[tool_name]
        config: McpAdapterConfig = self.context.adapter_config

        # Create Future and Queue for this task
        task_future = asyncio.Future()
        stream_queue = asyncio.Queue()
        task_id = None  # Initialize to None so finally block can check it

        try:
            # Use FastMCP's client_id for connection-based session
            # Note: client_id might be None for some transports, use fallback
            try:
                client_id = mcp_context.client_id
            except Exception as e:
                log.warning(f"Failed to access mcp_context.client_id: {e}")
                client_id = None

            if not client_id:
                # Fallback: try session_id first, then generate unique ID
                try:
                    client_id = mcp_context.session_id
                except Exception as e:
                    log.warning(f"Failed to access mcp_context.session_id: {e}")
                    client_id = None

                if not client_id:
                    # Last resort: generate a unique ID
                    import uuid

                    client_id = f"generated-{uuid.uuid4().hex[:12]}"

                log.warning(
                    f"mcp_context.client_id not available, using fallback: {client_id}"
                )

            # Store MCP context for enterprise authentication
            # Enterprise auth extractors will access this to extract Bearer tokens
            self._current_mcp_context = mcp_context

            # Create external input dict with client_id
            # NOTE: Token extraction is now handled by enterprise auth
            external_input = {
                "tool_name": tool_name,
                "agent_name": agent_name,
                "skill_id": skill_id,
                "message": message,
                "mcp_client_id": client_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Submit to SAM via the generic gateway with endpoint_context
            task_id = await self.context.handle_external_input(
                external_input, endpoint_context={"mcp_client_id": client_id}
            )

            # Register Future, Queue, and buffers for this task
            self.task_futures[task_id] = task_future
            self.task_queues[task_id] = stream_queue
            self.task_buffers[task_id] = []
            self.active_tasks[task_id] = tool_name

            # Report submission to MCP client
            await mcp_context.info(f"Task {task_id} submitted to agent {agent_name}")

            # Start consumer coroutine to stream updates from queue to MCP client
            async def stream_consumer():
                """
                Consume chunks from the queue and stream them to the MCP client.
                Accumulates non-text content objects for final return.
                This runs in the MCP request context, so mcp_context is valid here.
                """
                content_objects = []

                if not config.stream_responses:
                    log.debug(f"Streaming disabled for task {task_id}")
                    return content_objects

                try:
                    while True:
                        # Wait for next chunk from the queue
                        chunk = await stream_queue.get()

                        # Check for sentinel (completion signal)
                        if chunk is STREAM_COMPLETE:
                            log.debug(
                                f"Stream consumer for task {task_id} received completion signal"
                            )
                            break

                        # Handle different chunk types
                        if isinstance(chunk, str):
                            # Text chunk - stream as info
                            try:
                                await mcp_context.info(chunk)
                            except Exception as e:
                                log.warning(
                                    f"Failed to stream text chunk to MCP client: {e}"
                                )
                        else:
                            # Content object (ImageContent, AudioContent, ResourceLink, EmbeddedResource)
                            # Don't stream these, accumulate for final return
                            content_objects.append(chunk)
                            # Optionally notify about the content
                            try:
                                content_type = getattr(chunk, "type", "content")
                                if content_type == "image":
                                    await mcp_context.info(f"📷 Image attached")
                                elif content_type == "audio":
                                    await mcp_context.info(f"🎵 Audio attached")
                                elif content_type == "resource_link":
                                    await mcp_context.info(
                                        f"📎 File available: {getattr(chunk, 'name', 'file')}"
                                    )
                                elif content_type == "resource":
                                    await mcp_context.info(f"📄 Resource embedded")
                            except Exception as e:
                                log.warning(
                                    f"Failed to notify about content object: {e}"
                                )

                        stream_queue.task_done()

                except asyncio.CancelledError:
                    log.debug(f"Stream consumer for task {task_id} was cancelled")
                except Exception as e:
                    log.error(
                        f"Error in stream consumer for task {task_id}: {e}",
                        exc_info=True,
                    )

                return content_objects

            # Start consumer in background
            consumer_task = asyncio.create_task(stream_consumer())

            # Wait for the task to complete (with timeout)
            try:
                result_text = await asyncio.wait_for(
                    task_future, timeout=config.task_timeout_seconds
                )

                # Wait for consumer to finish and get accumulated content objects
                try:
                    content_objects = await asyncio.wait_for(consumer_task, timeout=5.0)
                except asyncio.TimeoutError:
                    log.warning(f"Consumer for task {task_id} did not finish in time")
                    consumer_task.cancel()
                    content_objects = []

                # Build final response
                if content_objects:
                    # We have mixed content - return as list
                    final_content = []

                    # Add text first if present
                    if result_text and result_text.strip():
                        final_content.append(TextContent(type="text", text=result_text))

                    # Add all content objects (images, audio, resources, etc.)
                    final_content.extend(content_objects)

                    log.info(
                        f"Task {task_id} completed with {len(final_content)} content parts"
                    )
                    return final_content
                else:
                    # Text-only response
                    log.info(
                        f"Task {task_id} completed successfully, returned {len(result_text)} chars"
                    )
                    return result_text

            except asyncio.TimeoutError:
                error_msg = f"Task {task_id} timed out after {config.task_timeout_seconds} seconds"
                log.error(error_msg)
                await mcp_context.error(error_msg)

                # Signal consumer to stop
                try:
                    await stream_queue.put(STREAM_COMPLETE)
                except:
                    pass
                consumer_task.cancel()

                self._cleanup_task(task_id)
                return f"Error: {error_msg}"

        except PermissionError as e:
            # Authentication/authorization error - provide clear OAuth guidance
            error_msg = f"Authentication required: {str(e)}"
            log.warning("Authentication failed for MCP tool call: %s", e)

            # Send error notification to client
            await mcp_context.error(error_msg)

            # Check if OAuth is configured
            if config.enable_auth and not config.dev_mode:
                # Provide OAuth endpoints in error message for client guidance
                oauth_metadata_url = f"http://{config.host}:{config.port}/.well-known/oauth-authorization-server"
                oauth_authorize_url = f"http://{config.host}:{config.port}/oauth/authorize"

                detailed_error = (
                    f"Authentication required. This MCP server requires OAuth authentication.\n\n"
                    f"To authenticate:\n"
                    f"1. Visit: {oauth_authorize_url}\n"
                    f"2. Complete the OAuth flow\n"
                    f"3. Use the returned access token in your MCP client configuration\n\n"
                    f"OAuth metadata: {oauth_metadata_url}\n\n"
                    f"Original error: {str(e)}"
                )
                return detailed_error
            else:
                return f"Error: {error_msg}"

        except Exception as e:
            error_msg = f"Error invoking agent {agent_name}: {str(e)}"
            log.exception(error_msg)
            await mcp_context.error(error_msg)
            return f"Error: {error_msg}"

        finally:
            # Cleanup queue (only if task_id was assigned)
            if task_id and task_id in self.task_queues:
                del self.task_queues[task_id]

    async def _run_mcp_server(self):
        """Start the FastMCP server with configured transport."""
        config: McpAdapterConfig = self.context.adapter_config

        try:
            if config.transport == "http":
                log.info(
                    "Starting MCP server on HTTP transport at %s:%d",
                    config.host,
                    config.port,
                )

                # Get the underlying Starlette app and add OAuth routes if auth enabled
                # For triple-redirect flow, MCP adapter handles OAuth directly (no auth_handler needed)
                log.info("OAuth endpoint check: enable_auth=%s", config.enable_auth)

                if config.enable_auth:
                    from starlette.routing import Route

                    # Create the HTTP app
                    http_app = self.mcp_server.http_app(transport="http")

                    # Add OAuth routes to the Starlette app
                    # These routes implement the triple-redirect OAuth flow
                    oauth_routes = [
                        Route(
                            "/oauth/authorize",
                            self._handle_oauth_authorize,
                            methods=["GET"],
                        ),
                        Route(
                            "/oauth/callback",
                            self._handle_oauth_callback,
                            methods=["GET"],
                        ),
                        Route(
                            "/oauth/token",
                            self._handle_oauth_token,
                            methods=["POST"],
                        ),
                        Route(
                            "/oauth/register",
                            self._handle_oauth_register,
                            methods=["POST"],
                        ),
                        Route(
                            "/.well-known/oauth-authorization-server",
                            self._handle_oauth_metadata,
                            methods=["GET"],
                        ),
                    ]

                    # Add routes to the app
                    http_app.router.routes.extend(oauth_routes)
                    log.info("Added OAuth endpoints to HTTP server (triple-redirect flow via WebUI proxy)")

                    # Debug: Log all registered routes
                    log.info("All registered routes:")
                    for route in http_app.router.routes:
                        if hasattr(route, 'path'):
                            log.info("  - %s %s", getattr(route, 'methods', ['GET']), route.path)

                    # Run with uvicorn directly since we customized the app
                    import uvicorn
                    uvicorn_config = uvicorn.Config(
                        http_app,
                        host=config.host,
                        port=config.port,
                        log_level="info",
                    )
                    server = uvicorn.Server(uvicorn_config)
                    await server.serve()
                else:
                    # Run normally without OAuth routes
                    await asyncio.to_thread(
                        self.mcp_server.run,
                        transport="http",
                        host=config.host,
                        port=config.port,
                    )
            elif config.transport == "stdio":
                log.info("Starting MCP server on stdio transport")
                # Run in a thread pool to avoid blocking
                await asyncio.to_thread(self.mcp_server.run, transport="stdio")
            else:
                log.error("Unknown transport: %s", config.transport)
        except Exception as e:
            log.exception("Error running MCP server: %s", e)

    async def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        log.info("Cleaning up MCP Gateway Adapter...")
        # FastMCP handles cleanup internally
        self.active_tasks.clear()
        self.task_buffers.clear()
        self.task_futures.clear()
        self.task_errors.clear()
        self.task_queues.clear()
        self.session_artifacts.clear()
        self.agent_to_tools.clear()

    def _cleanup_task(self, task_id: str) -> None:
        """
        Clean up all state for a completed or failed task.

        Args:
            task_id: The ID of the task to clean up
        """
        if task_id in self.task_futures:
            del self.task_futures[task_id]
        if task_id in self.task_buffers:
            del self.task_buffers[task_id]
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
        if task_id in self.task_errors:
            del self.task_errors[task_id]
        if task_id in self.task_queues:
            del self.task_queues[task_id]

    # --- File and Resource Handling Helper Methods ---

    def _determine_content_type(
        self, file_part: SamFilePart, config: McpAdapterConfig
    ) -> Literal["image", "audio", "text_embedded", "blob_embedded", "resource_link"]:
        """
        Determines how to return a file based on type and size.

        Returns:
            - "image": Return as ImageContent
            - "audio": Return as AudioContent
            - "text_embedded": Return as EmbeddedResource with TextResourceContents
            - "blob_embedded": Return as EmbeddedResource with BlobResourceContents
            - "resource_link": Return as ResourceLink (register as MCP resource)
        """
        mime_type = file_part.mime_type or "application/octet-stream"
        size = len(file_part.content_bytes) if file_part.content_bytes else 0

        # Image handling
        if mime_type.startswith("image/"):
            if size <= config.inline_image_max_bytes:
                return "image"
            else:
                return "resource_link"

        # Audio handling
        if mime_type.startswith("audio/"):
            if size <= config.inline_audio_max_bytes:
                return "audio"
            else:
                return "resource_link"

        # Text file handling - use existing helper!
        if is_text_based_file(mime_type, file_part.content_bytes):
            if size <= config.inline_text_max_bytes:
                return "text_embedded"
            else:
                return "resource_link"

        # Other binary
        if size <= config.inline_binary_max_bytes:
            return "blob_embedded"
        else:
            return "resource_link"

    async def _load_file_content_if_needed(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> bytes:
        """Loads file content from artifact service if not already present."""
        if file_part.content_bytes:
            return file_part.content_bytes

        # Load from artifact service
        content = await self.context.load_artifact_content(
            context=context, filename=file_part.name, version="latest"
        )

        if not content:
            raise ValueError(f"Failed to load content for {file_part.name}")

        return content

    async def _create_image_content(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> ImageContent:
        """Creates MCP ImageContent from file part."""
        content = await self._load_file_content_if_needed(file_part, context)

        return ImageContent(
            type="image",
            data=base64.b64encode(content).decode("utf-8"),
            mimeType=file_part.mime_type or "image/png",
        )

    async def _create_audio_content(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> AudioContent:
        """Creates MCP AudioContent from file part."""
        content = await self._load_file_content_if_needed(file_part, context)

        return AudioContent(
            type="audio",
            data=base64.b64encode(content).decode("utf-8"),
            mimeType=file_part.mime_type or "audio/mpeg",
        )

    async def _create_text_embedded_resource(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> EmbeddedResource:
        """Creates MCP EmbeddedResource with TextResourceContents."""
        content = await self._load_file_content_if_needed(file_part, context)
        text = content.decode("utf-8")

        # Use session-scoped URI
        uri = f"{self.context.adapter_config.resource_uri_prefix}://{context.session_id}/{file_part.name}"

        return EmbeddedResource(
            type="resource",
            resource=TextResourceContents(
                uri=uri, mimeType=file_part.mime_type, text=text
            ),
        )

    async def _create_blob_embedded_resource(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> EmbeddedResource:
        """Creates MCP EmbeddedResource with BlobResourceContents."""
        content = await self._load_file_content_if_needed(file_part, context)

        uri = f"{self.context.adapter_config.resource_uri_prefix}://{context.session_id}/{file_part.name}"

        return EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(
                uri=uri,
                mimeType=file_part.mime_type,
                blob=base64.b64encode(content).decode("utf-8"),
            ),
        )

    async def _create_resource_link(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> ResourceLink:
        """Registers file as MCP resource and returns ResourceLink."""
        # Register the resource
        resource_name, uri, size = await self._register_artifact_resource(
            file_part, context
        )

        return ResourceLink(
            type="resource_link",
            uri=uri,
            name=file_part.name,
            description=f"Artifact: {file_part.name}",
            mimeType=file_part.mime_type,
            size=size,
        )

    async def _register_artifact_resource(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> tuple[str, str, Optional[int]]:
        """
        Registers an artifact as available via the MCP resource template.

        This doesn't create individual resources, but tracks the artifact
        so it can be discovered via list_resources and accessed via the template.

        Returns:
            (resource_name, uri, size)
        """
        session_id = context.session_id
        filename = file_part.name

        # Build URI that matches our resource template
        uri = f"{self.context.adapter_config.resource_uri_prefix}://{session_id}/{filename}"

        # Get size
        if file_part.content_bytes:
            size = len(file_part.content_bytes)
        else:
            # Will be loaded on demand
            size = None

        # Track this artifact for the session with metadata (for list_resources)
        if session_id not in self.session_artifacts:
            self.session_artifacts[session_id] = {}

        self.session_artifacts[session_id][filename] = {
            "uri": uri,
            "mime_type": file_part.mime_type or "application/octet-stream",
            "size": size,
            "user_id": context.user_id,
        }

        # Also register as a concrete resource for discoverability via list_resources
        # This allows MCP clients to discover artifacts without knowing filenames in advance
        try:
            # Create a closure that captures session_id and filename
            async def concrete_resource_handler():
                return await self._handle_artifact_resource_read(session_id, filename)

            # Register the concrete resource with FastMCP
            self.mcp_server.add_resource_fn(
                fn=concrete_resource_handler,
                uri=uri,
                name=f"{session_id}_{filename}",
                description=f"Artifact: {filename}",
                mime_type=file_part.mime_type,
            )
            log.debug(f"Registered concrete resource: {uri}")
        except Exception as e:
            log.warning(f"Failed to register concrete resource for {uri}: {e}")

        log.info(
            f"Registered artifact for session {session_id}: {filename} (URI: {uri})"
        )
        return filename, uri, size

    async def _handle_artifact_resource_read(self, session_id: str, filename: str):
        """
        Handles MCP resource read requests for artifacts.

        Args:
            session_id: The session ID from the URI
            filename: The filename from the URI

        Returns:
            TextResourceContents or BlobResourceContents for FastMCP
        """
        config: McpAdapterConfig = self.context.adapter_config

        # Check if this artifact exists for this session
        if (
            session_id not in self.session_artifacts
            or filename not in self.session_artifacts[session_id]
        ):
            raise ValueError(f"Artifact not found: {filename} in session {session_id}")

        # Get artifact metadata
        artifact_metadata = self.session_artifacts[session_id][filename]
        user_id = artifact_metadata.get("user_id", config.default_user_identity)
        mime_type = artifact_metadata.get("mime_type", "application/octet-stream")

        # Create a ResponseContext for loading
        response_context = ResponseContext(
            task_id="resource-read",
            session_id=session_id,
            user_id=user_id,
            platform_context={},
        )

        # Load artifact content from the artifact service
        content = await self.context.load_artifact_content(
            context=response_context, filename=filename, version="latest"
        )

        if not content:
            raise ValueError(f"Failed to load artifact content: {filename}")

        # Build URI
        uri = artifact_metadata.get(
            "uri", f"{config.resource_uri_prefix}://{session_id}/{filename}"
        )

        # Return based on whether it's text or binary
        if is_text_based_file(mime_type, content):
            return TextResourceContents(
                uri=uri, mimeType=mime_type, text=content.decode("utf-8")
            )
        else:
            return BlobResourceContents(
                uri=uri,
                mimeType=mime_type,
                blob=base64.b64encode(content).decode("utf-8"),
            )

    def _deregister_session_artifacts(self, session_id: str):
        """Clears artifact tracking for a session."""
        if session_id not in self.session_artifacts:
            return

        artifact_count = len(self.session_artifacts[session_id])
        log.info(f"Clearing {artifact_count} artifact(s) for session {session_id}")

        del self.session_artifacts[session_id]

    def get_session_artifacts(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get a list of all artifacts for a given session.

        This is useful for debugging and can also be exposed via a tool/API.

        Args:
            session_id: The session ID (e.g., "mcp-client-abc123")

        Returns:
            List of artifact metadata dicts with uri, filename, mime_type, size
        """
        if session_id not in self.session_artifacts:
            return []

        artifacts = []
        for filename, metadata in self.session_artifacts[session_id].items():
            artifacts.append(
                {
                    "filename": filename,
                    "uri": metadata.get("uri"),
                    "mime_type": metadata.get("mime_type"),
                    "size": metadata.get("size"),
                }
            )

        return artifacts

    # --- Required GatewayAdapter Methods ---

    # NOTE: extract_auth_claims() has been removed!
    # Authentication is now handled by enterprise auth in generic gateway.
    # The MCP adapter just stores _current_mcp_context for enterprise extractors.
    # See: solace_agent_mesh_enterprise.gateway.auth.authenticate_request()

    async def prepare_task(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """
        Convert MCP tool invocation into a SamTask.

        Args:
            external_input: Dict with tool_name, agent_name, skill_id, message, mcp_client_id
            endpoint_context: Optional context with mcp_client_id

        Returns:
            SamTask ready for submission to SAM agent
        """
        agent_name = external_input.get("agent_name")
        message = external_input.get("message", "")
        tool_name = external_input.get("tool_name", "")
        mcp_client_id = external_input.get("mcp_client_id")

        if not agent_name:
            raise ValueError("Missing agent_name in external_input")

        if not message.strip():
            raise ValueError("Empty message")

        if not mcp_client_id:
            raise ValueError("Missing mcp_client_id in external_input")

        # Use connection-based session ID (persistent across tool calls)
        # This allows artifacts to accumulate and be accessible across multiple tool invocations
        session_id = f"mcp-client-{mcp_client_id}"

        # Create a simple text task with RUN_BASED behavior
        return SamTask(
            parts=[self.context.create_text_part(message)],
            session_id=session_id,
            target_agent=agent_name,
            is_streaming=True,
            session_behavior="RUN_BASED",  # No chat history between calls
            platform_context={
                "tool_name": tool_name,
                "mcp_client_id": mcp_client_id,
            },
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """
        Handle streaming updates from SAM agent.

        This puts chunks into the task's queue for the stream consumer to send.
        """
        task_id = context.task_id
        config: McpAdapterConfig = self.context.adapter_config

        # Get the queue for this task (if it exists)
        stream_queue = self.task_queues.get(task_id)

        for part in update.parts:
            if isinstance(part, SamTextPart):
                # Buffer text for final response
                if task_id not in self.task_buffers:
                    self.task_buffers[task_id] = []
                self.task_buffers[task_id].append(part.text)

                # Stream to MCP client via queue if enabled
                if config.stream_responses and stream_queue:
                    try:
                        stream_queue.put_nowait(part.text)
                    except Exception as e:
                        log.warning(
                            "Failed to queue text chunk for task %s: %s", task_id, e
                        )

            elif isinstance(part, SamFilePart):
                log.info("Received file part: %s", part.name)

                # Determine how to return this file
                content_type = self._determine_content_type(part, config)

                # Create appropriate content based on type
                content_obj = None
                try:
                    if content_type == "image":
                        content_obj = await self._create_image_content(part, context)
                    elif content_type == "audio":
                        content_obj = await self._create_audio_content(part, context)
                    elif content_type == "text_embedded":
                        content_obj = await self._create_text_embedded_resource(
                            part, context
                        )
                    elif content_type == "blob_embedded":
                        content_obj = await self._create_blob_embedded_resource(
                            part, context
                        )
                    elif content_type == "resource_link":
                        content_obj = await self._create_resource_link(part, context)
                except Exception as e:
                    log.error(
                        f"Failed to create {content_type} content for {part.name}: {e}",
                        exc_info=True,
                    )
                    # Fallback to simple notification
                    if stream_queue:
                        try:
                            stream_queue.put_nowait(
                                f"⚠️ Failed to process file: {part.name}"
                            )
                        except Exception as queue_err:
                            log.warning(
                                f"Failed to queue error notification: {queue_err}"
                            )
                    continue

                # Queue the content object for streaming
                if content_obj and stream_queue:
                    try:
                        stream_queue.put_nowait(content_obj)
                        log.debug(f"Queued {content_type} content for {part.name}")
                    except Exception as e:
                        log.warning(
                            f"Failed to queue {content_type} for task {task_id}: {e}"
                        )

            elif isinstance(part, SamDataPart):
                # Handle special data types
                data_type = part.data.get("type")

                if data_type == "agent_progress_update":
                    status = part.data.get("status_text", "")
                    if stream_queue and status:
                        try:
                            stream_queue.put_nowait(f"Status: {status}")
                        except Exception as e:
                            log.warning("Failed to queue status update: %s", e)

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """
        Handle task completion.

        This method:
        1. Assembles the final response from buffered text chunks
        2. Signals stream completion via queue
        3. Resolves the Future (unblocking _handle_tool_call)
        4. Cleans up all task state
        """
        task_id = context.task_id

        # Assemble final response from buffer
        response_text = "".join(self.task_buffers.get(task_id, []))

        # If empty, provide a default message
        if not response_text.strip():
            response_text = "Task completed successfully (no text response)"

        # Signal stream completion to consumer
        if task_id in self.task_queues:
            try:
                await self.task_queues[task_id].put(STREAM_COMPLETE)
                log.debug("Sent STREAM_COMPLETE signal for task %s", task_id)
            except Exception as e:
                log.warning(
                    "Failed to signal stream completion for task %s: %s", task_id, e
                )

        # Resolve the Future - this unblocks _handle_tool_call()
        if task_id in self.task_futures:
            future = self.task_futures[task_id]
            if not future.done():
                future.set_result(response_text)
                log.info(
                    "Task %s completed, returned %d chars to MCP client",
                    task_id,
                    len(response_text),
                )
            else:
                log.warning("Task %s Future was already resolved", task_id)
        else:
            log.warning(
                "Task %s completed but no Future found (may have timed out)", task_id
            )

        # NOTE: Resources are NOT cleaned up here - they persist for the connection lifetime
        # This allows MCP clients to fetch ResourceLinks after task completion

        # Clean up all task state
        self._cleanup_task(task_id)

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """
        Handle errors from SAM.

        This method:
        1. Formats the error message
        2. Signals stream completion via queue
        3. Resolves the Future with the error message (unblocking _handle_tool_call)
        4. Cleans up all task state
        """
        task_id = context.task_id

        # Format error message based on category
        if error.category == "CANCELED":
            error_msg = "Task was canceled"
        else:
            error_msg = f"Error: {error.message}"

        # Signal stream completion to consumer
        if task_id in self.task_queues:
            try:
                await self.task_queues[task_id].put(STREAM_COMPLETE)
                log.debug("Sent STREAM_COMPLETE signal for failed task %s", task_id)
            except Exception as e:
                log.warning(
                    "Failed to signal stream completion for failed task %s: %s",
                    task_id,
                    e,
                )

        # Resolve the Future with error message - this unblocks _handle_tool_call()
        if task_id in self.task_futures:
            future = self.task_futures[task_id]
            if not future.done():
                # Return error message as the result (not raising exception)
                future.set_result(error_msg)
                log.error(
                    "Task %s failed with %s: %s", task_id, error.category, error.message
                )
            else:
                log.warning("Task %s Future was already resolved before error", task_id)
        else:
            log.warning(
                "Task %s failed but no Future found (may have timed out)", task_id
            )

        # Clean up all task state
        self._cleanup_task(task_id)

    # --- Agent Registry Change Handlers ---

    async def handle_agent_registered(self, agent_card: AgentCard) -> None:
        """
        Dynamically register new MCP tools when agents come online.

        This method is called when a new agent publishes its AgentCard.
        It registers MCP tools for each of the agent's skills.

        Args:
            agent_card: The AgentCard of the newly registered agent
        """
        log.info(
            "Agent %s registered with %d skills, adding tools to MCP server...",
            agent_card.name,
            len(agent_card.skills) if agent_card.skills else 0,
        )

        if not agent_card.skills:
            log.debug(f"Agent {agent_card.name} has no skills, no tools to register")
            return

        # Track which tools we register for this agent
        tool_names = []

        for skill in agent_card.skills:
            tool_name = sanitize_tool_name(f"{agent_card.name}_{skill.name}")
            tool_names.append(tool_name)

            # Register the tool (this handles duplicates)
            self._register_tool_for_skill(agent_card, skill)

        # Store mapping for later removal
        self.agent_to_tools[agent_card.name] = tool_names

        log.info(
            "Successfully registered %d MCP tools for agent %s: %s",
            len(tool_names),
            agent_card.name,
            ", ".join(tool_names),
        )

    async def handle_agent_deregistered(self, agent_name: str) -> None:
        """
        Remove MCP tools when agent goes offline.

        This method is called when an agent is removed from the registry
        (e.g., due to TTL expiry). It removes all tools associated with
        that agent from the MCP server.

        Args:
            agent_name: Name of the agent that was removed
        """
        if agent_name not in self.agent_to_tools:
            log.debug(f"Agent {agent_name} deregistered but had no registered tools")
            return

        tool_names = self.agent_to_tools[agent_name]
        log.info(
            "Agent %s deregistered, removing %d MCP tools...",
            agent_name,
            len(tool_names),
        )

        for tool_name in tool_names:
            try:
                # Use FastMCP's remove_tool method
                # This automatically sends notification to connected MCP clients
                self.mcp_server.remove_tool(tool_name)

                # Clean up mapping
                if tool_name in self.tool_to_agent_map:
                    del self.tool_to_agent_map[tool_name]

                log.debug(f"Removed MCP tool: {tool_name}")

            except Exception as e:
                log.error(f"Failed to remove tool {tool_name}: {e}", exc_info=True)

        # Clean up agent mapping
        del self.agent_to_tools[agent_name]

        log.info(
            "Successfully removed all tools for agent %s",
            agent_name,
        )
