# Gateway OAuth Proxy Pattern

## Overview

The Gateway OAuth Proxy pattern enables SAM gateways to authenticate users via OAuth 2.0 without requiring individual Azure AD (or other OAuth provider) app registrations for each gateway. Instead, all gateways leverage a single OAuth proxy gateway (typically the WebUI) that handles the OAuth flow with the OAuth2 service.

This pattern is used for **browser-based gateways** where the user initiates authentication in a web browser.

## Supported Gateways

- WebHook Gateway (single-user)
- Any custom gateway with browser-based authentication

## Architecture

### Double-Redirect OAuth Flow

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Browser   │         │   Gateway   │         │    WebUI    │         │  Azure AD   │
│             │         │  (WebHook)  │         │   (Proxy)   │         │ OAuth2 Svc  │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │                       │
       │   1. GET /webhook/auth│                       │                       │
       ├──────────────────────>│                       │                       │
       │                       │                       │                       │
       │ 2. Redirect to WebUI  │                       │                       │
       │   /gateway-oauth/     │                       │                       │
       │      authorize        │                       │                       │
       │<──────────────────────┤                       │                       │
       │                       │                       │                       │
       │   3. GET /gateway-oauth/authorize?            │                       │
       │      gateway_uri=http://webhook/callback      │                       │
       ├───────────────────────────────────────────────>│                       │
       │                       │                       │                       │
       │                       │                       │ 4. Redirect to Azure │
       │<───────────────────────────────────────────────┤                       │
       │                       │                       │                       │
       │   5. User authenticates                                               │
       ├───────────────────────────────────────────────────────────────────────>│
       │                       │                       │                       │
       │   6. Redirect to WebUI callback                                       │
       │<───────────────────────────────────────────────────────────────────────┤
       │                       │                       │                       │
       │   7. GET /auth/callback?code=xyz              │                       │
       ├───────────────────────────────────────────────>│                       │
       │                       │                       │                       │
       │                       │                       │ 8. Exchange code for  │
       │                       │                       │    tokens (server-side)
       │                       │                       ├──────────────────────>│
       │                       │                       │                       │
       │                       │                       │ 9. Return tokens      │
       │                       │                       │<──────────────────────┤
       │                       │                       │                       │
       │ 10. Redirect to Gateway callback              │                       │
       │     with gateway_code                         │                       │
       │<───────────────────────────────────────────────┤                       │
       │                       │                       │                       │
       │ 11. GET /callback?code=gateway_xyz            │                       │
       ├──────────────────────>│                       │                       │
       │                       │                       │                       │
       │                       │ 12. Exchange gateway_code for tokens          │
       │                       ├───────────────────────>│                       │
       │                       │                       │                       │
       │                       │ 13. Return access_token & refresh_token       │
       │                       │<───────────────────────┤                       │
       │                       │                       │                       │
       │ 14. Success page      │                       │                       │
       │<──────────────────────┤                       │                       │
```

## Implementation

### 1. WebUI Configuration (OAuth Proxy)

The WebUI must be configured with the Gateway OAuth Proxy enabled:

```yaml
# WebUI configuration
gateway_oauth_proxy:
  enabled: true
  allowed_redirect_uris:
    - "http://localhost:5000/api/v1/auth/callback"  # WebHook gateway callback
    - "http://webhook-gateway.example.com/api/v1/auth/callback"
  gateway_code_ttl_seconds: 300  # 5 minutes
  strict_uri_validation: false  # Allow wildcard patterns like http://localhost:*
```

**Security:** Only pre-configured URIs in `allowed_redirect_uris` are permitted. This prevents malicious redirects.

### 2. Gateway Configuration (e.g., WebHook)

The gateway must be configured to use the WebUI as an OAuth proxy:

```yaml
# WebHook gateway configuration
external_auth:
  oauth_proxy_url: "http://localhost:8000"  # WebUI URL
  callback_url: "http://localhost:5000/api/v1/auth/callback"  # This gateway's callback
```

### 3. Gateway Implementation

Gateways use the `SAMOAuth2Handler` from the enterprise package:

```python
from solace_agent_mesh_enterprise.gateway.auth import SAMOAuth2Handler

# Initialize OAuth handler
auth_handler = SAMOAuth2Handler({
    'oauth_proxy_url': 'http://localhost:8000',
    'callback_url': 'http://localhost:5000/api/v1/auth/callback',
    'external_auth_service_url': 'http://localhost:8050',  # OAuth2 service (for refresh)
    'external_auth_provider': 'azure'
})

# /auth/login endpoint - initiates OAuth flow
@app.get("/auth/login")
async def login(request):
    result = await auth_handler.handle_authorize(request)
    return RedirectResponse(url=result['redirect_url'], status_code=result['status_code'])

# /auth/callback endpoint - handles OAuth callback from WebUI
@app.get("/auth/callback")
async def callback(request):
    try:
        tokens = await auth_handler.handle_callback(request)

        # IMPORTANT: Store tokens appropriately for your gateway
        # For single-user gateways: store in memory or persist to disk
        # For multi-user gateways: store in user session

        # Example: Store in session (for multi-user browser-based gateway)
        request.session['access_token'] = tokens['access_token']
        request.session['refresh_token'] = tokens['refresh_token']

        return HTMLResponse("<h1>Authentication successful!</h1>")
    except ValueError as e:
        return HTMLResponse(f"<h1>Authentication failed: {e}</h1>", status_code=400)
```

## Token Management

The `SAMOAuth2Handler` does **NOT** store tokens. Gateway adapters are responsible for:

1. **Storing tokens** appropriately for their use case
2. **Adding Authorization headers** to authenticated requests
3. **Refreshing tokens** when they expire

### Single-User Gateway Example (WebHook)

For single-user gateways, tokens can be stored in memory:

```python
class WebHookGateway:
    def __init__(self):
        self.access_token = None
        self.refresh_token = None

    async def handle_oauth_callback(self, request):
        tokens = await self.auth_handler.handle_callback(request)
        self.access_token = tokens['access_token']
        self.refresh_token = tokens['refresh_token']

    async def make_authenticated_request(self, url):
        headers = {"Authorization": f"Bearer {self.access_token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            return response
```

## Security Considerations

### Gateway Code Security

- **Single-use codes:** Gateway codes can only be exchanged once
- **Short-lived:** Codes expire after 5 minutes (configurable)
- **URI validation:** Exact URI matching prevents code stealing

### Token Security

- **Never exposed to browser:** Tokens are exchanged server-to-server
- **HTTPS required:** All production deployments must use HTTPS
- **Secure storage:** Gateways must store tokens securely (sessions, encrypted storage, etc.)

## Troubleshooting

### "Gateway URI not authorized" Error

The requesting gateway's callback URI is not in the WebUI's `allowed_redirect_uris` list. Add it to the WebUI configuration.

### "Invalid or expired gateway code" Error

Gateway codes expire after 5 minutes. The gateway took too long to exchange the code. Increase `gateway_code_ttl_seconds` if needed.

### "Failed to exchange gateway code" Error

The WebUI OAuth proxy is unreachable. Verify:
1. WebUI is running at the configured `oauth_proxy_url`
2. Network connectivity between gateway and WebUI
3. WebUI logs for additional error details

## Comparison with Triple-Redirect (MCP)

| Feature | Double-Redirect (WebHook) | Triple-Redirect (MCP) |
|---------|---------------------------|------------------------|
| Target Gateway | Browser-based (WebHook) | Desktop app-based (MCP with Claude Code) |
| User Flow | Browser → Gateway → WebUI → Azure → WebUI → Gateway | Browser → MCP → WebUI → Azure → WebUI → MCP → Claude Code |
| Token Storage | Server-side (in session or memory) | Client-side (Claude Code stores tokens) |
| Token Transmission | Included in OAuth callback | Sent with every request via Authorization header |
| Multi-User Support | Yes (via sessions) | Yes (each Claude Code instance has its own tokens) |

For MCP gateway authentication with Claude Code, see [MCP OAuth with Claude Code](./mcp_oauth_with_claude_code.md).
