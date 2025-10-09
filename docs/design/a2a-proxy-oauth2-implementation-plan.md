# OAuth 2.0 Client Credentials Flow - Implementation Plan

## Overview

This document provides a step-by-step implementation plan for adding OAuth 2.0 Client Credentials flow support to the A2A Proxy component. This plan covers only the code implementation and does not include testing or rollout strategies.

**Related Documents:**
- Design Document: `docs/design/a2a-proxy-oauth2-client-credentials-design.md`
- Test Checklist: `a2a-proxy-test-checklist.md`

---

## Implementation Steps

### Phase 1: Token Cache Infrastructure

#### Step 1: Create OAuth2TokenCache Module

**File:** `src/solace_agent_mesh/agent/proxies/a2a/oauth_token_cache.py` (NEW)

**Objective:** Implement the in-memory token cache with expiration support.

**Tasks:**
1. Create the new file
2. Add necessary imports (`asyncio`, `time`, `dataclasses`, `Dict`, `Optional`)
3. Define the `CachedToken` dataclass with fields:
   - `access_token: str`
   - `expires_at: float` (Unix timestamp)
4. Implement the `OAuth2TokenCache` class with:
   - `__init__()`: Initialize empty cache dict and asyncio.Lock
   - `async def get(agent_name: str) -> Optional[str]`: Retrieve token with expiration check
   - `async def set(agent_name: str, access_token: str, cache_duration_seconds: int)`: Store token with expiration
   - `async def invalidate(agent_name: str)`: Remove token from cache
5. Add comprehensive docstrings for all methods
6. Add logging statements at DEBUG and INFO levels

**Key Implementation Details:**
- Use `asyncio.Lock` for thread-safe operations
- Implement lazy expiration (check on `get()`, no background cleanup)
- Log cache hits/misses at DEBUG level
- Log invalidations at INFO level

---

### Phase 2: Configuration Schema Updates

#### Step 2: Update A2AProxyApp Configuration Schema

**File:** `src/solace_agent_mesh/agent/proxies/a2a/app.py`

**Objective:** Extend the configuration schema to support OAuth 2.0 parameters.

**Tasks:**
1. Locate the `proxied_agents_schema["items"]["properties"]["authentication"]` definition
2. Modify the authentication schema to support a `type` field with enum values:
   - `"static_bearer"`
   - `"static_apikey"`
   - `"oauth2_client_credentials"`
3. Add new properties for OAuth 2.0:
   - `token_url` (string, required for oauth2_client_credentials)
   - `client_id` (string, required for oauth2_client_credentials)
   - `client_secret` (string, required for oauth2_client_credentials)
   - `scope` (string, optional)
   - `token_cache_duration_seconds` (integer, optional, default 3300)
4. Update the description to document the new authentication types
5. Ensure backward compatibility by making `type` optional (will be inferred from `scheme` if absent)

**Key Implementation Details:**
- Keep existing `scheme` and `token` fields for backward compatibility
- Add clear descriptions for each new field
- Document the default cache duration (3300 seconds = 55 minutes)

---

### Phase 3: Token Acquisition Logic

#### Step 3: Add OAuth2TokenCache to A2AProxyComponent

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Initialize the token cache in the component.

**Tasks:**
1. Add import: `from .oauth_token_cache import OAuth2TokenCache`
2. In `__init__()`, after initializing `_auth_interceptor`, add:
   ```python
   self._oauth_token_cache = OAuth2TokenCache()
   ```
3. Add a docstring comment explaining the cache's purpose

---

#### Step 4: Implement _fetch_oauth2_token() Method

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Implement the core token acquisition logic.

**Tasks:**
1. Add the method signature after `_get_or_create_a2a_client()`:
   ```python
   async def _fetch_oauth2_token(
       self, 
       agent_name: str, 
       auth_config: dict
   ) -> str:
   ```
2. Implement the method body following this flow:
   - **Step 4.1:** Check cache first
     - Call `self._oauth_token_cache.get(agent_name)`
     - If hit, log at DEBUG level and return token
   - **Step 4.2:** Validate required parameters
     - Extract `token_url`, `client_id`, `client_secret` from `auth_config`
     - Raise `ValueError` if any are missing
   - **Step 4.3:** Extract optional parameters
     - Get `scope` (default: empty string)
     - Get `token_cache_duration_seconds` (default: 3300)
   - **Step 4.4:** Log token acquisition attempt at INFO level
   - **Step 4.5:** Create temporary httpx client with 30-second timeout
   - **Step 4.6:** Execute POST request
     - URL: `token_url`
     - Headers: `Content-Type: application/x-www-form-urlencoded`, `Accept: application/json`
     - Body: `grant_type=client_credentials&client_id=...&client_secret=...&scope=...`
   - **Step 4.7:** Parse response
     - Extract `access_token` from JSON response
     - Raise `ValueError` if missing
   - **Step 4.8:** Cache the token
     - Call `self._oauth_token_cache.set(agent_name, access_token, cache_duration)`
   - **Step 4.9:** Log success at INFO level
   - **Step 4.10:** Return access token
3. Add comprehensive error handling:
   - Catch `httpx.HTTPStatusError` and log at ERROR level with status code and response text
   - Catch `httpx.RequestError` and log at ERROR level
   - Catch generic `Exception` and log with stack trace
   - Re-raise all exceptions to propagate to caller
4. Add detailed docstring with Args, Returns, and Raises sections

**Key Implementation Details:**
- Use `async with httpx.AsyncClient(timeout=30.0) as client:` for the token request
- Log the token URL and scope (but NOT the client_secret or access_token)
- Use `log_identifier` format: `{self.log_identifier}[OAuth2:{agent_name}]`

---

### Phase 4: Client Creation Integration

#### Step 5: Update _get_or_create_a2a_client() for Auth Type Routing

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Integrate OAuth 2.0 authentication into the client creation flow.

**Tasks:**
1. Locate the authentication setup section (currently around line 100-110)
2. Replace the existing simple authentication logic with type-based routing:
   - **Step 5.1:** Extract `auth_type` from config
     - Check for `auth_config.get("type")`
     - If absent, infer from `scheme` field (backward compatibility)
     - Log deprecation warning if using legacy format
   - **Step 5.2:** Implement routing logic with if/elif/else:
     - **Case 1:** `auth_type == "static_bearer"`
       - Validate `token` is present
       - Call `self._credential_store.set_credentials(session_id, "bearer", token)`
     - **Case 2:** `auth_type == "static_apikey"`
       - Validate `token` is present
       - Call `self._credential_store.set_credentials(session_id, "apikey", token)`
     - **Case 3:** `auth_type == "oauth2_client_credentials"` (NEW)
       - Wrap in try/except block
       - Call `access_token = await self._fetch_oauth2_token(agent_name, auth_config)`
       - Call `self._credential_store.set_credentials(session_id, "bearer", access_token)`
       - Log error and re-raise on failure
     - **Default:** Raise `ValueError` for unsupported type
3. Add logging at INFO level for each authentication type used
4. Update method docstring to document OAuth 2.0 support

**Key Implementation Details:**
- Maintain exact backward compatibility with existing configs
- Log at WARNING level when using legacy config format
- Ensure all error messages include the agent name for debugging

---

### Phase 5: Token Refresh on Authentication Failure

#### Step 6: Implement _handle_auth_error() Method

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Handle 401 errors by invalidating cached tokens.

**Tasks:**
1. Add the method after `_fetch_oauth2_token()`:
   ```python
   async def _handle_auth_error(
       self, 
       agent_name: str, 
       task_context: "ProxyTaskContext"
   ) -> bool:
   ```
2. Implement the method body:
   - **Step 6.1:** Retrieve agent configuration
     - Search `self.proxied_agents_config` for matching agent
     - Return `False` if not found
   - **Step 6.2:** Check authentication type
     - Extract `auth_config` and determine type
     - If not `oauth2_client_credentials`, return `False` (no retry for static tokens)
   - **Step 6.3:** Invalidate cached token
     - Call `await self._oauth_token_cache.invalidate(agent_name)`
     - Log at INFO level
   - **Step 6.4:** Remove cached A2AClient
     - Pop from `self._a2a_clients`
     - Close the httpx client if not already closed
     - Log at INFO level
   - **Step 6.5:** Return `True` to signal retry should be attempted
3. Add comprehensive docstring
4. Add logging at each step

**Key Implementation Details:**
- Use `log_identifier` format: `{self.log_identifier}[AuthError:{agent_name}]`
- Only invalidate and retry for OAuth 2.0 authenticated agents
- Ensure httpx client is properly closed to avoid resource leaks

---

#### Step 7: Add Retry Logic to _forward_request()

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Implement single retry on 401 errors for OAuth 2.0 agents.

**Tasks:**
1. Locate the `_forward_request()` method
2. Wrap the existing forwarding logic in a retry loop:
   - **Step 7.1:** Initialize retry counter
     - `max_auth_retries = 1`
     - `auth_retry_count = 0`
   - **Step 7.2:** Create while loop: `while auth_retry_count <= max_auth_retries:`
   - **Step 7.3:** Move existing try/except block inside the loop
   - **Step 7.4:** Add specific handling for `A2AClientHTTPError`:
     - Check if `e.status_code == 401` and `auth_retry_count < max_auth_retries`
     - If true, call `should_retry = await self._handle_auth_error(agent_name, task_context)`
     - If `should_retry` is True:
       - Log at WARNING level: "Received 401 Unauthorized. Attempting token refresh (retry X/Y)"
       - Increment `auth_retry_count`
       - `continue` to retry
     - Otherwise, re-raise the exception
   - **Step 7.5:** Add `break` statement after successful forwarding
3. Update method docstring to document retry behavior
4. Add logging for retry attempts

**Key Implementation Details:**
- Only retry once (prevents infinite loops)
- Only retry on 401 errors (not other HTTP errors)
- Only retry if `_handle_auth_error()` returns True (OAuth 2.0 agents only)
- Log each retry attempt with clear messaging

---

### Phase 6: Cleanup and Documentation

#### Step 8: Update Component Cleanup

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Ensure token cache is properly cleaned up on shutdown.

**Tasks:**
1. Locate the `cleanup()` method
2. Add a comment noting that the token cache is automatically garbage collected
3. No explicit cleanup needed (cache is in-memory only)

**Key Implementation Details:**
- Token cache cleanup is automatic via Python garbage collection
- No persistent state to clean up
- Document this behavior in a comment

---

#### Step 9: Add Module-Level Documentation

**File:** `src/solace_agent_mesh/agent/proxies/a2a/oauth_token_cache.py`

**Objective:** Add comprehensive module docstring.

**Tasks:**
1. Add module-level docstring at the top of the file:
   ```python
   """
   OAuth 2.0 token caching for A2A proxy authentication.
   
   This module provides an in-memory cache for OAuth 2.0 access tokens
   with automatic expiration. Tokens are cached per agent to minimize
   token acquisition overhead and reduce load on authorization servers.
   
   The cache is thread-safe using asyncio.Lock and implements lazy
   expiration (tokens are checked for expiration on retrieval).
   """
   ```

---

#### Step 10: Update A2AProxyComponent Docstring

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Document OAuth 2.0 support in the class docstring.

**Tasks:**
1. Locate the class docstring for `A2AProxyComponent`
2. Add a section documenting authentication support:
   ```python
   """
   Concrete proxy component for standard A2A-over-HTTPS agents.
   
   Supports multiple authentication methods:
   - Static bearer tokens
   - Static API keys
   - OAuth 2.0 Client Credentials flow (with automatic token refresh)
   
   OAuth 2.0 tokens are cached in memory with configurable expiration
   and automatically refreshed on 401 errors.
   """
   ```

---

### Phase 7: Error Handling Enhancements

#### Step 11: Add Detailed Error Messages

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Ensure all error messages are clear and actionable.

**Tasks:**
1. Review all error messages in the new methods
2. Ensure each error includes:
   - The agent name
   - The specific parameter that's missing/invalid
   - Suggested action to fix the issue
3. Examples:
   - `ValueError(f"OAuth 2.0 client credentials flow requires 'token_url', 'client_id', and 'client_secret' for agent '{agent_name}'. Please check your configuration.")`
   - `ValueError(f"Authentication type '{auth_type}' is not supported for agent '{agent_name}'. Supported types: static_bearer, static_apikey, oauth2_client_credentials.")`

---

#### Step 12: Add Configuration Validation

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Validate OAuth 2.0 configuration at startup.

**Tasks:**
1. In `__init__()`, after initializing the token cache, add validation:
   - Iterate through `self.proxied_agents_config`
   - For each agent with `authentication.type == "oauth2_client_credentials"`:
     - Validate `token_url` is a valid HTTPS URL
     - Validate `client_id` is non-empty
     - Validate `client_secret` is non-empty
     - Validate `token_cache_duration_seconds` is > 0 if specified
   - Log warnings for any validation failures
   - Optionally raise exception to fail fast

**Key Implementation Details:**
- Use `urlparse()` to validate URL format
- Check for `https://` scheme (not `http://`)
- Log at ERROR level for validation failures
- Consider making this a separate `_validate_oauth_config()` method

---

### Phase 8: Logging Standardization

#### Step 13: Standardize Log Messages

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Ensure consistent logging format across all OAuth 2.0 code.

**Tasks:**
1. Review all log statements in new methods
2. Ensure consistent format:
   - Use `log_identifier` prefix for all messages
   - Include agent name in context-specific identifiers
   - Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)
3. Standard formats:
   - DEBUG: `"%s Using cached OAuth token for '%s'", log_identifier, agent_name`
   - INFO: `"%s Successfully obtained OAuth 2.0 token (cached for %ds)", log_identifier, cache_duration`
   - WARNING: `"%s Received 401 Unauthorized. Attempting token refresh (retry %d/%d)", log_identifier, retry_count, max_retries`
   - ERROR: `"%s OAuth 2.0 token request failed with status %d: %s", log_identifier, status_code, response_text`

---

### Phase 9: Security Hardening

#### Step 14: Ensure Secrets Are Not Logged

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Verify that sensitive data is never logged.

**Tasks:**
1. Review all log statements in OAuth 2.0 code
2. Ensure the following are NEVER logged:
   - `client_secret`
   - `access_token`
   - Full `auth_config` dictionary (may contain secrets)
3. Safe to log:
   - `token_url`
   - `client_id`
   - `scope`
   - `agent_name`
   - Token cache duration
4. Add comments warning about sensitive data:
   ```python
   # SECURITY: Never log client_secret or access_token
   log.info("%s Fetching OAuth token from %s", log_identifier, token_url)
   ```

---

#### Step 15: Add HTTPS Enforcement

**File:** `src/solace_agent_mesh/agent/proxies/a2a/component.py`

**Objective:** Ensure OAuth 2.0 token URLs use HTTPS.

**Tasks:**
1. In `_fetch_oauth2_token()`, before making the request:
   - Parse `token_url` with `urlparse()`
   - Check if scheme is `https`
   - Raise `ValueError` if not HTTPS
   - Log at ERROR level
2. Example:
   ```python
   from urllib.parse import urlparse
   
   parsed_url = urlparse(token_url)
   if parsed_url.scheme != 'https':
       raise ValueError(
           f"OAuth 2.0 token_url must use HTTPS for security. "
           f"Got: {parsed_url.scheme}://"
       )
   ```

---

### Phase 10: Final Integration

#### Step 16: Update __init__.py Exports

**File:** `src/solace_agent_mesh/agent/proxies/a2a/__init__.py`

**Objective:** Ensure new module is properly exported.

**Tasks:**
1. Add import for `OAuth2TokenCache` (if needed for external access)
2. Update `__all__` list if present
3. Add module docstring if not present

**Note:** This may not be necessary if the cache is only used internally by the component.

---

#### Step 17: Add Type Hints

**Files:** All modified files

**Objective:** Ensure all new code has proper type hints.

**Tasks:**
1. Review all new methods and functions
2. Add type hints for:
   - All parameters
   - Return types
   - Instance variables
3. Import necessary types from `typing` module
4. Use `Optional[T]` for nullable types
5. Use `Dict[str, Any]` for config dictionaries

---

#### Step 18: Add Inline Comments

**Files:** All modified files

**Objective:** Add explanatory comments for complex logic.

**Tasks:**
1. Add comments explaining:
   - Why we use 55-minute cache duration (5-minute safety margin)
   - Why we only retry once (prevent infinite loops)
   - Why we remove the A2AClient on 401 (force fresh token fetch)
   - Why we use asyncio.Lock (thread safety)
2. Keep comments concise and focused on "why" not "what"

---

## Implementation Order Summary

**Recommended implementation order:**

1. **Steps 1-2:** Token cache and configuration schema (foundation)
2. **Steps 3-4:** Token acquisition logic (core functionality)
3. **Steps 5:** Client creation integration (connect to existing code)
4. **Steps 6-7:** Token refresh logic (error handling)
5. **Steps 8-10:** Documentation and cleanup
6. **Steps 11-15:** Error handling and security hardening
7. **Steps 16-18:** Final polish and type hints

**Estimated Implementation Time:**
- Phase 1-2: 1-2 hours
- Phase 3-4: 2-3 hours
- Phase 5: 1-2 hours
- Phase 6-10: 2-3 hours
- **Total: 6-10 hours**

---

## Pre-Implementation Checklist

Before starting implementation, ensure:

- [ ] Design document has been reviewed and approved
- [ ] All team members understand the OAuth 2.0 Client Credentials flow
- [ ] Development environment is set up with Python 3.10+
- [ ] All dependencies are installed (`httpx`, `a2a-sdk`, etc.)
- [ ] Git branch created for this feature
- [ ] Test environment available for manual testing

---

## Post-Implementation Checklist

After completing implementation:

- [ ] All code has been written and tested locally
- [ ] All type hints are present and correct
- [ ] All docstrings are complete and accurate
- [ ] All log messages follow the standard format
- [ ] No secrets are logged
- [ ] HTTPS enforcement is in place
- [ ] Backward compatibility is maintained
- [ ] Code has been reviewed by at least one other developer
- [ ] Manual testing completed with real OAuth 2.0 provider
- [ ] Ready for unit test implementation (separate phase)

---

## Notes for Implementer

### Common Pitfalls to Avoid

1. **Don't log secrets:** Never log `client_secret` or `access_token`
2. **Don't cache errors:** Only cache successful tokens
3. **Don't retry indefinitely:** Limit to one retry to prevent loops
4. **Don't forget cleanup:** Ensure httpx clients are closed
5. **Don't break backward compatibility:** Support legacy config format

### Testing During Implementation

While formal tests are in a separate phase, during implementation you should:

1. Test with a real OAuth 2.0 provider (e.g., Auth0, Okta)
2. Test token caching (verify cache hits in logs)
3. Test token expiration (use short cache duration)
4. Test 401 retry (revoke token manually)
5. Test backward compatibility (use old config format)
6. Test error cases (invalid credentials, network errors)

### Debugging Tips

1. Set log level to DEBUG to see cache operations
2. Use short cache durations (e.g., 60 seconds) for testing
3. Monitor token acquisition in OAuth provider's dashboard
4. Use `httpx` logging to see actual HTTP requests
5. Test with `curl` to verify token endpoint works

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-09 | AI Assistant | Initial implementation plan |

---

**End of Document**
