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

- [x] **Step 2**: Update `app.py` configuration schema
  - [x] Add `type` field with enum values
  - [x] Add OAuth 2.0 properties (token_url, client_id, client_secret, scope, token_cache_duration_seconds)
  - [x] Update descriptions
  - [x] Ensure backward compatibility

---

## Phase 3: Token Acquisition Logic

- [x] **Step 3**: Add OAuth2TokenCache to component
  - [x] Import `OAuth2TokenCache`
  - [x] Initialize in `__init__()`
  - [x] Add docstring comment

- [x] **Step 4**: Implement `_fetch_oauth2_token()` method
  - [x] Add method signature
  - [x] Check cache first
  - [x] Validate required parameters
  - [x] Extract optional parameters
  - [x] Log token acquisition attempt
  - [x] Create temporary httpx client
  - [x] Execute POST request
  - [x] Parse response
  - [x] Cache the token
  - [x] Log success
  - [x] Add comprehensive error handling
  - [x] Add detailed docstring

---

## Phase 4: Client Creation Integration

- [x] **Step 5**: Update `_get_or_create_a2a_client()` for auth routing
  - [x] Extract `auth_type` from config
  - [x] Implement backward compatibility logic
  - [x] Add routing for `static_bearer`
  - [x] Add routing for `static_apikey`
  - [x] Add routing for `oauth2_client_credentials` (NEW)
  - [x] Add logging for each auth type
  - [x] Update method docstring

---

## Phase 5: Token Refresh on Authentication Failure

- [x] **Step 6**: Implement `_handle_auth_error()` method
  - [x] Add method signature
  - [x] Retrieve agent configuration
  - [x] Check authentication type
  - [x] Invalidate cached token
  - [x] Remove cached A2AClient
  - [x] Return True/False appropriately
  - [x] Add comprehensive docstring
  - [x] Add logging at each step

- [x] **Step 7**: Add retry logic to `_forward_request()`
  - [x] Initialize retry counter
  - [x] Create while loop
  - [x] Move existing try/except inside loop
  - [x] Add specific handling for `A2AClientHTTPError` with status 401
  - [x] Call `_handle_auth_error()` on 401
  - [x] Increment counter and continue if should retry
  - [x] Add break after successful forwarding
  - [x] Update method docstring
  - [x] Add logging for retry attempts

---

## Phase 6: Cleanup and Documentation

- [x] **Step 8**: Document token cache lifecycle
  - [x] Locate `cleanup()` method
  - [x] Add docstring note about automatic garbage collection
  - [x] Document no explicit cleanup needed

- [x] **Step 9**: Add configuration validation
  - [x] Add validation in `__init__()` after token cache init
  - [x] Iterate through `proxied_agents_config`
  - [x] Validate `token_url` is HTTPS
  - [x] Validate `client_id` is non-empty
  - [x] Validate `client_secret` is non-empty
  - [x] Validate `token_cache_duration_seconds` > 0
  - [x] Log errors for validation failures
  - [x] Raise exception to fail fast

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

- [x] **Step 11**: Add type hints and inline comments
  - [x] Add type hints to all new methods (parameters, returns)
  - [x] Add type hints to instance variables
  - [x] Add inline comment: 55-minute cache duration rationale
  - [x] Add inline comment: single retry rationale
  - [x] Add inline comment: A2AClient removal rationale
  - [x] Add inline comment: asyncio.Lock usage rationale
  - [x] Verify all log messages use standard format
  - [x] Verify all log messages use appropriate levels
  - [x] Add/verify docstrings for all new methods

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
