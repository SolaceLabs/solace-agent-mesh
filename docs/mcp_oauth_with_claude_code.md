# MCP OAuth with Claude Code: Triple-Redirect Flow

## Overview

This document describes the OAuth 2.0 authentication flow for the MCP (Model Context Protocol) gateway when used with Claude Code. This flow enables secure, multi-user authentication where each Claude Code instance manages its own OAuth tokens.

The MCP gateway implements a **triple-redirect OAuth flow** that builds upon SAM's double-redirect pattern by adding an additional redirect to handle Claude Code's OAuth requirements.

## Why Triple-Redirect?

The MCP gateway has unique requirements that necessitate a triple-redirect flow:

1. **Claude Code manages tokens:** Unlike browser-based gateways, Claude Code (the desktop app) stores tokens locally and sends them with every request
2. **Desktop app callback:** The final redirect must go to `http://127.0.0.1:<port>/callback` where Claude Code is listening
3. **Stateless validation:** The MCP gateway validates tokens per-request and does NOT store them server-side
4. **Multi-user isolation:** Each Claude Code instance has its own tokens, preventing cross-user contamination

## Architecture

### Triple-Redirect OAuth Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│Claude Code  │    │     MCP     │    │    WebUI    │    │  Azure AD   │    │   OAuth2    │
│  (Desktop)  │    │   Gateway   │    │   (Proxy)   │    │             │    │   Service   │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │                  │                  │
       │ 1. User clicks   │                  │                  │                  │
       │    "Connect" on  │                  │                  │                  │
       │    MCP server    │                  │                  │                  │
       │                  │                  │                  │                  │
       │ 2. GET /oauth/authorize?                               │                  │
       │    redirect_uri=http://127.0.0.1:PORT/callback         │                  │
       │    &state=CC_STATE&code_challenge=PKCE                 │                  │
       ├─────────────────>│                  │                  │                  │
       │                  │                  │                  │                  │
       │                  │ 3. Redirect to WebUI                │                  │
       │                  │    /gateway-oauth/authorize?        │                  │
       │                  │    gateway_uri=http://mcp:8000/oauth/callback          │
       │                  │    &state=INTERNAL_STATE            │                  │
       │<─────────────────┤                  │                  │                  │
       │                  │                  │                  │                  │
       │ 4. GET /gateway-oauth/authorize?                       │                  │
       │    gateway_uri=http://mcp:8000/oauth/callback          │                  │
       │    &state=INTERNAL_STATE            │                  │                  │
       ├────────────────────────────────────>│                  │                  │
       │                  │                  │                  │                  │
       │                  │                  │ 5. Redirect to /auth/login          │
       │<────────────────────────────────────┤                  │                  │
       │                  │                  │                  │                  │
       │ 6. GET /auth/login                  │                  │                  │
       ├────────────────────────────────────>│                  │                  │
       │                  │                  │                  │                  │
       │                  │                  │ 7. Redirect to Azure AD             │
       │<────────────────────────────────────┤                  │                  │
       │                  │                  │                  │                  │
       │ 8. User authenticates with Azure AD                    │                  │
       ├───────────────────────────────────────────────────────>│                  │
       │                  │                  │                  │                  │
       │ 9. Redirect to WebUI callback                          │                  │
       │<───────────────────────────────────────────────────────┤                  │
       │                  │                  │                  │                  │
       │ 10. GET /auth/callback?code=AZURE_CODE                 │                  │
       ├────────────────────────────────────>│                  │                  │
       │                  │                  │                  │                  │
       │                  │                  │ 11. Exchange code for tokens        │
       │                  │                  │    (server-to-server)               │
       │                  │                  ├────────────────────────────────────>│
       │                  │                  │                  │                  │
       │                  │                  │ 12. Return access_token & refresh   │
       │                  │                  │<────────────────────────────────────┤
       │                  │                  │                  │                  │
       │ 13. Redirect to MCP callback with gateway_code         │                  │
       │     GET http://mcp:8000/oauth/callback?                │                  │
       │     code=GATEWAY_CODE&state=INTERNAL_STATE             │                  │
       │<────────────────────────────────────┤                  │                  │
       │                  │                  │                  │                  │
       │ 14. GET /oauth/callback?code=GATEWAY_CODE              │                  │
       │                  │    &state=INTERNAL_STATE            │                  │
       ├─────────────────>│                  │                  │                  │
       │                  │                  │                  │                  │
       │                  │ 15. Exchange gateway_code for tokens                   │
       │                  │    (server-to-server)               │                  │
       │                  ├─────────────────>│                  │                  │
       │                  │                  │                  │                  │
       │                  │ 16. Return access_token & refresh   │                  │
       │                  │<─────────────────┤                  │                  │
       │                  │                  │                  │                  │
       │ 17. Redirect to Claude Code callback                   │                  │
       │     with authorization_code         │                  │                  │
       │     GET http://127.0.0.1:PORT/callback?                │                  │
       │     code=MCP_AUTH_CODE&state=CC_STATE│                 │                  │
       │<─────────────────┤                  │                  │                  │
       │                  │                  │                  │                  │
       │ 18. POST /oauth/token               │                  │                  │
       │     grant_type=authorization_code   │                  │                  │
       │     code=MCP_AUTH_CODE              │                  │                  │
       │     code_verifier=PKCE_VERIFIER     │                  │                  │
       ├─────────────────>│                  │                  │                  │
       │                  │                  │                  │                  │
       │ 19. Return access_token & refresh_token                │                  │
       │<─────────────────┤                  │                  │                  │
       │                  │                  │                  │                  │
       │ [DONE: Claude Code stores tokens locally]              │                  │
       │                  │                  │                  │                  │
```

### Subsequent Tool Calls (Stateless Validation)

After the initial OAuth flow, every MCP tool call includes the access token:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│Claude Code  │    │     MCP     │    │   OAuth2    │
│  (Desktop)  │    │   Gateway   │    │   Service   │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       │ POST /tools/call │                  │
       │ Authorization: Bearer ACCESS_TOKEN  │
       │ {tool: "agent_foo", params: {...}}  │
       ├─────────────────>│                  │
       │                  │                  │
       │                  │ Validate token   │
       │                  ├─────────────────>│
       │                  │                  │
       │                  │ Token valid +    │
       │                  │ user_info        │
       │                  │<─────────────────┤
       │                  │                  │
       │                  │ Execute tool as  │
       │                  │ authenticated    │
       │                  │ user             │
       │                  │                  │
       │ Tool result      │                  │
       │<─────────────────┤                  │
```

## Configuration

### 1. WebUI Configuration (OAuth Proxy)

The WebUI must include the MCP gateway's callback URI in its whitelist:

```yaml
# WebUI configuration
gateway_oauth_proxy:
  enabled: true
  allowed_redirect_uris:
    - "http://localhost:8000/oauth/callback"  # MCP gateway callback
    - "http://mcp-gateway.example.com/oauth/callback"
  gateway_code_ttl_seconds: 300  # 5 minutes
```

### 2. MCP Gateway Configuration

The MCP gateway must be configured with:
- OAuth enabled
- HTTP transport (required for OAuth)
- WebUI proxy URL
- User ID claim preference

```yaml
# MCP gateway configuration
adapter_config:
  mcp_server_name: "SAM MCP Gateway"
  transport: "http"
  port: 8000
  host: "0.0.0.0"

  # OAuth configuration
  enable_auth: true
  dev_mode: false  # NEVER enable in production
  external_auth_service_url: "http://localhost:8050"  # OAuth2 service
  external_auth_provider: "azure"
  oauth_proxy_url: "http://localhost:8000"  # WebUI URL

  # User identification (for audit logs)
  user_id_claim: "email"  # Options: "email", "sub", "upn", "preferred_username"

  # Optional: Session secret for OAuth state management
  session_secret_key: "your-secret-key"  # Auto-generated if not provided
```

### 3. Claude Code Configuration

Users configure the MCP server in Claude Code's settings:

```json
{
  "mcpServers": {
    "sam": {
      "url": "http://localhost:8000",
      "transport": "http"
    }
  }
}
```

When the user clicks "Connect" on the MCP server, Claude Code:
1. Calls `/.well-known/oauth-authorization-server` to discover OAuth endpoints
2. Registers as an OAuth client via `/oauth/register`
3. Initiates the OAuth flow via `/oauth/authorize`
4. Stores tokens locally after successful authentication
5. Sends tokens with every subsequent `/tools/call` request

## Implementation Details

### MCP Gateway (Triple-Redirect)

The MCP gateway implements the triple-redirect flow in `/src/solace_agent_mesh/gateway/mcp/adapter.py`:

#### `/oauth/authorize` - Initiates Triple-Redirect

```python
async def _handle_oauth_authorize(self, request):
    # Extract Claude Code's OAuth request
    redirect_uri = request.query_params.get("redirect_uri")  # CC's callback
    state = request.query_params.get("state")  # CC's CSRF token
    code_challenge = request.query_params.get("code_challenge")  # PKCE

    # Store CC's request in session
    internal_state = secrets.token_urlsafe(32)
    request.session["cc_redirect_uri"] = redirect_uri
    request.session["cc_state"] = state
    request.session["cc_code_challenge"] = code_challenge
    request.session["internal_state"] = internal_state

    # Redirect to WebUI OAuth proxy
    mcp_callback = f"http://{config.host}:{config.port}/oauth/callback"
    proxy_url = f"{config.oauth_proxy_url}/api/v1/gateway-oauth/authorize?gateway_uri={mcp_callback}&state={internal_state}"

    return RedirectResponse(url=proxy_url, status_code=302)
```

#### `/oauth/callback` - Handles Gateway Code from WebUI

```python
async def _handle_oauth_callback(self, request):
    # Validate state (CSRF protection)
    gateway_code = request.query_params.get("code")
    returned_state = request.query_params.get("state")
    expected_state = request.session.get("internal_state")

    if returned_state != expected_state:
        raise ValueError("State mismatch")

    # Exchange gateway code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.oauth_proxy_url}/api/v1/gateway-oauth/exchange",
            json={"code": gateway_code, "gateway_uri": mcp_callback_uri}
        )
        tokens = response.json()

    # Generate authorization code for Claude Code
    authorization_code = secrets.token_urlsafe(32)
    self.oauth_codes[authorization_code] = {
        'access_token': tokens['access_token'],
        'refresh_token': tokens['refresh_token'],
        'created_at': time.time(),
        'code_challenge': request.session.get("cc_code_challenge"),
        'redirect_uri': request.session.get("cc_redirect_uri"),
        'ttl_seconds': 300
    }

    # Redirect to Claude Code with authorization code
    cc_redirect_uri = request.session.get("cc_redirect_uri")
    cc_state = request.session.get("cc_state")
    redirect_url = f"{cc_redirect_uri}?code={authorization_code}&state={cc_state}"

    return RedirectResponse(url=redirect_url, status_code=302)
```

#### `/oauth/token` - Exchanges Authorization Code for Tokens

```python
async def _handle_oauth_token(self, request):
    body = await request.form()
    code = body.get("code")
    redirect_uri = body.get("redirect_uri")
    code_verifier = body.get("code_verifier")

    # Look up authorization code
    code_data = self.oauth_codes[code]

    # Validate redirect_uri
    if redirect_uri != code_data['redirect_uri']:
        raise ValueError("Redirect URI mismatch")

    # Validate PKCE
    if code_data.get('code_challenge'):
        computed_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip('=')

        if computed_challenge != code_data['code_challenge']:
            raise ValueError("Invalid code_verifier")

    # Return tokens (one-time use, delete code)
    tokens = {
        'access_token': code_data['access_token'],
        'refresh_token': code_data['refresh_token'],
        'token_type': 'Bearer',
        'expires_in': 3600
    }
    del self.oauth_codes[code]

    return JSONResponse(tokens)
```

### Token Validation (Stateless, Per-Request)

The MCP gateway validates tokens on every `/tools/call` request:

```python
async def extract_auth_claims(self, external_input, endpoint_context):
    config = self.context.adapter_config

    # Extract Bearer token from request
    access_token = oauth_utils.extract_bearer_token_from_dict(
        external_input,
        token_keys=["Authorization", "authorization", "access_token", "token"],
    )

    if not access_token:
        raise PermissionError("No Bearer token provided")

    # Validate token with OAuth2 service
    claims = await oauth_utils.validate_and_create_auth_claims(
        auth_service_url=config.external_auth_service_url,
        auth_provider=config.external_auth_provider,
        access_token=access_token,
        source="mcp",
        preferred_user_id_claim=config.user_id_claim,
    )

    return claims
```

## User ID Configuration

The `user_id_claim` config field controls which OAuth claim is used for audit logging:

| Claim | Type | Example | Use Case |
|-------|------|---------|----------|
| `email` | Email address | `user@example.com` | Human-readable, recommended for most cases |
| `sub` | GUID | `a1b2c3d4-...` | Stable across email changes, but not human-readable |
| `upn` | User Principal Name | `user@tenant.onmicrosoft.com` | Azure AD specific |
| `preferred_username` | Username | `user@example.com` | Azure AD, similar to email |

**Recommendation:** Use `"email"` for human-readable audit logs unless email addresses change frequently in your organization.

## Security Considerations

### Multi-User Isolation

Each Claude Code instance stores its own tokens locally. This ensures:
- User A's tokens are never mixed with User B's tokens
- Server-side token storage is unnecessary
- Each user maintains their own authentication state

### Stateless Validation

The MCP gateway validates tokens per-request by calling the OAuth2 service. This:
- Prevents stale token issues
- Allows immediate token revocation
- Eliminates server-side session state

### PKCE (Proof Key for Code Exchange)

Claude Code uses PKCE to prevent authorization code interception:
1. Generates `code_verifier` (random string)
2. Computes `code_challenge = BASE64URL(SHA256(code_verifier))`
3. Sends `code_challenge` in `/oauth/authorize` request
4. Sends `code_verifier` in `/oauth/token` request
5. Server validates: `code_challenge == BASE64URL(SHA256(code_verifier))`

### Session Security

The MCP gateway uses `SessionMiddleware` (Starlette) to:
- Store OAuth state during the triple-redirect flow
- Prevent CSRF attacks via state parameter validation
- Encrypt session cookies with `session_secret_key`

**Production:** Set a strong `session_secret_key` and use HTTPS.

## Troubleshooting

### "Authentication required: No Bearer token provided"

Claude Code is not sending the access token. Verify:
1. OAuth flow completed successfully
2. Claude Code stored the tokens (check Claude Code logs)
3. Token is being sent in `Authorization` header

### "Authentication failed: Invalid or expired access token"

Token validation failed. Check:
1. OAuth2 service is running and reachable
2. Token has not expired (default: 1 hour)
3. Token was issued by the correct OAuth provider

### "State mismatch (CSRF check failed)"

Session state was lost during OAuth flow. Verify:
1. `SessionMiddleware` is configured with a valid secret
2. Cookies are enabled in the browser
3. `session_secret_key` is consistent across gateway restarts

### "Missing code_verifier for PKCE"

Claude Code sent a PKCE challenge but no verifier. This indicates:
1. Claude Code version mismatch (update to latest)
2. Network issue during token exchange

## Comparison with Double-Redirect

| Feature | Double-Redirect (WebHook) | Triple-Redirect (MCP) |
|---------|---------------------------|------------------------|
| **Target Gateway** | Browser-based (WebHook) | Desktop app-based (MCP + Claude Code) |
| **Redirects** | 2 (WebHook → WebUI → WebHook) | 3 (Claude Code → MCP → WebUI → MCP → Claude Code) |
| **Token Storage** | Server-side (session/memory) | Client-side (Claude Code) |
| **Token Transmission** | Included in OAuth callback | Sent with every request via Authorization header |
| **Validation** | Per-session (store tokens) | Per-request (stateless) |
| **Multi-User** | Yes (via sessions) | Yes (each Claude Code instance has own tokens) |
| **PKCE** | Not required | Required (Claude Code enforces) |

For browser-based gateways using the double-redirect pattern, see [Gateway OAuth Proxy](./gateway_oauth_proxy.md).

## References

- [MCP OAuth Specification](https://modelcontextprotocol.io/docs/concepts/oauth)
- [RFC 8414: OAuth 2.0 Authorization Server Metadata](https://datatracker.ietf.org/doc/html/rfc8414)
- [RFC 7636: Proof Key for Code Exchange (PKCE)](https://datatracker.ietf.org/doc/html/rfc7636)
- [RFC 6749: OAuth 2.0 Authorization Framework](https://datatracker.ietf.org/doc/html/rfc6749)
