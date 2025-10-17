# Phase 2 User Authentication Token Implementation Checklist

## Overview
This checklist tracks the implementation of user authentication token signing and verification in the SAM Trust Manager (Phase 2). All cryptographic implementation details (JWT) reside in the enterprise repository. Open source changes use generic security abstractions only.

## Security Abstraction Principle
The open source repository uses **generic security terminology** to avoid disclosing implementation details:
- ✅ Use: "authentication token", "auth token", "user claims", "security context"
- ❌ Avoid: "JWT", "JSON Web Token", "JWKS", specific cryptographic terms

This provides defense-in-depth and future flexibility to change security mechanisms.

---

## Prerequisites

### Enterprise Repository (Completed)
- [x] `TrustManager.sign_user_identity()` method implemented
- [x] `TrustManager.verify_user_identity_jwt()` method implemented
- [x] JWT configuration fields added to `TrustManagerConfig`
- [x] PyJWT dependency added
- [x] Unit tests for JWT signing
- [x] Unit tests for JWT verification
- [x] Documentation updated

---

## Open Source Repository Changes

### File 1: `src/solace_agent_mesh/gateway/base/component.py`

**Location:** `BaseGatewayComponent.submit_a2a_task()` method

#### Gateway User Claims Signing Integration

- [x] **Find insertion point**
  - Locate where `user_properties` dict is being built
  - After `authenticate_and_enrich_user()` call
  - Before `self.publish_a2a_message()` call

- [x] **Add trust manager check**
  - Guard: `if hasattr(self, 'trust_manager') and self.trust_manager:`
  - Log at DEBUG: "Trust Manager not available, proceeding without authentication token" (if no trust_manager)

- [x] **Call generic signing method**
  - Call: `trust_manager.sign_user_claims(user_info=user_identity, task_id=task_id)`
  - **Note**: Method name is generic - no mention of JWT
  - Wrap in try/except block
  - Catch generic Exception (enterprise exceptions may not be available)

- [x] **Handle signing success**
  - Store token in variable: `auth_token`
  - Add to user_properties: `user_properties["authToken"] = auth_token`
  - **Note**: Generic property name - no mention of JWT
  - Log at DEBUG: "Added authentication token to task {task_id}"

- [x] **Handle signing failure**
  - Log at ERROR: "Failed to sign user claims for task {task_id}: {error}"
  - Continue without token (degraded mode, don't block task)
  - Do NOT raise exception

- [x] **Add logging**
  - DEBUG: "Attempting to sign user claims for task {task_id}"
  - DEBUG: "Successfully signed user claims for task {task_id}" (on success)
  - Include task_id and user_id in log messages
  - **Important**: No mention of JWT in any log messages

---

### File 2: `src/solace_agent_mesh/agent/protocol/event_handlers.py`

**Location:** `handle_a2a_request()` function

#### Agent User Claims Verification Integration

- [x] **Find insertion point**
  - After A2ARequest is parsed and validated
  - After task_id is extracted
  - Before TaskExecutionContext is created
  - Before any ADK runner invocation

- [x] **Add trust manager check**
  - Guard: `if hasattr(component, 'trust_manager') and component.trust_manager:`
  - Log at DEBUG: "Trust Manager not available, skipping authentication verification" (if no trust_manager)

- [x] **Extract auth token from message**
  - Get: `auth_token = message.get_user_properties().get("authToken")`
  - **Note**: Generic property name - no mention of JWT
  - Log at DEBUG: "Extracting authentication token from user properties for task {task_id}"

- [x] **Handle missing auth token**
  - Check: `if auth_token is None:`
  - Log at WARNING: "Trust Manager enabled but no authentication token provided for task {task_id}"
  - Create error response: `create_invalid_request_error_response()`
  - Error message: "Authentication failed" (generic)
  - Error data: `{"reason": "authentication_failed", "task_id": task_id}`
  - Publish error response to reply topic
  - Call `message.call_acknowledgements()` (ACK, don't retry)
  - Return early (do not process task)

- [x] **Call generic verification method**
  - Call: `component.trust_manager.verify_user_claims(auth_token=auth_token, task_id=task_id)`
  - **Note**: Method name is generic - no mention of JWT
  - Wrap in try/except block
  - Catch generic Exception (enterprise exceptions may not be available)

- [x] **Handle verification success**
  - Store verified claims: `verified_claims = <result>`
  - Extract user identity from claims (sub, name, email, roles, scopes)
  - Store in a2a_context: `a2a_context["verified_user_identity"] = {...}` (claims only, NOT raw token)
  - Log at INFO: "Successfully verified user claims for user '{sub}' (task: {task_id})"
  - **Important**: No mention of JWT in log messages

- [x] **Handle verification failure**
  - Log at WARNING: "User authentication verification failed for task {task_id}: {error}" (server-side detail)
  - Create error response: `create_invalid_request_error_response()`
  - Error message: "Authentication failed" (generic, no details)
  - Error data: `{"reason": "authentication_failed", "task_id": task_id}`
  - Publish error response to reply topic
  - Call `message.call_acknowledgements()` (ACK, don't retry invalid tokens)
  - Return early (do not process task)

- [x] **Store auth token for peer delegation using generic security storage**
  - After successful verification
  - Use TaskExecutionContext generic security storage: `task_context.set_security_data("auth_token", auth_token)`
  - **Note**: Opaque storage - open source doesn't know what's being stored
  - Do NOT store in a2a_context (security risk - accessible to tools)
  - Do NOT store in session state (security risk - accessible to tools)
  - Do NOT use private attributes (use generic security storage instead)

---

### File 3: `src/solace_agent_mesh/agent/protocol/event_handlers.py`

**Location:** Peer agent delegation logic (where peer requests are created)

#### Peer Agent Auth Token Propagation

- [ ] **Find peer request creation**
  - Locate where peer agent requests are constructed
  - Find where `user_properties` dict is built for peer requests

- [ ] **Retrieve original auth token using generic security storage**
  - Get from TaskExecutionContext: `auth_token = task_context.get_security_data("auth_token")`
  - **Note**: Generic security storage - open source doesn't know what's being retrieved
  - Check if token exists (may be None if no trust_manager)

- [ ] **Add auth token to peer request**
  - If token exists: `peer_user_properties["authToken"] = auth_token`
  - **Note**: Generic property name - no mention of JWT
  - Log at DEBUG: "Propagating authentication token to peer agent {peer_agent_name} for sub-task {sub_task_id}"

- [ ] **Verify no re-signing**
  - Confirm code does NOT call `sign_user_claims()` for peer requests
  - Agents cannot sign user authentication tokens (only gateways can)
  - Pass through original token unchanged

### File 4: `src/solace_agent_mesh/agent/sac/task_execution_context.py`

**Location:** `TaskExecutionContext` class

#### Add Generic Security Storage

- [ ] **Add security storage to __init__**
  - Add private attribute: `self._security_context: Dict[str, Any] = {}`
  - **Purpose**: Opaque storage for enterprise security data
  - **Note**: Open source doesn't know what's stored here
  - **Location**: After existing instance variable initialization

- [ ] **Add set_security_data method**
  - Method signature: `def set_security_data(self, key: str, value: Any) -> None:`
  - Docstring: "Store opaque security data (enterprise use only)."
  - Implementation: 
    ```python
    with self.lock:
        self._security_context[key] = value
    ```
  - **Thread safety**: Use existing `self.lock` to match class patterns

- [ ] **Add get_security_data method**
  - Method signature: `def get_security_data(self, key: str, default: Any = None) -> Any:`
  - Docstring: "Retrieve opaque security data (enterprise use only)."
  - Implementation:
    ```python
    with self.lock:
        return self._security_context.get(key, default)
    ```
  - **Thread safety**: Use existing `self.lock` to match class patterns

- [ ] **Add clear_security_data method**
  - Method signature: `def clear_security_data(self) -> None:`
  - Docstring: "Clear all security data."
  - Implementation:
    ```python
    with self.lock:
        self._security_context.clear()
    ```
  - **Thread safety**: Use existing `self.lock` to match class patterns
  - **Note**: Provided for completeness but not explicitly called

- [ ] **Verify automatic cleanup**
  - **No code changes needed**: Security context is automatically cleaned up when TaskExecutionContext is removed from `active_tasks` and garbage collected
  - **Verification**: Confirm that `finalize_task_with_cleanup()` removes context via `active_tasks.pop(logical_task_id, None)`
  - **Note**: Python's garbage collection handles cleanup of `_security_context` dict

---

## Existing Code Updates (Remove JWT-Specific References)

### File 5: `src/solace_agent_mesh/gateway/base/component.py`

**Location:** Existing code that may reference JWT

#### Remove Any Existing JWT References

- [ ] **Search for existing JWT code**
  - Search for: "JWT", "userIdentityJWT", "sign_user_identity"
  - Check if any code already exists from previous implementation attempts

- [ ] **Replace with generic equivalents**
  - Replace `userIdentityJWT` with `authToken`
  - Replace `sign_user_identity` with `sign_user_claims`
  - Replace JWT-specific log messages with generic equivalents

- [ ] **Update comments and docstrings**
  - Remove any mention of JWT in comments
  - Use generic security terminology

### File 6: `src/solace_agent_mesh/agent/protocol/event_handlers.py`

**Location:** Existing code that may reference JWT

#### Remove Any Existing JWT References

- [ ] **Search for existing JWT code**
  - Search for: "JWT", "userIdentityJWT", "verify_user_identity_jwt"
  - Check if any code already exists from previous implementation attempts

- [ ] **Replace with generic equivalents**
  - Replace `userIdentityJWT` with `authToken`
  - Replace `verify_user_identity_jwt` with `verify_user_claims`
  - Replace JWT-specific log messages with generic equivalents

- [ ] **Update comments and docstrings**
  - Remove any mention of JWT in comments
  - Use generic security terminology

---

## Testing Requirements

### Unit Tests (Open Source)

- [ ] **Gateway signing tests**
  - Mock `trust_manager.sign_user_claims()` to return fake auth token
  - Test successful signing path
  - Test signing failure (exception handling)
  - Test no trust_manager (graceful degradation)
  - Test auth token added to user_properties with generic name "authToken"
  - **Verify**: No mention of JWT in test code or assertions

- [ ] **Agent verification tests**
  - Mock `trust_manager.verify_user_claims()` to return fake claims
  - Test successful verification path
  - Test missing auth token (error response)
  - Test verification failure (error response)
  - Test no trust_manager (graceful degradation)
  - Test verified claims stored in a2a_context
  - Test error responses use generic messages ("Authentication failed")
  - **Verify**: No mention of JWT in test code or assertions

- [ ] **Peer propagation tests**
  - Test auth token passed to peer agent via generic security storage
  - Test no token if not present in original request
  - Test token not re-signed
  - Test generic property name "authToken" used
  - **Verify**: No mention of JWT in test code

- [ ] **TaskExecutionContext security storage tests**
  - Test `set_security_data()` stores data
  - Test `get_security_data()` retrieves data
  - Test `get_security_data()` returns default if key not found
  - Test `clear_security_data()` clears all data
  - Test security data isolated between tasks
  - Test thread safety of security storage methods
  - Test automatic cleanup when context is removed from active_tasks

### Integration Tests (Requires Enterprise)

- [ ] **End-to-end flow**
  - Gateway signs user claims (internally uses JWT)
  - Agent verifies user claims (internally verifies JWT)
  - Verified claims available in agent
  - Task processes successfully
  - **Verify**: Open source code uses only generic terminology

- [ ] **Multi-hop delegation**
  - Gateway → Agent A → Agent B
  - Auth token propagates through chain via generic security storage
  - Each agent verifies independently using `verify_user_claims()`
  - Original token preserved
  - **Verify**: No JWT-specific code in open source path

- [ ] **Error scenarios**
  - Missing auth token rejected with generic error
  - Invalid token rejected with generic error
  - Expired token rejected with generic error
  - Tampered token rejected with generic error
  - Unknown issuer rejected with generic error
  - Non-gateway issuer rejected with generic error
  - **Verify**: All error messages are generic ("Authentication failed")

- [ ] **Degradation scenarios**
  - No trust_manager: tasks process normally
  - Signing failure: gateway continues without JWT
  - Verification failure: agent rejects task

---

## Security Verification

### Code Review Checklist

- [ ] **Auth token never logged**
  - Confirm raw auth token never appears in log statements
  - Only log success/failure and user_id (after verification)
  - **Verify**: No "JWT" string in any open source log messages

- [ ] **Generic error messages**
  - All client-facing errors use "Authentication failed"
  - No cryptographic details in error messages
  - No mention of JWT, signature, or specific algorithms
  - Detailed errors only in server-side logs (enterprise)

- [ ] **Auth token storage security**
  - Raw token NOT in a2a_context (accessible to tools)
  - Raw token NOT in session state (accessible to tools)
  - Raw token only in TaskExecutionContext generic security storage
  - Verified claims (not raw token) in a2a_context
  - **Verify**: Uses `set_security_data()` / `get_security_data()` methods with thread safety
  - **Verify**: Security context automatically cleaned up when task completes

- [ ] **ACK vs NACK strategy**
  - Invalid tokens are ACKed (not NACKed)
  - Prevents infinite retry loops
  - Malformed tokens won't become valid on retry

- [ ] **No cryptographic validation in open source**
  - All validation in enterprise `verify_user_claims()` implementation
  - Open source only calls generic method and handles result
  - No expiration checks in open source
  - No signature checks in open source
  - No JWT-specific logic in open source

- [ ] **Generic terminology throughout**
  - Search open source for: "JWT", "json web token", "jwks"
  - Replace any found instances with generic equivalents
  - User property: `authToken` (not `userIdentityJWT`)
  - Methods: `sign_user_claims()`, `verify_user_claims()` (not JWT-specific names)
  - Logs: "authentication token", "user claims" (not "JWT")

- [ ] **Graceful degradation**
  - JWT failures never crash components
  - Gateway continues without JWT if signing fails
  - Agent rejects task if verification fails (when enabled)
  - No trust_manager: normal operation

---

## Documentation

### Code Documentation

- [ ] **Add docstring comments**
  - Explain why JWT operations are optional
  - Document new parameters
  - Document error conditions
  - Document security considerations

- [ ] **Add inline comments**
  - Explain trust_manager checks
  - Explain error handling strategy
  - Explain JWT storage decisions

### User Documentation

- [ ] **Configuration guide**
  - How to enable trust_manager
  - JWT TTL recommendations
  - Clock synchronization requirements

- [ ] **Security documentation**
  - What JWTs protect against
  - What JWTs don't protect against
  - Why verification is mandatory when enabled

- [ ] **Troubleshooting guide**
  - "Authentication failed" errors
  - Clock skew issues
  - Missing Trust Cards
  - JWT verification failures

---

## Deployment Checklist

### Pre-Deployment

- [ ] **All tests passing**
  - Unit tests (open source)
  - Integration tests (with enterprise)
  - Security tests

- [ ] **Code review completed**
  - Security review
  - Architecture review
  - Performance review

- [ ] **Documentation complete**
  - Code comments
  - User documentation
  - Troubleshooting guide

### Deployment Strategy

- [ ] **Phase 2A: Gateway Signing (Non-Breaking)**
  - Deploy gateway code with JWT signing
  - JWTs added to messages but not required
  - Monitor JWT creation and propagation
  - Verify no errors in signing

- [ ] **Phase 2B: Agent Verification (Opt-In)**
  - Deploy agent code with JWT verification
  - Verification optional (trust_manager disabled by default)
  - Enable in dev/test environments
  - Monitor verification success/failure rates

- [ ] **Phase 2C: Enforcement (Production)**
  - Enable trust_manager in production
  - JWT verification becomes mandatory
  - Monitor for authentication failures
  - Have rollback plan ready

### Post-Deployment

- [ ] **Monitor metrics**
  - JWT signing success rate
  - JWT verification success rate
  - Authentication failure rate
  - Task rejection rate

- [ ] **Monitor logs**
  - JWT signing errors
  - JWT verification errors
  - Clock skew warnings
  - Missing Trust Card warnings

- [ ] **Verify security**
  - No JWTs in logs
  - Generic error messages only
  - No information leakage

---

## Rollback Plan

### If Issues Detected

- [ ] **Immediate rollback**
  - Disable trust_manager in configuration
  - Restart affected components
  - Verify normal operation resumes

- [ ] **Investigation**
  - Collect logs from affected components
  - Identify root cause
  - Determine fix or configuration change

- [ ] **Re-deployment**
  - Apply fix
  - Test in dev/test environment
  - Gradual rollout to production

---

## Success Criteria

### Functional Requirements

- [x] Gateway can sign user identity JWTs
- [x] Agent can verify user identity JWTs
- [x] JWTs propagate through peer delegation
- [x] Invalid JWTs are rejected
- [x] System works without trust_manager (graceful degradation)

### Security Requirements

- [x] Only gateways can sign user identity JWTs
- [x] Agents verify JWT signature and expiration
- [x] JWTs bound to specific tasks
- [x] No JWT information leakage in errors
- [x] No bearer token exposure to tools

### Performance Requirements

- [x] JWT signing adds < 10ms to task submission
- [x] JWT verification adds < 10ms to task processing
- [x] No impact on throughput
- [x] No impact on latency (beyond verification time)

### Operational Requirements

- [x] Clear error messages for troubleshooting
- [x] Comprehensive logging for security audit
- [x] Monitoring metrics available
- [x] Rollback plan tested

---

## Notes

### Key Decisions

1. **Use generic security abstraction in open source**
   - Open source uses generic terminology only
   - No mention of JWT, JWKS, or cryptographic details
   - Enterprise owns all implementation details
   - Provides defense-in-depth and future flexibility

2. **Store verified claims, not raw token in a2a_context**
   - Prevents bearer token exposure to tools
   - Claims are safe to log and serialize
   - Tools get user identity without security risk

3. **Store raw token in TaskExecutionContext generic security storage**
   - Only for peer delegation
   - Uses opaque `set_security_data()` / `get_security_data()` methods with thread safety
   - Not accessible to tools
   - Automatic cleanup via garbage collection when task completes
   - No explicit cleanup method needed (relies on Python GC)

4. **Use generic error messages for all authentication failures**
   - "Authentication failed" for all cases
   - No mention of JWT, signature, or cryptographic details
   - Prevents information leakage
   - Detailed errors only in server logs (enterprise)

5. **ACK invalid tokens, don't NACK**
   - Invalid tokens won't become valid on retry
   - Prevents infinite retry loops
   - Appropriate for security failures

6. **No permissive mode for authentication verification**
   - When trust_manager enabled, verification is mandatory
   - No "log warnings only" mode
   - Security is binary: on or off

7. **Generic user property names**
   - Use `authToken` (not `userIdentityJWT`)
   - Use `sign_user_claims()` (not `sign_user_identity()`)
   - Use `verify_user_claims()` (not `verify_user_identity_jwt()`)
   - Reduces attack surface knowledge

### Open Questions Resolved

- **Q: Store auth token in a2a_context?** A: No, store verified claims only
- **Q: Store auth token in TaskExecutionContext?** A: Yes, in generic security storage for delegation
- **Q: Auth token in status updates?** A: No, only in task requests
- **Q: Validate token format in open source?** A: No, all validation in enterprise
- **Q: Permissive verification mode?** A: No, mandatory when enabled
- **Q: Use JWT-specific terminology in open source?** A: No, use generic security abstraction
- **Q: Expose implementation details?** A: No, enterprise owns all cryptographic details

---

## Enterprise Repository Interface

### Required Public Methods (Generic Interface)

The enterprise `TrustManager` must provide these generic methods for open source integration:

- [ ] **`sign_user_claims(user_info: Dict, task_id: str) -> str`**
  - Public interface for signing user claims
  - Returns opaque authentication token string
  - Internal implementation uses JWT (not exposed to open source)

- [ ] **`verify_user_claims(auth_token: str, task_id: str) -> Dict`**
  - Public interface for verifying user claims
  - Takes opaque authentication token string
  - Returns verified claims dictionary
  - Internal implementation verifies JWT (not exposed to open source)

### Internal Implementation (Enterprise Only)

These methods remain internal to enterprise repository:

- [ ] **`sign_user_identity(user_info: Dict, task_id: str) -> str`**
  - Internal JWT signing implementation
  - Called by `sign_user_claims()` public interface

- [ ] **`verify_user_identity_jwt(jwt_token: str, task_id: str) -> Dict`**
  - Internal JWT verification implementation
  - Called by `verify_user_claims()` public interface

### Enterprise Documentation

- [ ] **Document generic interface**
  - Explain that open source uses generic methods
  - Document that JWT is an implementation detail
  - Explain security benefits of abstraction

- [ ] **Document JWT implementation**
  - JWT signing and verification details in enterprise docs only
  - Cryptographic algorithms and key management
  - Security properties and guarantees

---

## Completion

- [ ] All checklist items completed
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Security review approved
- [ ] Deployed to production
- [ ] Monitoring confirmed working
- [ ] Success criteria met

**Implementation Status:** In Progress

**Last Updated:** 2025-01-16
