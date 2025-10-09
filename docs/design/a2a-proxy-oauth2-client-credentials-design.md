# OAuth 2.0 Client Credentials Flow - Design Document

## 1. Executive Summary

This document describes the design for adding OAuth 2.0 Client Credentials flow support to the A2A Proxy component. This enhancement enables the proxy to authenticate with downstream A2A agents using industry-standard OAuth 2.0, providing automatic token acquisition, caching, and refresh capabilities.

### Key Benefits
- **Standards-Based Authentication**: Implements RFC 6749 Section 4.4 (Client Credentials Grant)
- **Automatic Token Management**: Eliminates manual token rotation
- **Production-Ready**: Suitable for service-to-service authentication scenarios
- **Backward Compatible**: Existing static token configurations continue to work

### Scope
This design covers:
- Token acquisition via OAuth 2.0 Client Credentials flow
- In-memory token caching with expiration
- Automatic token refresh on authentication failures
- Configuration schema extensions
- Error handling and logging

This design does NOT cover:
- Other OAuth 2.0 flows (Authorization Code, Device Code, etc.)
- Token persistence across proxy restarts
- Distributed token caching
- OpenID Connect (OIDC) support
- Mutual TLS (mTLS)

---

## 2. Architecture Overview

### 2.1 Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      A2AProxyComponent                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  _get_or_create_a2a_client()                             │  │
│  │  • Checks auth config type                               │  │
│  │  • Routes to appropriate auth handler                    │  │
│  └────────────┬─────────────────────────────────────────────┘  │
│               │                                                 │
│               ├─ static_bearer ──────────────────────┐          │
│               │                                      │          │
│               ├─ static_apikey ──────────────────────┤          │
│               │                                      │          │
│               └─ oauth2_client_credentials          │          │
│                         │                            │          │
│                         ▼                            ▼          │
│  ┌──────────────────────────────────┐  ┌──────────────────┐   │
│  │  _fetch_oauth2_token()           │  │ InMemoryContext  │   │
│  │  • Check OAuth2TokenCache        │  │ CredentialStore  │   │
│  │  • If miss: POST to token_url    │  │ (from a2a-sdk)   │   │
│  │  • Parse access_token            │  └──────────────────┘   │
│  │  • Cache with expiration         │                          │
│  └────────────┬─────────────────────┘                          │
│               │                                                 │
│               ▼                                                 │
│  ┌──────────────────────────────────┐                          │
│  │     OAuth2TokenCache             │                          │
│  │  • In-memory token storage       │                          │
│  │  • Per-agent keying              │                          │
│  │  • Expiration tracking           │                          │
│  └──────────────────────────────────┘                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  _forward_request()                                      │  │
│  │  • Wraps client calls with retry logic                  │  │
│  │  • Catches 401 errors                                    │  │
│  │  • Calls _handle_auth_error() on 401                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  _handle_auth_error()                                    │  │
│  │  • Invalidates cached token                             │  │
│  │  • Removes cached A2AClient                             │  │
│  │  • Returns True to trigger retry                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP POST
                              ▼
                    ┌──────────────────────┐
                    │  OAuth 2.0 Token     │
                    │  Endpoint            │
                    │  (External Service)  │
                    └──────────────────────┘
```

### 2.2 Authentication Flow Sequence

```
Client Request → Proxy → Check A2AClient Cache
                           │
                           ├─ Cache Hit → Use Existing Client
                           │
                           └─ Cache Miss → Create New Client
                                            │
                                            ├─ Check Auth Config Type
                                            │
                                            └─ oauth2_client_credentials
                                                │
                                                ├─ Check Token Cache
                                                │   │
                                                │   ├─ Cache Hit → Use Token
                                                │   │
                                                │   └─ Cache Miss → Fetch Token
                                                │                    │
                                                │                    ├─ POST to token_url
                                                │                    ├─ Parse response
                                                │                    └─ Cache token
                                                │
                                                └─ Store in CredentialStore
                                                    │
                                                    └─ Create A2AClient with AuthInterceptor
                                                        │
                                                        └─ Forward Request
                                                            │
                                                            ├─ Success → Return Response
                                                            │
                                                            └─ 401 Error → Invalidate Cache
                                                                           │
                                                                           └─ Retry (once)
```

---

## 3. Configuration Schema Design

### 3.1 Enhanced Authentication Configuration

The authentication configuration will support three types, maintaining backward compatibility:

```yaml
proxied_agents:
  - name: "agent-name"
    url: "https://agent.example.com"
    authentication:
      type: "oauth2_client_credentials"  # NEW: Explicit type field
      
      # OAuth 2.0 Client Credentials Parameters
      token_url: "https://auth.example.com/oauth/token"
      client_id: "${CLIENT_ID}"
      client_secret: "${CLIENT_SECRET}"
      scope: "agent:read agent:write"  # Optional, space-separated
      token_cache_duration_seconds: 3300  # Optional, default 3300 (55 min)
```

### 3.2 Configuration Type Enumeration

| Type | Description | Required Fields | Use Case |
|------|-------------|-----------------|----------|
| `static_bearer` | Static bearer token | `token` | Long-lived tokens, dev/test |
| `static_apikey` | Static API key | `token` | API key authentication |
| `oauth2_client_credentials` | OAuth 2.0 flow | `token_url`, `client_id`, `client_secret` | Production service-to-service |

### 3.3 Backward Compatibility Strategy

To maintain backward compatibility with existing configurations that don't specify a `type` field:

```python
# Legacy config (still supported)
authentication:
  scheme: "bearer"
  token: "static-token"

# Interpreted as:
authentication:
  type: "static_bearer"
  token: "static-token"
```

The implementation will:
1. Check for `type` field first
2. If absent, check for `scheme` field and map to appropriate type
3. Log a deprecation warning for legacy format
4. Continue to function correctly

### 3.4 Schema Validation Rules

**For `oauth2_client_credentials` type:**
- `token_url` (required): Must be a valid HTTPS URL
- `client_id` (required): Non-empty string
- `client_secret` (required): Non-empty string
- `scope` (optional): String, space-separated scope values
- `token_cache_duration_seconds` (optional): Integer > 0, default 3300

**Validation occurs at:**
1. Configuration load time (schema validation)
2. Client creation time (runtime validation)

---

## 4. Token Cache Design

### 4.1 OAuth2TokenCache Class

**Purpose**: Provide thread-safe, in-memory caching of OAuth 2.0 access tokens with automatic expiration.

**Location**: `src/solace_agent_mesh/agent/proxies/a2a/oauth_token_cache.py`

#### 4.1.1 Data Structures

```python
@dataclass
class CachedToken:
    """Represents a cached OAuth token with expiration."""
    access_token: str
    expires_at: float  # Unix timestamp (time.time() + cache_duration)
```

**Cache Storage**:
```python
_cache: Dict[str, CachedToken]
# Key: agent_name (string)
# Value: CachedToken instance
```

#### 4.1.2 Thread Safety

The cache uses `asyncio.Lock` to ensure thread-safe operations:
- All public methods acquire the lock before accessing `_cache`
- Lock is held for the minimum duration necessary
- No blocking operations occur while holding the lock

#### 4.1.3 Cache Key Strategy

**Key Format**: `agent_name` (string)

**Rationale**:
- Each proxied agent has independent credentials
- Simple, human-readable key
- No collision risk (agent names are unique per proxy instance)

**Not using session_id because**:
- OAuth 2.0 Client Credentials is service-to-service (no user session)
- Token is shared across all requests to the same agent
- Reduces token acquisition overhead

#### 4.1.4 Expiration Strategy

**Default Cache Duration**: 3300 seconds (55 minutes)

**Rationale**:
- Most OAuth 2.0 providers issue tokens valid for 60 minutes
- 55-minute cache provides 5-minute safety margin
- Prevents token expiration mid-request
- Configurable per agent for flexibility

**Expiration Check**:
- Performed on every `get()` call
- Expired tokens are automatically removed from cache
- No background cleanup thread (lazy expiration)

#### 4.1.5 Public Interface

```python
class OAuth2TokenCache:
    async def get(self, agent_name: str) -> Optional[str]:
        """
        Retrieves a cached token if valid.
        Returns None if not cached or expired.
        """
    
    async def set(
        self, 
        agent_name: str, 
        access_token: str, 
        cache_duration_seconds: int
    ):
        """
        Caches a token with expiration.
        """
    
    async def invalidate(self, agent_name: str):
        """
        Removes a token from cache.
        Used when 401 error indicates token is invalid.
        """
```

### 4.2 Cache Lifecycle

**Creation**: Single instance created in `A2AProxyComponent.__init__()`

**Scope**: Component-level (shared across all agents proxied by this component instance)

**Cleanup**: Automatic (Python garbage collection when component is destroyed)

**Persistence**: None (in-memory only, tokens lost on restart)

---

## 5. Token Acquisition Design

### 5.1 _fetch_oauth2_token() Method

**Purpose**: Acquire an OAuth 2.0 access token using the Client Credentials flow.

**Location**: `src/solace_agent_mesh/agent/proxies/a2a/component.py` (method of `A2AProxyComponent`)

#### 5.1.1 Method Signature

```python
async def _fetch_oauth2_token(
    self, 
    agent_name: str, 
    auth_config: dict
) -> str:
    """
    Fetches an OAuth 2.0 access token using the client credentials flow.
    
    Args:
        agent_name: The name of the agent (used as cache key).
        auth_config: Authentication configuration dictionary containing:
            - token_url: OAuth 2.0 token endpoint
            - client_id: OAuth 2.0 client identifier
            - client_secret: OAuth 2.0 client secret
            - scope: (optional) Space-separated scope string
            - token_cache_duration_seconds: (optional) Cache duration
    
    Returns:
        A valid OAuth 2.0 access token (string).
    
    Raises:
        ValueError: If required OAuth parameters are missing or invalid.
        httpx.HTTPStatusError: If token request returns non-2xx status.
        httpx.RequestError: If network error occurs.
    """
```

#### 5.1.2 Execution Flow

```
1. Check cache
   ├─ Hit: Return cached token
   └─ Miss: Continue to step 2

2. Validate configuration
   ├─ Ensure token_url, client_id, client_secret are present
   └─ Raise ValueError if missing

3. Prepare token request
   ├─ Extract scope (default: empty string)
   ├─ Extract cache_duration (default: 3300)
   └─ Log token acquisition attempt

4. Execute HTTP POST request
   ├─ URL: auth_config['token_url']
   ├─ Method: POST
   ├─ Content-Type: application/x-www-form-urlencoded
   ├─ Body:
   │   ├─ grant_type=client_credentials
   │   ├─ client_id={client_id}
   │   ├─ client_secret={client_secret}
   │   └─ scope={scope}
   └─ Timeout: 30 seconds

5. Parse response
   ├─ Expect JSON: {"access_token": "...", ...}
   ├─ Extract access_token field
   └─ Raise ValueError if missing

6. Cache token
   ├─ Call cache.set(agent_name, access_token, cache_duration)
   └─ Log success

7. Return access_token
```

#### 5.1.3 HTTP Request Details

**Request Format** (per RFC 6749 Section 4.4.2):
```http
POST /oauth/token HTTP/1.1
Host: auth.example.com
Content-Type: application/x-www-form-urlencoded
Accept: application/json

grant_type=client_credentials
&client_id=CLIENT_ID
&client_secret=CLIENT_SECRET
&scope=agent:read%20agent:write
```

**Expected Response** (per RFC 6749 Section 4.4.3):
```json
{
  "access_token": "2YotnFZFEjr1zCsicMWpAA",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "agent:read agent:write"
}
```

**Note**: The implementation only requires `access_token` field. Other fields (`token_type`, `expires_in`, `scope`) are ignored. Token expiration is managed by the configurable `token_cache_duration_seconds`, not the `expires_in` value from the response.

#### 5.1.4 Error Handling

| Error Type | HTTP Status | Handling Strategy |
|------------|-------------|-------------------|
| Invalid credentials | 401 | Log error, raise HTTPStatusError, propagate to caller |
| Missing parameters | 400 | Log error, raise HTTPStatusError, propagate to caller |
| Server error | 500-599 | Log error, raise HTTPStatusError, propagate to caller |
| Network timeout | N/A | Log error, raise RequestError, propagate to caller |
| Invalid response format | 200 | Log error, raise ValueError, propagate to caller |

**Error Propagation**: All errors are logged and propagated to the caller (`_get_or_create_a2a_client`), which will fail the client creation and ultimately fail the request forwarding.

#### 5.1.5 Logging Strategy

```python
# On cache hit
log.debug(f"Using cached OAuth token for '{agent_name}'")

# On token acquisition start
log.info(f"Fetching new OAuth 2.0 token from {token_url} (scope: {scope or 'default'})")

# On success
log.info(f"Successfully obtained OAuth 2.0 token (cached for {cache_duration}s)")

# On HTTP error
log.error(f"OAuth 2.0 token request failed with status {status_code}: {response_text}")

# On network error
log.error(f"OAuth 2.0 token request failed: {error}")

# On unexpected error
log.exception(f"Unexpected error fetching OAuth 2.0 token: {error}")
```

---

## 6. Client Creation Integration

### 6.1 Modified _get_or_create_a2a_client() Method

**Purpose**: Integrate OAuth 2.0 authentication into the existing client creation flow.

**Changes Required**:
1. Add authentication type routing logic
2. Call `_fetch_oauth2_token()` for OAuth 2.0 type
3. Maintain backward compatibility with legacy config
4. Store token in `InMemoryContextCredentialStore`

#### 6.1.1 Authentication Type Routing

```python
auth_config = agent_config.get("authentication")
if auth_config:
    session_id = task_context.a2a_context.get("session_id", "default_session")
    auth_type = auth_config.get("type")
    
    # Determine auth type (with backward compatibility)
    if not auth_type:
        # Legacy config: infer type from 'scheme' field
        scheme = auth_config.get("scheme", "bearer")
        if scheme == "bearer":
            auth_type = "static_bearer"
        elif scheme == "apikey":
            auth_type = "static_apikey"
        else:
            raise ValueError(f"Unknown legacy scheme: {scheme}")
        
        log.warning(
            f"Using legacy authentication config for agent '{agent_name}'. "
            f"Consider migrating to 'type' field."
        )
    
    # Route to appropriate handler
    if auth_type == "static_bearer":
        # Existing logic
        token = auth_config.get("token")
        if not token:
            raise ValueError(f"'token' required for static_bearer")
        await self._credential_store.set_credentials(session_id, "bearer", token)
    
    elif auth_type == "static_apikey":
        # Existing logic
        token = auth_config.get("token")
        if not token:
            raise ValueError(f"'token' required for static_apikey")
        await self._credential_store.set_credentials(session_id, "apikey", token)
    
    elif auth_type == "oauth2_client_credentials":
        # NEW: OAuth 2.0 flow
        try:
            access_token = await self._fetch_oauth2_token(agent_name, auth_config)
            await self._credential_store.set_credentials(session_id, "bearer", access_token)
        except Exception as e:
            log.error(f"Failed to obtain OAuth 2.0 token for '{agent_name}': {e}")
            raise
    
    else:
        raise ValueError(f"Unsupported authentication type: {auth_type}")
```

#### 6.1.2 Integration with a2a-sdk

The `a2a-sdk` provides:
- `InMemoryContextCredentialStore`: Stores credentials per session
- `AuthInterceptor`: Automatically adds `Authorization` header to requests

**Integration Points**:
1. Token stored via `credential_store.set_credentials(session_id, "bearer", token)`
2. `AuthInterceptor` initialized with `credential_store` in `__init__`
3. `A2AClient` created with `interceptors=[self._auth_interceptor]`
4. SDK handles header injection automatically

**No changes required to a2a-sdk** - we use its existing authentication infrastructure.

---

## 7. Token Refresh Design

### 7.1 Authentication Error Detection

**Trigger**: HTTP 401 Unauthorized response from downstream agent

**Detection Point**: `_forward_request()` method catches `A2AClientHTTPError` with `status_code == 401`

### 7.2 _handle_auth_error() Method

**Purpose**: Handle authentication failures by invalidating cached tokens and enabling retry.

#### 7.2.1 Method Signature

```python
async def _handle_auth_error(
    self, 
    agent_name: str, 
    task_context: "ProxyTaskContext"
) -> bool:
    """
    Handles authentication errors by invalidating cached tokens.
    
    Args:
        agent_name: The name of the agent that returned 401.
        task_context: The current task context.
    
    Returns:
        True if token was invalidated and retry should be attempted.
        False if no retry should be attempted (e.g., static token).
    """
```

#### 7.2.2 Execution Flow

```
1. Retrieve agent configuration
   └─ Return False if not found

2. Check authentication type
   ├─ oauth2_client_credentials: Continue to step 3
   └─ Other types: Return False (no retry for static tokens)

3. Invalidate cached token
   └─ Call cache.invalidate(agent_name)

4. Remove cached A2AClient
   ├─ Pop from self._a2a_clients
   └─ Close httpx client if not already closed

5. Return True (signal retry)
```

#### 7.2.3 Why Remove A2AClient?

The cached `A2AClient` instance holds a reference to the old token via the `AuthInterceptor` and `CredentialStore`. To ensure the next request uses a fresh token:

1. Remove the client from `self._a2a_clients` cache
2. Close its underlying `httpx.AsyncClient`
3. Next call to `_get_or_create_a2a_client()` will create a new client
4. New client creation will fetch a fresh token (cache miss)

### 7.3 Retry Logic in _forward_request()

**Strategy**: Single retry on 401 error for OAuth 2.0 authenticated agents.

```python
max_auth_retries = 1
auth_retry_count = 0

while auth_retry_count <= max_auth_retries:
    try:
        # Get client and forward request
        client = await self._get_or_create_a2a_client(agent_name, task_context)
        # ... forward logic ...
        break  # Success - exit retry loop
    
    except A2AClientHTTPError as e:
        if e.status_code == 401 and auth_retry_count < max_auth_retries:
            should_retry = await self._handle_auth_error(agent_name, task_context)
            if should_retry:
                auth_retry_count += 1
                continue  # Retry
        
        # Not retryable or max retries exceeded
        raise
```

**Rationale for Single Retry**:
- First 401: Token may have expired between cache check and request
- Retry with fresh token should succeed
- Second 401: Indicates configuration or authorization issue (not transient)
- Prevents infinite retry loops

### 7.4 Token Refresh Scenarios

| Scenario | Cache State | Behavior |
|----------|-------------|----------|
| Token expires during request | Valid in cache | 401 → Invalidate → Fetch new → Retry → Success |
| Token revoked by auth server | Valid in cache | 401 → Invalidate → Fetch new → Retry → 401 (fail) |
| Invalid client credentials | N/A | Fetch fails → Request fails (no retry) |
| Network error to auth server | N/A | Fetch fails → Request fails (no retry) |

---

## 8. Error Handling Strategy

### 8.1 Error Categories

#### 8.1.1 Configuration Errors (Fail Fast)

**When**: Configuration validation at startup or client creation

**Examples**:
- Missing required OAuth parameters
- Invalid URL format
- Invalid cache duration (≤ 0)

**Handling**:
- Raise `ValueError` with descriptive message
- Log error at ERROR level
- Fail component initialization or request

**User Action**: Fix configuration and restart

#### 8.1.2 Token Acquisition Errors (Transient)

**When**: HTTP request to token endpoint fails

**Examples**:
- Network timeout
- DNS resolution failure
- Connection refused

**Handling**:
- Log error at ERROR level
- Raise `httpx.RequestError`
- Fail the current request
- Do NOT cache the error
- Next request will retry token acquisition

**User Action**: Check network connectivity, auth server availability

#### 8.1.3 Authentication Errors (Permanent)

**When**: Token endpoint returns error response

**Examples**:
- 401: Invalid client credentials
- 400: Invalid request format
- 403: Client not authorized for requested scope

**Handling**:
- Log error at ERROR level with response body
- Raise `httpx.HTTPStatusError`
- Fail the current request
- Do NOT cache the error
- Next request will retry (and likely fail again)

**User Action**: Fix client credentials or scope configuration

#### 8.1.4 Token Expiration Errors (Recoverable)

**When**: Downstream agent returns 401 with valid OAuth config

**Examples**:
- Token expired between cache check and request
- Token revoked by auth server

**Handling**:
- Log warning at WARNING level
- Invalidate cached token
- Retry request once with fresh token
- If second 401, fail request

**User Action**: None (automatic recovery) or check authorization if persistent

### 8.2 Logging Standards

#### 8.2.1 Log Levels

| Level | Use Case | Example |
|-------|----------|---------|
| DEBUG | Cache hits, routine operations | "Using cached OAuth token for 'agent1'" |
| INFO | Token acquisition, successful operations | "Successfully obtained OAuth 2.0 token (cached for 3300s)" |
| WARNING | Retries, deprecated config usage | "Received 401 Unauthorized. Attempting token refresh (retry 1/1)" |
| ERROR | Failures, invalid config | "OAuth 2.0 token request failed with status 401: Invalid client" |
| EXCEPTION | Unexpected errors | "Unexpected error fetching OAuth 2.0 token" (with stack trace) |

#### 8.2.2 Log Message Format

**Standard Format**:
```
{log_identifier} {message}
```

**Where**:
- `log_identifier`: `{component.log_identifier}[OAuth2:{agent_name}]`
- `message`: Human-readable description with relevant context

**Examples**:
```
[A2AProxyComponent:proxy_component][OAuth2:ModernAgent] Fetching new OAuth 2.0 token from https://auth.example.com/token (scope: agent:read agent:write)

[A2AProxyComponent:proxy_component][OAuth2:ModernAgent] Successfully obtained OAuth 2.0 token (cached for 3300s)

[A2AProxyComponent:proxy_component][ForwardRequest:task-123:ModernAgent] Received 401 Unauthorized. Attempting token refresh (retry 1/1)
```

### 8.3 Error Response to Client

When OAuth 2.0 authentication fails and cannot be recovered:

**Response Format**:
```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "error": {
    "code": -32603,
    "message": "Internal error: Failed to authenticate with downstream agent 'ModernAgent'",
    "data": {
      "taskId": "task-123",
      "agent_name": "ModernAgent",
      "error_type": "authentication_failure"
    }
  }
}
```

**Published to**: `replyToTopic` from original request

---

## 9. Security Considerations

### 9.1 Credential Storage

**Client Secrets**:
- MUST be stored in environment variables, not config files
- SHOULD use secrets management systems (Vault, AWS Secrets Manager, etc.)
- MUST NOT be logged (even at DEBUG level)

**Access Tokens**:
- Stored in memory only (no disk persistence)
- Cleared on component shutdown
- Not logged (even at DEBUG level)

### 9.2 Token Transmission

**To Auth Server**:
- MUST use HTTPS (enforced by requiring `https://` in `token_url`)
- Client secret sent in POST body (not URL)
- Standard OAuth 2.0 security practices apply

**To Downstream Agent**:
- Token added to `Authorization: Bearer {token}` header by `a2a-sdk`
- MUST use HTTPS for agent URL (enforced by A2A protocol)

### 9.3 Token Lifetime

**Cache Duration**:
- Default: 3300 seconds (55 minutes)
- Configurable per agent
- SHOULD be less than actual token expiration
- Provides safety margin for clock skew

**Token Revocation**:
- Proxy has no mechanism to proactively revoke tokens
- Tokens remain valid until expiration or auth server revocation
- On 401 error, token is invalidated and refetched

### 9.4 Scope Management

**Principle of Least Privilege**:
- Request only necessary scopes
- Document required scopes per agent
- Auth server enforces scope restrictions

**Scope Validation**:
- Proxy does NOT validate scopes
- Auth server is source of truth
- Downstream agent enforces scope-based authorization

---

## 10. Performance Considerations

### 10.1 Token Caching Benefits

**Without Caching**:
- Every request requires token acquisition
- Adds ~100-500ms latency per request
- Increases load on auth server
- Risk of rate limiting

**With Caching**:
- Token acquired once per cache duration
- Subsequent requests have no auth overhead
- Reduced auth server load
- Better throughput

**Cache Hit Rate** (expected):
- Assuming 60-minute token lifetime and 55-minute cache
- Assuming 10 requests/minute to an agent
- Cache hit rate: ~99.7% (549 hits, 1 miss per hour)

### 10.2 Memory Footprint

**Per Cached Token**:
- `CachedToken` object: ~200 bytes
- Access token string: ~500-2000 bytes (typical JWT)
- Total: ~2KB per agent

**For 100 Agents**:
- Total memory: ~200KB
- Negligible compared to other component memory usage

### 10.3 Concurrency Handling

**Token Acquisition**:
- Uses `asyncio.Lock` in cache
- Only one token fetch per agent at a time
- Concurrent requests for same agent wait for first fetch
- No thundering herd problem

**Client Creation**:
- `_get_or_create_a2a_client()` not currently locked
- Potential race condition: multiple concurrent requests could create multiple clients
- **Recommendation**: Add lock around client creation (future enhancement)
- **Impact**: Low (clients are cached, race is rare)

---

## 11. Configuration Migration Guide

### 11.1 From Static Bearer Token to OAuth 2.0

**Before**:
```yaml
proxied_agents:
  - name: "MyAgent"
    url: "https://agent.example.com"
    authentication:
      scheme: "bearer"
      token: "${STATIC_TOKEN}"
```

**After**:
```yaml
proxied_agents:
  - name: "MyAgent"
    url: "https://agent.example.com"
    authentication:
      type: "oauth2_client_credentials"
      token_url: "https://auth.example.com/oauth/token"
      client_id: "${CLIENT_ID}"
      client_secret: "${CLIENT_SECRET}"
      scope: "agent:read agent:write"
```

**Steps**:
1. Obtain OAuth 2.0 client credentials from auth provider
2. Update configuration with new `authentication` block
3. Set environment variables for `CLIENT_ID` and `CLIENT_SECRET`
4. Restart proxy component
5. Verify successful token acquisition in logs

### 11.2 Backward Compatibility

**Legacy Config** (no `type` field):
```yaml
authentication:
  scheme: "bearer"
  token: "static-token"
```

**Behavior**:
- Interpreted as `type: "static_bearer"`
- Deprecation warning logged
- Continues to function correctly

**Recommendation**: Migrate to explicit `type` field for clarity

---

## 12. Observability and Monitoring

### 12.1 Key Metrics (Future Enhancement)

While not implemented in this design, the following metrics would be valuable:

- `oauth2_token_acquisitions_total`: Counter of token fetch attempts
- `oauth2_token_acquisition_errors_total`: Counter of token fetch failures
- `oauth2_token_cache_hits_total`: Counter of cache hits
- `oauth2_token_cache_misses_total`: Counter of cache misses
- `oauth2_token_acquisition_duration_seconds`: Histogram of token fetch latency

### 12.2 Log-Based Monitoring

**Success Indicators**:
- `"Successfully obtained OAuth 2.0 token"` (INFO)
- `"Using cached OAuth token"` (DEBUG)

**Failure Indicators**:
- `"OAuth 2.0 token request failed"` (ERROR)
- `"Failed to obtain OAuth 2.0 token"` (ERROR)
- `"Received 401 Unauthorized. Attempting token refresh"` (WARNING)

**Alerting Recommendations**:
- Alert on repeated token acquisition failures (> 3 in 5 minutes)
- Alert on repeated 401 errors after retry (indicates config issue)

---

## 13. Testing Strategy (Overview)

While detailed test implementation is out of scope, the following test categories are recommended:

### 13.1 Unit Tests

**OAuth2TokenCache**:
- Token caching and retrieval
- Expiration handling
- Invalidation
- Concurrent access

**_fetch_oauth2_token()**:
- Successful token acquisition
- Cache hit behavior
- HTTP error handling
- Invalid response handling
- Network error handling

**_handle_auth_error()**:
- Token invalidation for OAuth agents
- No-op for static token agents
- Client removal

### 13.2 Integration Tests

**End-to-End OAuth Flow**:
- Mock OAuth server
- Token acquisition
- Request forwarding with token
- Token refresh on 401

**Configuration Validation**:
- Valid OAuth config
- Invalid OAuth config
- Missing required fields
- Backward compatibility

### 13.3 Manual Testing Checklist

- [ ] Configure agent with OAuth 2.0
- [ ] Verify token acquisition in logs
- [ ] Verify successful request forwarding
- [ ] Simulate token expiration (short cache duration)
- [ ] Verify automatic token refresh
- [ ] Test with invalid client credentials
- [ ] Test with network failure to auth server
- [ ] Verify backward compatibility with static tokens

---

## 14. Implementation Checklist

### 14.1 New Files

- [ ] `src/solace_agent_mesh/agent/proxies/a2a/oauth_token_cache.py`
  - `CachedToken` dataclass
  - `OAuth2TokenCache` class

### 14.2 Modified Files

- [ ] `src/solace_agent_mesh/agent/proxies/a2a/app.py`
  - Update `app_schema` with OAuth 2.0 parameters
  - Add validation for new authentication types

- [ ] `src/solace_agent_mesh/agent/proxies/a2a/component.py`
  - Add `_oauth_token_cache` instance variable in `__init__`
  - Implement `_fetch_oauth2_token()` method
  - Implement `_handle_auth_error()` method
  - Modify `_get_or_create_a2a_client()` for auth type routing
  - Modify `_forward_request()` for retry logic

### 14.3 Documentation

- [ ] Update proxy configuration documentation
- [ ] Add OAuth 2.0 setup guide
- [ ] Add migration guide from static tokens
- [ ] Update security best practices

---

## 15. Future Enhancements (Out of Scope)

### 15.1 Additional OAuth 2.0 Flows

- **Authorization Code Flow**: For user-delegated access
- **Device Code Flow**: For headless/CLI agents
- **Refresh Token Support**: For long-lived sessions

### 15.2 Advanced Token Management

- **Distributed Token Cache**: Redis/Memcached for multi-instance deployments
- **Token Persistence**: Survive proxy restarts
- **Proactive Token Refresh**: Refresh before expiration
- **Token Rotation**: Automatic credential rotation

### 15.3 Enhanced Security

- **Mutual TLS (mTLS)**: Client certificate authentication
- **Token Introspection**: Validate token with auth server
- **Scope Validation**: Verify token has required scopes
- **PKCE Support**: For public clients

### 15.4 Observability

- **Prometheus Metrics**: Expose token acquisition metrics
- **Distributed Tracing**: Trace token acquisition in spans
- **Health Checks**: Verify auth server connectivity

---

## 16. References

### 16.1 Standards

- **RFC 6749**: The OAuth 2.0 Authorization Framework
  - Section 4.4: Client Credentials Grant
  - Section 5.1: Successful Response
  - Section 5.2: Error Response

- **RFC 6750**: The OAuth 2.0 Authorization Framework: Bearer Token Usage
  - Section 2.1: Authorization Request Header Field

### 16.2 A2A Protocol

- `a2a-protocol-auth-info.md`: A2A authentication patterns and best practices
- A2A Protocol Specification: AgentCard security schemes

### 16.3 Dependencies

- **httpx**: Async HTTP client for token requests
- **a2a-sdk**: Official A2A Python SDK
  - `InMemoryContextCredentialStore`
  - `AuthInterceptor`
  - `A2AClient`

---

## 17. Glossary

| Term | Definition |
|------|------------|
| **Access Token** | A credential used to access protected resources, issued by an authorization server |
| **Client Credentials** | A pair of client_id and client_secret used to authenticate the client application |
| **Grant Type** | The method by which a client obtains an access token (e.g., client_credentials) |
| **Scope** | A space-separated list of permissions requested by the client |
| **Token Endpoint** | The OAuth 2.0 server endpoint that issues access tokens |
| **Bearer Token** | A type of access token that grants access to whoever possesses it |
| **Token Expiration** | The time after which a token is no longer valid |
| **Token Cache** | In-memory storage of tokens to avoid repeated acquisition |
| **Token Refresh** | The process of obtaining a new token when the current one expires or is invalid |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-09 | AI Assistant | Initial design document |

---

**End of Document**
