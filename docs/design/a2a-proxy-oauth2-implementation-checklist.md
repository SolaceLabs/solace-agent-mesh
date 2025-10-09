# OAuth 2.0 Client Credentials - Implementation Checklist

**Related Documents:**
- Design: `docs/design/a2a-proxy-oauth2-client-credentials-design.md`
- Full Plan: `docs/design/a2a-proxy-oauth2-implementation-plan.md`

---

## Phase 1: Token Cache Infrastructure

- [x] **Step 1**: Create `oauth_token_cache.py` module
  - [x] Create file with imports
  - [x] Define `CachedToken` dataclass
  - [x] Implement `OAuth2TokenCache` class
  - [x] Add `__init__()`, `get()`, `set()`, `invalidate()` methods
  - [x] Add docstrings and logging

---

## Phase 2: Configuration Schema Updates

- [ ] **Step 2**: Update `app.py` configuration schema
  - [ ] Add `type` field with enum values
  - [ ] Add OAuth 2.0 properties (token_url, client_id, client_secret, scope, token_cache_duration_seconds)
  - [ ] Update descriptions
  - [ ] Ensure backward compatibility

---

## Phase 3: Token Acquisition Logic

- [ ] **Step 3**: Add OAuth2TokenCache to component
  - [ ] Import `OAuth2TokenCache`
  - [ ] Initialize in `__init__()`
  - [ ] Add docstring comment

- [ ] **Step 4**: Implement `_fetch_oauth2_token()` method
  - [ ] Add method signature
  - [ ] Check cache first
  - [ ] Validate required parameters
  - [ ] Extract optional parameters
  - [ ] Log token acquisition attempt
  - [ ] Create temporary httpx client
  - [ ] Execute POST request
  - [ ] Parse response
  - [ ] Cache the token
  - [ ] Log success
  - [ ] Add comprehensive error handling
  - [ ] Add detailed docstring

---

## Phase 4: Client Creation Integration

- [ ] **Step 5**: Update `_get_or_create_a2a_client()` for auth routing
  - [ ] Extract `auth_type` from config
  - [ ] Implement backward compatibility logic
  - [ ] Add routing for `static_bearer`
  - [ ] Add routing for `static_apikey`
  - [ ] Add routing for `oauth2_client_credentials` (NEW)
  - [ ] Add logging for each auth type
  - [ ] Update method docstring

---

## Phase 5: Token Refresh on Authentication Failure

- [ ] **Step 6**: Implement `_handle_auth_error()` method
  - [ ] Add method signature
  - [ ] Retrieve agent configuration
  - [ ] Check authentication type
  - [ ] Invalidate cached token
  - [ ] Remove cached A2AClient
  - [ ] Return True/False appropriately
  - [ ] Add comprehensive docstring
  - [ ] Add logging at each step

- [ ] **Step 7**: Add retry logic to `_forward_request()`
  - [ ] Initialize retry counter
  - [ ] Create while loop
  - [ ] Move existing try/except inside loop
  - [ ] Add specific handling for `A2AClientHTTPError` with status 401
  - [ ] Call `_handle_auth_error()` on 401
  - [ ] Increment counter and continue if should retry
  - [ ] Add break after successful forwarding
  - [ ] Update method docstring
  - [ ] Add logging for retry attempts

---

## Phase 6: Cleanup and Documentation

- [ ] **Step 8**: Document token cache lifecycle
  - [ ] Locate `cleanup()` method
  - [ ] Add docstring note about automatic garbage collection
  - [ ] Document no explicit cleanup needed

- [ ] **Step 9**: Add configuration validation
  - [ ] Add validation in `__init__()` after token cache init
  - [ ] Iterate through `proxied_agents_config`
  - [ ] Validate `token_url` is HTTPS
  - [ ] Validate `client_id` is non-empty
  - [ ] Validate `client_secret` is non-empty
  - [ ] Validate `token_cache_duration_seconds` > 0
  - [ ] Log errors for validation failures
  - [ ] Raise exception to fail fast

---

## Phase 7: Security Hardening

- [ ] **Step 10**: Ensure secrets not logged & add HTTPS enforcement
  - [ ] Review all log statements in OAuth 2.0 code
  - [ ] Verify `client_secret` never logged
  - [ ] Verify `access_token` never logged
  - [ ] Verify full `auth_config` never logged
  - [ ] Add security warning comments
  - [ ] Add HTTPS enforcement in `_fetch_oauth2_token()`
  - [ ] Parse `token_url` with `urlparse()`
  - [ ] Check scheme is `https`
  - [ ] Raise `ValueError` if not HTTPS

---

## Phase 8: Code Quality

- [ ] **Step 11**: Add type hints and inline comments
  - [ ] Add type hints to all new methods (parameters, returns)
  - [ ] Add type hints to instance variables
  - [ ] Add inline comment: 55-minute cache duration rationale
  - [ ] Add inline comment: single retry rationale
  - [ ] Add inline comment: A2AClient removal rationale
  - [ ] Add inline comment: asyncio.Lock usage rationale
  - [ ] Verify all log messages use standard format
  - [ ] Verify all log messages use appropriate levels
  - [ ] Add/verify docstrings for all new methods

---

## Pre-Implementation Checklist

- [ ] Design document reviewed and approved
- [ ] Team understands OAuth 2.0 Client Credentials flow
- [ ] Development environment set up (Python 3.10+)
- [ ] All dependencies installed (`httpx`, `a2a-sdk`)
- [ ] Git branch created for this feature

---

## Post-Implementation Checklist

- [ ] All code written and tested locally
- [ ] All type hints present and correct
- [ ] All docstrings complete and accurate
- [ ] All log messages follow standard format
- [ ] No secrets logged
- [ ] HTTPS enforcement in place
- [ ] Backward compatibility maintained
- [ ] Code reviewed by at least one other developer
- [ ] Manual testing completed with real OAuth 2.0 provider
- [ ] Ready for unit test implementation (separate phase)

---

## Notes

- Estimated implementation time: 6-10 hours
- Each phase builds on the previous one
- Test incrementally as you implement
- Use short cache durations (e.g., 60s) during development for easier testing
