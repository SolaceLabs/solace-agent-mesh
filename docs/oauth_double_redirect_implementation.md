# OAuth Double-Redirect Implementation for SAM OAuth2 Service

## Problem Statement

Currently, SAM's OAuth2 service requires every gateway's callback URI to be registered in the OAuth provider (e.g., Azure AD). This creates operational overhead when:
- Adding new gateways with different ports/domains
- Running multiple instances of the same gateway
- Testing with different configurations

**Current Flow:**
```
1. Gateway → SAM OAuth2 /login?redirect_uri=<gateway_callback>
2. SAM → Azure AD with redirect_uri=<gateway_callback>
3. Azure AD → Gateway callback (MUST be registered in Azure)
4. Gateway → SAM /exchange-code
5. SAM → Gateway with tokens
```

**Problem:** Step 3 fails if `<gateway_callback>` is not registered in Azure AD.

## Solution: Double-Redirect Pattern

Implement a double-redirect pattern where Azure always redirects to SAM's registered callback, then SAM redirects back to the requesting gateway.

**New Flow:**
```
1. Gateway → SAM OAuth2 /login?redirect_uri=<gateway_callback>&gateway_redirect_uri=<gateway_callback>
2. SAM → Azure AD with redirect_uri=<SAM_callback> (always http://localhost:8050/callback)
3. Azure AD → SAM callback (already registered)
4. SAM validates state, exchanges code for tokens
5. SAM → Gateway callback with tokens in URL fragment
6. Gateway extracts tokens from URL fragment
```

**Benefits:**
- Only SAM's callback needs Azure registration
- Gateways can use any redirect URI
- Backwards compatible (existing gateways still work)

## Implementation Details

### 1. Configuration Changes

**File: `configs/auth/oauth2_config.yaml`**

Add new security configuration for gateway redirect URI validation:

```yaml
# Security configuration
security:
  # Gateway redirect URI whitelist for double-redirect
  # Only URIs matching these patterns will be allowed as final redirect targets
  gateway_redirect_whitelist:
    # For development - allow localhost on any port
    - "http://localhost:*"
    - "http://127.0.0.1:*"
    # For production - add specific allowed domains
    # - "https://gateway.yourdomain.com/*"
    # - "https://*.yourdomain.com/oauth/callback"

  # Strict validation mode - if true, only exact matches allowed (no wildcards)
  strict_redirect_validation: ${OAUTH2_STRICT_REDIRECT:false}

  # CORS settings
  cors:
    enabled: ${OAUTH2_CORS_ENABLED:true}
    origins: ${OAUTH2_CORS_ORIGINS:*}
```

### 2. OAuth2 Service Code Changes

**File: `/Users/edfunnekotter/github/solace-agent-mesh-enterprise/src/services/oauth2_service.py`**

#### 2.1. Add Redirect URI Validation

Add this method to the `OAuth2Service` class (around line 200, after `_get_token_endpoint`):

```python
def _validate_gateway_redirect_uri(self, redirect_uri: str) -> bool:
    """
    Validate that a gateway redirect URI matches the whitelist.

    This prevents open redirect vulnerabilities by ensuring only
    trusted gateway URIs can be used as final redirect targets.

    Args:
        redirect_uri: The gateway's callback URI to validate

    Returns:
        True if the URI is allowed, False otherwise
    """
    if not redirect_uri:
        return False

    from urllib.parse import urlparse
    import fnmatch

    # Get whitelist from config
    whitelist = self.config.get("security", {}).get("gateway_redirect_whitelist", [])
    strict_mode = self.config.get("security", {}).get("strict_redirect_validation", False)

    if not whitelist:
        # No whitelist configured - reject all for security
        log.warning("No gateway_redirect_whitelist configured, rejecting redirect")
        return False

    parsed = urlparse(redirect_uri)

    # Basic security checks
    if parsed.scheme not in ["http", "https"]:
        log.warning(f"Invalid redirect URI scheme: {parsed.scheme}")
        return False

    # Check against whitelist
    for pattern in whitelist:
        if strict_mode:
            # Exact match only
            if redirect_uri == pattern:
                log.debug(f"Redirect URI matched (strict): {redirect_uri}")
                return True
        else:
            # Wildcard matching
            if fnmatch.fnmatch(redirect_uri, pattern):
                log.debug(f"Redirect URI matched pattern: {redirect_uri} ~ {pattern}")
                return True

    log.warning(f"Redirect URI not in whitelist: {redirect_uri}")
    return False
```

#### 2.2. Modify `/login` Endpoint

**Current code (lines 367-432):**

Replace the `/login` endpoint with this updated version:

```python
@self.app.get("/login", response_class=RedirectResponse)
async def login(
    provider: str = Query(..., description="OAuth2 provider name"),
    redirect_uri: Optional[str] = Query(None, description="Override default redirect URI"),
    gateway_redirect_uri: Optional[str] = Query(None, description="Gateway's final callback URI for double-redirect"),
    request: Request = None
):
    """
    Initiate OAuth2 login flow.

    Redirects the user to the OAuth2 provider's authorization URL.

    Double-Redirect Mode:
    - If gateway_redirect_uri is provided, SAM will use its own callback with Azure,
      then redirect to gateway_redirect_uri with tokens in URL fragment.
    - This allows gateways to use any callback URI without Azure registration.

    Legacy Mode:
    - If gateway_redirect_uri is NOT provided, works as before (direct redirect).
    - Gateway's redirect_uri must be registered in Azure.
    """
    if provider not in self.providers:
        available = ", ".join(self.providers.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}. Available: {available}"
        )

    provider_instance = self.providers[provider]

    # Determine if using double-redirect mode
    use_double_redirect = gateway_redirect_uri is not None

    if use_double_redirect:
        # Double-redirect mode: validate gateway URI
        if not self._validate_gateway_redirect_uri(gateway_redirect_uri):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or unauthorized gateway_redirect_uri. Check gateway_redirect_whitelist configuration."
            )

        # Use SAM's own callback with Azure
        actual_redirect_uri = provider_instance.redirect_uri
        log.info(f"Double-redirect mode: Azure will redirect to {actual_redirect_uri}, then to {gateway_redirect_uri}")
    else:
        # Legacy mode: use gateway's redirect_uri directly
        actual_redirect_uri = redirect_uri or provider_instance.redirect_uri
        log.info(f"Legacy mode: Azure will redirect directly to {actual_redirect_uri}")

    try:
        # Re-discover endpoints if required
        if provider_instance.auth_base_url is None:
            provider_instance._discover_endpoints()

        # Create OAuth2 session
        oauth = OAuth2Session(
            client_id=provider_instance.client_id,
            redirect_uri=actual_redirect_uri,
            scope=provider_instance.scope
        )

        # Get authorization URL with provider-specific parameters
        auth_params = provider_instance.get_authorization_url_params()
        authorization_url, state = oauth.authorization_url(
            provider_instance.auth_base_url,
            **auth_params
        )

        # Store state and provider info in session
        session_data = {
            "oauth_state": state,
            "oauth_provider": provider,
            "redirect_uri": actual_redirect_uri,
        }

        # If double-redirect mode, store gateway's callback URI
        if use_double_redirect:
            session_data["gateway_redirect_uri"] = gateway_redirect_uri
            session_data["double_redirect_mode"] = True

        session_id = self._set_session(request, session_data)

        # Create redirect response and set session cookie
        response = RedirectResponse(url=authorization_url)
        response.set_cookie(
            key="oauth_session_id",
            value=session_id,
            max_age=3600,  # 1 hour
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Login failed for provider {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login initiation failed"
        )
```

#### 2.3. Modify `/callback` Endpoint

**Current code (lines 434-520):**

Replace the `/callback` endpoint with this updated version:

```python
@self.app.get("/callback")
async def callback(
    code: Optional[str] = Query(None, description="Authorization code"),
    state: Optional[str] = Query(None, description="State parameter"),
    error: Optional[str] = Query(None, description="Error code"),
    error_description: Optional[str] = Query(None, description="Error description"),
    request: Request = None
):
    """
    Handle OAuth2 callback.

    Two modes:
    1. Legacy mode: Returns tokens as JSON (for backward compatibility)
    2. Double-redirect mode: Redirects to gateway_redirect_uri with tokens in URL fragment
    """
    # Check for OAuth errors
    if error:
        # If double-redirect mode, redirect to gateway with error
        try:
            session = self._get_session(request)
            if session.get("double_redirect_mode"):
                gateway_uri = session.get("gateway_redirect_uri")
                if gateway_uri:
                    from urllib.parse import urlencode
                    error_params = urlencode({
                        "error": error,
                        "error_description": error_description or "OAuth authentication failed"
                    })
                    return RedirectResponse(url=f"{gateway_uri}#{error_params}")
        except Exception:
            pass

        # Fallback to JSON error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {error} - {error_description or 'Unknown error'}"
        )

    try:
        # Get stored session data
        session = self._get_session(request)
        stored_state = session.get("oauth_state")
        provider_name = session.get("oauth_provider")
        redirect_uri = session.get("redirect_uri")
        double_redirect_mode = session.get("double_redirect_mode", False)
        gateway_redirect_uri = session.get("gateway_redirect_uri")

        if not all([stored_state, provider_name, redirect_uri]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session state"
            )

        if state != stored_state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter"
            )

        if provider_name not in self.providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid provider in session"
            )

        provider = self.providers[provider_name]

        # Create OAuth2 session
        oauth = OAuth2Session(
            client_id=provider.client_id,
            redirect_uri=redirect_uri,
            state=stored_state
        )

        # Exchange authorization code for token
        token_params = provider.get_token_request_params()
        token = oauth.fetch_token(
            provider.token_url,
            authorization_response=str(request.url),
            client_secret=provider.client_secret,
            **token_params
        )

        # Clear the temporary OAuth session data
        self._clear_session(request)

        # Handle scope format - convert list to space-delimited string if needed
        scope = token.get("scope")
        if isinstance(scope, list):
            scope = " ".join(scope)

        # Build token response data
        token_data = {
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token"),
            "token_type": token.get("token_type", "Bearer"),
            "expires_in": token.get("expires_in"),
            "scope": scope,
            "id_token": token.get("id_token")
        }

        # Double-redirect mode: redirect to gateway with tokens in URL fragment
        if double_redirect_mode and gateway_redirect_uri:
            log.info(f"Double-redirect mode: redirecting to {gateway_redirect_uri}")

            # Build URL fragment with tokens (more secure than query params)
            from urllib.parse import urlencode

            # Only include non-None values
            fragment_params = {k: v for k, v in token_data.items() if v is not None}
            hash_fragment = urlencode(fragment_params)

            final_redirect = f"{gateway_redirect_uri}#{hash_fragment}"

            # Create redirect response
            response = RedirectResponse(url=final_redirect, status_code=302)

            # Clear session cookie
            response.delete_cookie("oauth_session_id")

            return response

        # Legacy mode: return tokens as JSON (for backward compatibility)
        log.info("Legacy mode: returning tokens as JSON")
        return TokenResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_type=token_data["token_type"],
            expires_in=token_data["expires_in"],
            scope=token_data["scope"]
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Callback failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication callback failed"
        )
```

### 3. Update MCP Gateway OAuth Handler

**File: `/Users/edfunnekotter/github/solace-agent-mesh/src/solace_agent_mesh/gateway/mcp/oauth_handler.py`**

#### 3.1. Modify `handle_authorize` Method

**Current code (lines 162-196):**

Replace with this updated version:

```python
async def handle_authorize(
    self, request: Request, redirect_uri: Optional[str] = None
) -> RedirectResponse:
    """
    Handle authorization request from MCP client.

    This redirects the user to SAM's OAuth2 service using double-redirect mode,
    which will then redirect to the identity provider (Azure AD, Google, etc.).

    Args:
        request: FastAPI request object
        redirect_uri: Optional redirect URI override

    Returns:
        Redirect response to SAM OAuth2 service
    """
    log.info("Handling OAuth authorization request")

    # Create state for CSRF protection
    state = await self.state_manager.create_state(
        {"redirect_uri": redirect_uri or self.callback_url}
    )

    # Build authorization URL for SAM's OAuth2 service using double-redirect mode
    # NEW: Pass gateway_redirect_uri parameter to enable double-redirect
    params = {
        "provider": self.oauth_provider,
        "gateway_redirect_uri": self.callback_url,  # NEW: Enable double-redirect
        "state": state,  # Our own state for CSRF protection
    }

    auth_url = f"{self.oauth_service_url}/login?{urlencode(params)}"

    log.debug("Redirecting to SAM OAuth2 service (double-redirect mode): %s", auth_url)
    return RedirectResponse(url=auth_url, status_code=302)
```

#### 3.2. Modify `handle_callback` Method

**Current code (lines 198-273):**

Replace with this updated version:

```python
async def handle_callback(
    self, request: Request, code: Optional[str] = None, state: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle OAuth callback from SAM's OAuth2 service (double-redirect mode).

    In double-redirect mode, SAM exchanges the code for tokens and redirects
    here with tokens in the URL fragment. We extract them and return to client.

    Args:
        request: FastAPI request object
        code: Authorization code (NOT used in double-redirect mode)
        state: State value for CSRF validation

    Returns:
        Dictionary with access_token, refresh_token, expires_in, etc.

    Raises:
        HTTPException: If validation fails
    """
    log.info("Handling OAuth callback (double-redirect mode)")

    # In double-redirect mode, tokens come in URL fragment, not as query params
    # However, URL fragments are not sent to the server by browsers!
    # We need to use JavaScript to extract them and send via POST

    # Check if this is the initial callback (no tokens yet)
    # In this case, return HTML with JavaScript to extract tokens from fragment
    if not request.query_params.get("access_token"):
        log.debug("Returning token extraction HTML")
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Processing OAuth Callback...</title>
            <script>
                // Extract tokens from URL fragment
                const hash = window.location.hash.substring(1);
                const params = new URLSearchParams(hash);

                // Check for error
                const error = params.get('error');
                if (error) {
                    const error_description = params.get('error_description') || 'Authentication failed';
                    document.body.innerHTML = '<h1>Authentication Error</h1><p>' + error + ': ' + error_description + '</p>';
                    throw new Error(error + ': ' + error_description);
                }

                // Build token object
                const tokens = {
                    access_token: params.get('access_token'),
                    refresh_token: params.get('refresh_token'),
                    token_type: params.get('token_type'),
                    expires_in: params.get('expires_in'),
                    scope: params.get('scope'),
                    id_token: params.get('id_token')
                };

                // Remove null values
                Object.keys(tokens).forEach(key => {
                    if (tokens[key] === null) delete tokens[key];
                });

                // Validate we have at least access_token
                if (!tokens.access_token) {
                    document.body.innerHTML = '<h1>Error</h1><p>No access token received</p>';
                    throw new Error('No access token in callback');
                }

                // Display success message
                document.body.innerHTML = '<h1>Authentication Successful</h1><p>You can close this window.</p>';

                // Send tokens back to MCP client via postMessage (if in iframe)
                if (window.opener) {
                    window.opener.postMessage({ type: 'oauth_callback', tokens: tokens }, '*');
                    window.close();
                } else if (window.parent !== window) {
                    window.parent.postMessage({ type: 'oauth_callback', tokens: tokens }, '*');
                }

                // Also make them available for direct access
                window.oauthTokens = tokens;

                console.log('OAuth callback processed successfully');
            </script>
        </head>
        <body>
            <h1>Processing authentication...</h1>
            <p>Please wait...</p>
        </body>
        </html>
        """)

    # If we get here, tokens were sent as query params (fallback or direct call)
    # This shouldn't normally happen in double-redirect mode, but handle it anyway

    log.warning("Tokens received as query params (unexpected in double-redirect mode)")

    # Validate state (CSRF protection) if provided
    if state:
        state_data = await self.state_manager.validate_and_consume_state(state)
        if not state_data:
            log.error("Invalid or expired OAuth state")
            raise HTTPException(
                status_code=400, detail="Invalid or expired state parameter"
            )

    # Extract tokens from query params
    access_token = request.query_params.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Missing access token")

    tokens = {
        "access_token": access_token,
        "refresh_token": request.query_params.get("refresh_token"),
        "token_type": request.query_params.get("token_type", "Bearer"),
        "expires_in": request.query_params.get("expires_in"),
        "scope": request.query_params.get("scope"),
        "id_token": request.query_params.get("id_token"),
    }

    # Remove None values
    tokens = {k: v for k, v in tokens.items() if v is not None}

    log.info("Successfully extracted tokens from callback")
    return tokens
```

**IMPORTANT NOTE:** The callback handling is complex because URL fragments (the `#` part) are not sent to the server by browsers. The MCP client must handle extracting tokens from the fragment. The HTML/JavaScript above is a fallback for browser-based flows. For programmatic MCP clients, they should:

1. Follow the redirect to `http://localhost:8090/oauth/callback#access_token=...`
2. Extract tokens from the URL fragment themselves
3. Use the tokens in subsequent MCP requests

### 4. Testing

#### 4.1. Test Configuration

Update `/Users/edfunnekotter/github/solace-chat/configs/auth/oauth2_config.yaml`:

```yaml
# Security configuration
security:
  # Gateway redirect URI whitelist
  gateway_redirect_whitelist:
    - "http://localhost:*"
    - "http://127.0.0.1:*"
  strict_redirect_validation: false
```

Update `/Users/edfunnekotter/github/solace-chat/configs/gateways/mcp_gateway_example.yaml`:

```yaml
# Authentication Configuration
enable_auth: true
external_auth_service_url: http://localhost:8050
external_auth_provider: azure
dev_mode: false
```

#### 4.2. Test Steps

1. **Start SAM with OAuth2 service:**
   ```bash
   sam run configs/auth/oauth2_server.yaml configs/gateways/mcp_gateway_example.yaml configs/agents/main_orchestrator.yaml
   ```

2. **Verify OAuth metadata endpoint:**
   ```bash
   curl http://localhost:8090/.well-known/oauth-authorization-server | jq
   ```

3. **Test authorization flow:**
   ```bash
   # Open in browser:
   open http://localhost:8090/oauth/authorize

   # Should redirect to:
   # 1. http://localhost:8050/login?provider=azure&gateway_redirect_uri=http://localhost:8090/oauth/callback&state=...
   # 2. Azure AD login page
   # 3. http://localhost:8050/callback?code=...&state=...
   # 4. http://localhost:8090/oauth/callback#access_token=...&refresh_token=...
   ```

4. **Verify tokens in URL fragment:**
   - Check browser's address bar shows `#access_token=...`
   - Open browser console and check `window.oauthTokens`

5. **Test with Claude Code:**
   - Claude Code should automatically handle OAuth flow
   - Check that tool calls include `Authorization: Bearer <token>` header

## Security Considerations

### 1. Open Redirect Vulnerability

**Risk:** Without validation, attackers could use SAM as an open redirect:
```
http://localhost:8050/login?gateway_redirect_uri=https://evil.com
```

**Mitigation:** The `_validate_gateway_redirect_uri()` method checks against whitelist.

**Configuration:**
```yaml
security:
  gateway_redirect_whitelist:
    # Development
    - "http://localhost:*"
    # Production - be specific
    - "https://gateway.yourdomain.com/oauth/callback"
  strict_redirect_validation: true  # Disable wildcards in production
```

### 2. Token Exposure in URL

**Risk:** Tokens in URL fragments can be:
- Logged by browsers
- Leaked via Referer headers (though fragments are not included)
- Visible in browser history

**Mitigation:**
- URL fragments are NOT sent in HTTP requests (safer than query params)
- Tokens should be short-lived (handled by Azure AD)
- Use HTTPS in production
- Clear URL fragment after extraction (JavaScript)

**Best Practice:** For production, consider adding a POST endpoint for token delivery instead of URL fragments.

### 3. State Token Validation

**Risk:** CSRF attacks if state is not validated

**Mitigation:**
- MCP gateway generates its own state token
- Stored in `OAuthStateManager` with 10-minute TTL
- One-time use (consumed after validation)

### 4. Whitelist Maintenance

**Important:** Update the whitelist when:
- Adding new gateway instances
- Changing ports/domains
- Deploying to new environments

## Backwards Compatibility

The implementation maintains backward compatibility:

1. **Legacy mode (existing behavior):**
   - Don't pass `gateway_redirect_uri` parameter
   - Gateway's `redirect_uri` must be registered in Azure
   - Tokens returned as JSON from `/callback`

2. **New double-redirect mode:**
   - Pass `gateway_redirect_uri` parameter
   - Only SAM's callback needs Azure registration
   - Tokens returned in URL fragment via redirect

WebUI and other existing gateways continue working without changes.

## Migration Path

1. **Phase 1: Deploy OAuth2 service changes**
   - Add whitelist configuration
   - Deploy updated `oauth2_service.py`
   - Existing gateways continue working (legacy mode)

2. **Phase 2: Update gateways to use double-redirect**
   - Update MCP gateway to pass `gateway_redirect_uri`
   - Test with Azure AD
   - Optionally update other gateways

3. **Phase 3 (Optional): Remove legacy mode**
   - After all gateways migrated, can simplify code
   - Force double-redirect mode only

## Troubleshooting

### Gateway redirect blocked

**Error:** "Invalid or unauthorized gateway_redirect_uri"

**Cause:** URI not in whitelist

**Solution:** Add to `gateway_redirect_whitelist` in config

### Tokens not appearing in callback

**Symptom:** Callback URL has no fragment

**Cause:** Session data lost or `/callback` not in double-redirect mode

**Debug:**
```python
# In oauth2_service.py, add logging:
log.info(f"Callback session data: {session}")
log.info(f"Double-redirect mode: {session.get('double_redirect_mode')}")
```

### State validation failures

**Symptom:** "Invalid or expired state parameter"

**Cause:** State timeout or cookie issues

**Solution:**
- Increase `OAuthStateManager` TTL
- Check browser cookies are enabled
- Verify `oauth_session_id` cookie is set

## Summary of Changes

### Files Modified

1. **`configs/auth/oauth2_config.yaml`**
   - Add `gateway_redirect_whitelist` configuration
   - Add `strict_redirect_validation` option

2. **`oauth2_service.py`** (enterprise repo)
   - Add `_validate_gateway_redirect_uri()` method
   - Modify `/login` endpoint to support `gateway_redirect_uri` parameter
   - Modify `/callback` endpoint to redirect with tokens in fragment

3. **`gateway/mcp/oauth_handler.py`** (community repo)
   - Update `handle_authorize()` to pass `gateway_redirect_uri`
   - Update `handle_callback()` to handle token extraction from fragment

### Total Lines of Code

- **OAuth2 service:** ~150 lines modified/added
- **MCP gateway:** ~50 lines modified
- **Configuration:** ~10 lines added
- **Documentation:** This document

## Questions or Issues

If you encounter any issues during implementation, check:

1. Whitelist configuration includes your gateway URI
2. Session cookies are working (check browser dev tools)
3. State validation is not timing out (increase TTL if needed)
4. Azure AD callback is reaching SAM (check logs)

For additional help, refer to the security considerations section and testing steps above.
