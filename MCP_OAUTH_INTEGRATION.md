# MCP Gateway OAuth Authentication Integration Plan

## Overview

This document outlines the implementation plan for adding OAuth authentication to the Solace Agent Mesh MCP Gateway. The plan follows the proven patterns from the Slack gateway implementation while leveraging FastMCP's OAuth proxy capabilities for provider-agnostic authentication.

## Architecture

```
┌─────────────────┐    ┌──────────────────────────────────┐    ┌─────────────────┐
│   MCP Client    │───▶│         MCP Gateway              │───▶│ Solace A2A      │
│                 │    │  ┌─────────────────────────────┐ │    │ Agent Mesh      │
│ - OAuth Flow    │    │  │     OAuth Proxy             │ │    │                 │
│ - Provider      │    │  │  ┌─────────┬─────────────┐  │ │    │ - Agent Registry│
│   Selection     │    │  │  │ Azure   │   Google    │  │ │    │ - Task Manager  │
│ - Token Cache   │    │  │  │ GitHub  │   Custom    │  │ │    │ - Auth Context  │
└─────────────────┘    │  │  └─────────┴─────────────┘  │ │    └─────────────────┘
                       │  └─────────────────────────────┘ │
                       └──────────────────────────────────┘
```

## Key Design Principles

1. **Provider-Agnostic**: Single implementation works with any OAuth 2.0/OIDC provider
2. **Configuration-Driven**: Users configure endpoints rather than code-based provider selection
3. **Caching Optimized**: User identity caching reduces OAuth overhead (following Slack gateway pattern)
4. **Standards Compliant**: Leverages FastMCP's OAuth proxy for DCR-compliant interface
5. **A2A Integration**: Proper user context propagation through Agent-to-Agent tasks

## Implementation Plan

### Phase 1: Core OAuth Integration (Week 1)

#### 1.1 Configuration Schema Extension

Add OAuth configuration parameters to `app.py`:

```python
# Add to SPECIFIC_APP_SCHEMA_PARAMS in app.py
OAUTH_CONFIG_PARAMS = [
    # Authentication Control
    {
        "name": "enable_authentication",
        "type": "boolean",
        "default": False,
        "description": "Enable OAuth authentication for MCP gateway"
    },
    {
        "name": "user_cache_ttl_seconds",
        "type": "integer", 
        "default": 3600,
        "description": "User identity cache TTL in seconds"
    },
    
    # Generic OAuth Configuration
    {
        "name": "oauth_authorization_endpoint",
        "type": "string",
        "required": False,
        "description": "OAuth authorization endpoint URL"
    },
    {
        "name": "oauth_token_endpoint",
        "type": "string", 
        "required": False,
        "description": "OAuth token endpoint URL"
    },
    {
        "name": "oauth_client_id",
        "type": "string",
        "required": False,
        "description": "OAuth client ID"
    },
    {
        "name": "oauth_client_secret",
        "type": "string",
        "required": False,
        "description": "OAuth client secret"
    },
    
    # Token Verification
    {
        "name": "oauth_jwks_uri",
        "type": "string",
        "required": False,
        "description": "JWKS URI for token verification"
    },
    {
        "name": "oauth_issuer", 
        "type": "string",
        "required": False,
        "description": "Expected token issuer"
    },
    {
        "name": "oauth_audience",
        "type": "string",
        "required": False,
        "description": "Expected token audience"
    },
    
    # Optional Settings
    {
        "name": "oauth_base_url",
        "type": "string",
        "required": False,
        "description": "Base URL for OAuth callbacks (auto-detected if not set)"
    },
    {
        "name": "oauth_redirect_path",
        "type": "string",
        "default": "/auth/callback", 
        "description": "OAuth callback path"
    },
    {
        "name": "oauth_scopes",
        "type": "string",
        "default": "openid profile email",
        "description": "OAuth scopes (space-separated)"
    }
]
```

#### 1.2 OAuth Proxy Integration

Modify `component.py` to integrate FastMCP OAuth proxy:

```python
def __init__(self, **kwargs: Any):
    super().__init__(**kwargs)
    
    # ... existing MCP setup ...
    
    # OAuth-specific initialization
    self.user_cache = {}  # Cache user identities like Slack gateway
    self.user_cache_ttl = self.get_config("user_cache_ttl_seconds", 3600)
    
    # Initialize OAuth if enabled
    if self.get_config("enable_authentication", False):
        self.mcp_server = FastMCP(name="Solace Agent Mesh", auth=self._create_oauth_proxy())
    else:
        self.mcp_server = FastMCP(name="Solace Agent Mesh")

def _create_oauth_proxy(self):
    """Create OAuth proxy with generic configuration"""
    from fastmcp.server.auth import OAuthProxy
    from fastmcp.server.auth.providers.jwt import JWTVerifier
    
    base_url = self.get_config("oauth_base_url") or f"http://{self.mcp_host}:{self.mcp_port}"
    
    # Create token verifier
    token_verifier = JWTVerifier(
        jwks_uri=self.get_config("oauth_jwks_uri"),
        issuer=self.get_config("oauth_issuer"),
        audience=self.get_config("oauth_audience")
    )
    
    # Create OAuth proxy
    return OAuthProxy(
        upstream_authorization_endpoint=self.get_config("oauth_authorization_endpoint"),
        upstream_token_endpoint=self.get_config("oauth_token_endpoint"),
        upstream_client_id=self.get_config("oauth_client_id"),
        upstream_client_secret=self.get_config("oauth_client_secret"),
        token_verifier=token_verifier,
        base_url=base_url,
        redirect_path=self.get_config("oauth_redirect_path", "/auth/callback")
    )
```

### Phase 2: User Identity & Caching (Week 2)

#### 2.1 User Identity Extraction (Following Slack Gateway Pattern)

```python
async def _extract_initial_claims(self, external_event_data: Any) -> Optional[Dict[str, Any]]:
    """
    Extract initial identity claims from MCP OAuth request
    Following the Slack gateway pattern but for OAuth tokens
    """
    log_id_prefix = f"{self.log_identifier}[ExtractClaims]"
    
    if not self.get_config("enable_authentication", False):
        # No auth mode - return anonymous user
        return {
            "user_id": "anonymous",
            "email": "anonymous@local",
            "name": "Anonymous User",
            "source": "no_auth"
        }
    
    try:
        from fastmcp.server.dependencies import get_access_token
        
        token = get_access_token()
        if not token or not token.claims:
            log.warning("%s No valid OAuth token found in request", log_id_prefix)
            return None
        
        claims = token.claims
        
        # Extract primary identifiers (similar to Slack's user/team extraction)
        user_id = claims.get("sub") or claims.get("user_id") or claims.get("id")
        email = claims.get("email") or claims.get("preferred_username")
        
        if not user_id:
            log.warning("%s No user ID found in OAuth token claims", log_id_prefix)
            return None
        
        # Build initial claims (similar to Slack's approach)
        initial_claims = {
            "user_id": user_id,
            "email": email,
            "name": claims.get("name") or claims.get("given_name", "") + " " + claims.get("family_name", ""),
            "provider": claims.get("iss", "unknown"),
            "source": "oauth",
            "raw_claims": claims
        }
        
        # Clean up name
        if initial_claims["name"]:
            initial_claims["name"] = initial_claims["name"].strip()
        if not initial_claims["name"]:
            initial_claims["name"] = email or user_id
        
        log.debug("%s Extracted initial claims for user: %s", log_id_prefix, user_id)
        return initial_claims
        
    except Exception as e:
        log.exception("%s Error extracting OAuth claims: %s", log_id_prefix, e)
        return None
```

#### 2.2 User Authentication with Caching

```python
async def _authenticate_external_user(self, external_event_data: Any) -> Optional[str]:
    """
    Authenticate and cache user identity (following Slack gateway caching pattern)
    """
    log_id_prefix = f"{self.log_identifier}[AuthenticateUser]"
    
    # Extract initial claims first
    initial_claims = await self._extract_initial_claims(external_event_data)
    if not initial_claims:
        log.warning("%s Failed to extract initial claims", log_id_prefix)
        return None
    
    user_id = initial_claims["user_id"]
    
    # Check cache first (like Slack gateway)
    cached_user = self._get_cached_user(user_id)
    if cached_user:
        log.debug("%s Using cached user identity for: %s", log_id_prefix, user_id)
        return cached_user["email"] or user_id
    
    # Build full user identity
    user_identity = {
        "user_id": user_id,
        "email": initial_claims["email"],
        "name": initial_claims["name"],
        "provider": initial_claims["provider"],
        "roles": initial_claims["raw_claims"].get("roles", []),
        "groups": initial_claims["raw_claims"].get("groups", []),
        "scopes": initial_claims["raw_claims"].get("scope", "").split() if initial_claims["raw_claims"].get("scope") else [],
        "last_seen": time.time()
    }
    
    # Cache the user identity (like Slack gateway)
    self._cache_user(user_id, user_identity)
    
    log.info("%s Authenticated OAuth user: %s (%s)", 
            log_id_prefix, user_identity["name"], user_identity["provider"])
    
    # Return identifier for A2A (email preferred, fallback to user_id)
    return user_identity["email"] or user_id

def _get_cached_user(self, user_id: str) -> Optional[Dict[str, Any]]:
    """Get cached user identity if still valid"""
    if user_id not in self.user_cache:
        return None
    
    cached_user = self.user_cache[user_id]
    if time.time() - cached_user["last_seen"] > self.user_cache_ttl:
        # Cache expired
        del self.user_cache[user_id]
        return None
    
    return cached_user

def _cache_user(self, user_id: str, user_identity: Dict[str, Any]):
    """Cache user identity with TTL"""
    self.user_cache[user_id] = user_identity
    
    # Cleanup expired entries periodically (simple approach)
    current_time = time.time()
    expired_users = [
        uid for uid, user in self.user_cache.items()
        if current_time - user["last_seen"] > self.user_cache_ttl
    ]
    for uid in expired_users:
        del self.user_cache[uid]
```

#### 2.3 Enhanced Agent Tool Call Handler

```python
async def _call_agent_via_a2a(self, agent_name: str, message: str) -> str:
    """Calls an agent via A2A protocol with proper OAuth user context"""
    log_id_prefix = f"{self.log_identifier}[CallAgent:{agent_name}]"
    
    try:
        # Get authenticated user identity (following Slack pattern)
        authenticated_user = await self._authenticate_external_user(None)  # MCP token in context
        if not authenticated_user:
            return "Authentication required. Please authenticate with the MCP gateway."
        
        # Get cached user details for better context
        initial_claims = await self._extract_initial_claims(None)
        user_identity = {
            "id": authenticated_user,
            "name": initial_claims.get("name", "OAuth User") if initial_claims else "OAuth User",
            "source": "oauth"
        }
        
        # Create A2A parts
        a2a_parts = [TextPart(text=message)]
        
        # Build external request context (following Slack pattern)
        session_id = f"mcp-oauth-{self.generate_uuid()}"
        external_request_context = {
            "user_id_for_a2a": authenticated_user,
            "app_name_for_artifacts": self.gateway_id,
            "user_id_for_artifacts": authenticated_user,
            "a2a_session_id": session_id,
            "original_message": message,
            "target_agent": agent_name,
            "source": "mcp_oauth_gateway"
        }
        
        # Submit A2A task
        task_id = await self.submit_a2a_task(
            target_agent_name=agent_name,
            a2a_parts=a2a_parts,
            external_request_context=external_request_context,
            user_identity=user_identity,
            is_streaming=False
        )
        
        log.info("%s Submitted OAuth-authenticated A2A task %s for user %s", 
                log_id_prefix, task_id, authenticated_user)
        
        # Wait for completion
        response_text = await self._wait_for_task_completion(task_id, external_request_context)
        return response_text
        
    except Exception as e:
        log.exception("%s Error in OAuth-authenticated agent call: %s", log_id_prefix, e)
        return f"Error: {str(e)}"
```

### Phase 3: Multi-Provider Testing (Week 3)

#### 3.1 Provider Configuration Examples

**Azure Configuration:**
```yaml
app_config:
  enable_authentication: true
  oauth_authorization_endpoint: "https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/authorize"
  oauth_token_endpoint: "https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/token"
  oauth_client_id: "${AZURE_CLIENT_ID}"
  oauth_client_secret: "${AZURE_CLIENT_SECRET}"
  oauth_jwks_uri: "https://login.microsoftonline.com/{tenant-id}/discovery/v2.0/keys"
  oauth_issuer: "https://login.microsoftonline.com/{tenant-id}/v2.0"
  oauth_audience: "${AZURE_CLIENT_ID}"
  oauth_scopes: "openid profile email User.Read"
```

**Google Configuration:**
```yaml
app_config:
  enable_authentication: true
  oauth_authorization_endpoint: "https://accounts.google.com/o/oauth2/v2/auth"
  oauth_token_endpoint: "https://oauth2.googleapis.com/token"
  oauth_client_id: "${GOOGLE_CLIENT_ID}"
  oauth_client_secret: "${GOOGLE_CLIENT_SECRET}"
  oauth_jwks_uri: "https://www.googleapis.com/oauth2/v3/certs"
  oauth_issuer: "https://accounts.google.com"
  oauth_audience: "${GOOGLE_CLIENT_ID}"
  oauth_scopes: "openid profile email"
```

**GitHub Configuration:**
```yaml
app_config:
  enable_authentication: true
  oauth_authorization_endpoint: "https://github.com/login/oauth/authorize"
  oauth_token_endpoint: "https://github.com/login/oauth/access_token"
  oauth_client_id: "${GITHUB_CLIENT_ID}"
  oauth_client_secret: "${GITHUB_CLIENT_SECRET}"
  # GitHub uses API-based token verification instead of JWKS
  oauth_scopes: "user:email"
```

#### 3.2 Client Integration

Clients connect using FastMCP's built-in OAuth support:

```python
from fastmcp import Client

async def main():
    # Automatic OAuth flow - opens browser for authentication
    async with Client("https://your-gateway.com/mcp/", auth="oauth") as client:
        # Call authenticated agent tools
        result = await client.call_tool("my_agent_agent", {"message": "Hello from authenticated user"})
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

### Phase 4: Production Readiness (Week 4)

#### 4.1 Security Considerations

1. **Environment Variables**: Store sensitive credentials in environment variables
2. **HTTPS**: Enable HTTPS for production deployments  
3. **Token Validation**: Implement proper token expiration and refresh
4. **Scope Management**: Map OAuth scopes to A2A agent permissions
5. **Audit Logging**: Log all authenticated requests for compliance

#### 4.2 Enhanced External Input Translation

```python
async def _translate_external_input(self, external_event_data: Any, authenticated_user_identity: str) -> Tuple[Optional[str], List[A2APart], Dict[str, Any]]:
    """
    Translate MCP tool call to A2A format
    This is called by BaseGatewayComponent when processing external events
    """
    log_id_prefix = f"{self.log_identifier}[TranslateInput]"
    
    try:
        # Extract message from event data
        message = getattr(external_event_data, 'message', str(external_event_data))
        target_agent = getattr(external_event_data, 'target_agent', None)
        
        if not message:
            log.warning("%s No message found in external event", log_id_prefix)
            return None, [], {}
        
        # Create A2A parts (similar to Slack gateway)
        a2a_parts = [TextPart(text=message)]
        
        # Build external request context
        session_id = f"mcp-{self.generate_uuid()}"
        external_request_context = {
            "user_id_for_a2a": authenticated_user_identity,
            "app_name_for_artifacts": self.gateway_id,
            "user_id_for_artifacts": authenticated_user_identity,
            "a2a_session_id": session_id,
            "original_message": message,
            "source": "mcp_oauth"
        }
        
        return target_agent, a2a_parts, external_request_context
        
    except Exception as e:
        log.exception("%s Error translating external input: %s", log_id_prefix, e)
        return None, [], {}
```

## Key Benefits

1. **Provider-Agnostic**: Single implementation works with any OAuth 2.0/OIDC provider
2. **Follows Proven Patterns**: Uses the same architecture as the working Slack gateway
3. **Performance Optimized**: User caching reduces OAuth overhead
4. **Standards Compliant**: Leverages FastMCP's OAuth proxy for DCR compliance
5. **Maintainable**: Clear separation of concerns, easy to debug and extend
6. **Secure**: Proper token validation, user context propagation, and audit capabilities

## Implementation Dependencies

- FastMCP OAuth proxy functionality
- Existing Solace Agent Mesh gateway base classes
- OAuth provider configurations (Azure, Google, GitHub, etc.)
- HTTPS setup for production deployments

## Testing Strategy

1. **Unit Tests**: Test user identity extraction, caching, and token validation
2. **Integration Tests**: Test with multiple OAuth providers
3. **End-to-End Tests**: Test complete flow from client authentication to A2A task completion
4. **Performance Tests**: Validate user caching performance and memory usage
5. **Security Tests**: Test token validation, scope enforcement, and error handling

This plan provides a comprehensive roadmap for implementing OAuth authentication in the MCP Gateway while maintaining compatibility with the existing Solace Agent Mesh architecture.