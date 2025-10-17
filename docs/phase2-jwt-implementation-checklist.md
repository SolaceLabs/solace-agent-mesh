# Phase 2 JWT Implementation Checklist

## Overview
This checklist tracks the implementation of JWT signing and verification for user identity in the SAM Trust Manager (Phase 2). All JWT logic resides in the enterprise repository. Open source changes are limited to integration hooks only.

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

#### Gateway JWT Signing Integration

- [ ] **Find insertion point**
  - Locate where `user_properties` dict is being built
  - After `authenticate_and_enrich_user()` call
  - Before `self.publish_a2a_message()` call

- [ ] **Add trust manager check**
  - Guard: `if hasattr(self, 'trust_manager') and self.trust_manager:`
  - Log at DEBUG: "Trust Manager not available, proceeding without JWT" (if no trust_manager)

- [ ] **Call JWT signing method**
  - Call: `trust_manager.sign_user_identity(user_info=user_identity, task_id=task_id)`
  - Wrap in try/except block
  - Catch generic Exception (enterprise exceptions may not be available)

- [ ] **Handle signing success**
  - Store JWT in variable: `jwt_token`
  - Add to user_properties: `user_properties["userIdentityJWT"] = jwt_token`
  - Log at DEBUG: "Successfully signed user identity JWT for task {task_id}"

- [ ] **Handle signing failure**
  - Log at ERROR: "Failed to sign user identity JWT for task {task_id}: {error}"
  - Continue without JWT (degraded mode, don't block task)
  - Do NOT raise exception

- [ ] **Add logging**
  - DEBUG: "Attempting to sign user identity JWT for task {task_id}"
  - DEBUG: "Added signed user identity JWT to task {task_id}" (on success)
  - Include task_id and user_id in log messages

---

### File 2: `src/solace_agent_mesh/agent/protocol/event_handlers.py`

**Location:** `handle_a2a_request()` function

#### Agent JWT Verification Integration

- [ ] **Find insertion point**
  - After A2ARequest is parsed and validated
  - After task_id is extracted
  - Before TaskExecutionContext is created
  - Before any ADK runner invocation

- [ ] **Add trust manager check**
  - Guard: `if hasattr(component, 'trust_manager') and component.trust_manager:`
  - Log at DEBUG: "Trust Manager not available, skipping JWT verification" (if no trust_manager)

- [ ] **Extract JWT from message**
  - Get: `jwt_token = message.get_user_properties().get("userIdentityJWT")`
  - Log at DEBUG: "Extracting JWT from user properties for task {task_id}"

- [ ] **Handle missing JWT**
  - Check: `if jwt_token is None:`
  - Log at WARNING: "Trust Manager enabled but no JWT provided for task {task_id}"
  - Create error response: `create_invalid_request_error_response()`
  - Error message: "Authentication failed" (generic)
  - Error data: `{"reason": "authentication_failed", "task_id": task_id}`
  - Publish error response to reply topic
  - Call `message.call_acknowledgements()` (ACK, don't retry)
  - Return early (do not process task)

- [ ] **Call JWT verification method**
  - Call: `component.trust_manager.verify_user_identity_jwt(jwt_token=jwt_token, expected_task_id=task_id)`
  - Wrap in try/except block
  - Catch generic Exception (enterprise exceptions may not be available)

- [ ] **Handle verification success**
  - Store verified claims: `verified_claims = <result>`
  - Extract user identity from claims (sub, name, email, roles, scopes)
  - Store in a2a_context: `a2a_context["verified_user_identity"] = {...}` (claims only, NOT raw JWT)
  - Log at INFO: "Successfully verified JWT for user '{sub}' (task: {task_id})"

- [ ] **Handle verification failure**
  - Log at WARNING: "JWT verification failed for task {task_id}: {error}" (server-side detail)
  - Create error response: `create_invalid_request_error_response()`
  - Error message: "Authentication failed" (generic, no details)
  - Error data: `{"reason": "authentication_failed", "task_id": task_id}`
  - Publish error response to reply topic
  - Call `message.call_acknowledgements()` (ACK, don't retry invalid JWTs)
  - Return early (do not process task)

- [ ] **Store JWT for peer delegation**
  - After successful verification
  - Store in TaskExecutionContext private attribute: `task_context._original_jwt_for_delegation = jwt_token`
  - Do NOT store in a2a_context (security risk)
  - Do NOT store in session state (security risk)

---

### File 3: `src/solace_agent_mesh/agent/protocol/event_handlers.py`

**Location:** Peer agent delegation logic (where peer requests are created)

#### Peer Agent JWT Propagation

- [ ] **Find peer request creation**
  - Locate where peer agent requests are constructed
  - Find where `user_properties` dict is built for peer requests

- [ ] **Retrieve original JWT**
  - Get from TaskExecutionContext: `original_jwt = task_context._original_jwt_for_delegation`
  - Check if JWT exists (may be None if no trust_manager)

- [ ] **Add JWT to peer request**
  - If JWT exists: `peer_user_properties["userIdentityJWT"] = original_jwt`
  - Log at DEBUG: "Propagating user identity JWT to peer agent {peer_agent_name} for sub-task {sub_task_id}"

- [ ] **Verify no re-signing**
  - Confirm code does NOT call `sign_user_identity()` for peer requests
  - Agents cannot sign user identity JWTs (only gateways can)
  - Pass through original JWT unchanged

---

## Testing Requirements

### Unit Tests (Open Source)

- [ ] **Gateway signing tests**
  - Mock `trust_manager.sign_user_identity()` to return fake JWT
  - Test successful signing path
  - Test signing failure (exception handling)
  - Test no trust_manager (graceful degradation)
  - Test JWT added to user_properties

- [ ] **Agent verification tests**
  - Mock `trust_manager.verify_user_identity_jwt()` to return fake claims
  - Test successful verification path
  - Test missing JWT (error response)
  - Test verification failure (error response)
  - Test no trust_manager (graceful degradation)
  - Test verified claims stored in a2a_context
  - Test error responses use generic messages

- [ ] **Peer propagation tests**
  - Test JWT passed to peer agent
  - Test no JWT if not present in original request
  - Test JWT not re-signed

### Integration Tests (Requires Enterprise)

- [ ] **End-to-end flow**
  - Gateway signs JWT
  - Agent verifies JWT
  - Verified claims available in agent
  - Task processes successfully

- [ ] **Multi-hop delegation**
  - Gateway → Agent A → Agent B
  - JWT propagates through chain
  - Each agent verifies independently
  - Original JWT preserved

- [ ] **Error scenarios**
  - Missing JWT rejected
  - Invalid JWT rejected
  - Expired JWT rejected
  - Tampered JWT rejected
  - Unknown issuer rejected
  - Non-gateway issuer rejected

- [ ] **Degradation scenarios**
  - No trust_manager: tasks process normally
  - Signing failure: gateway continues without JWT
  - Verification failure: agent rejects task

---

## Security Verification

### Code Review Checklist

- [ ] **JWT never logged**
  - Confirm raw JWT token never appears in log statements
  - Only log success/failure and user_id (after verification)

- [ ] **Generic error messages**
  - All client-facing JWT errors use "Authentication failed"
  - No cryptographic details in error messages
  - Detailed errors only in server-side logs

- [ ] **JWT storage security**
  - Raw JWT NOT in a2a_context (accessible to tools)
  - Raw JWT NOT in session state (accessible to tools)
  - Raw JWT only in TaskExecutionContext private attribute
  - Verified claims (not JWT) in a2a_context

- [ ] **ACK vs NACK strategy**
  - Invalid JWTs are ACKed (not NACKed)
  - Prevents infinite retry loops
  - Malformed JWTs won't become valid on retry

- [ ] **No JWT validation in open source**
  - All validation in enterprise `verify_user_identity_jwt()`
  - Open source only calls method and handles result
  - No expiration checks in open source
  - No signature checks in open source

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

1. **Store verified claims, not raw JWT in a2a_context**
   - Prevents bearer token exposure to tools
   - Claims are safe to log and serialize
   - Tools get user identity without security risk

2. **Store raw JWT in TaskExecutionContext private attribute**
   - Only for peer delegation
   - Not accessible to tools
   - Automatic cleanup with task

3. **Use generic error messages for all JWT failures**
   - "Authentication failed" for all cases
   - Prevents information leakage
   - Detailed errors only in server logs

4. **ACK invalid JWTs, don't NACK**
   - Invalid JWTs won't become valid on retry
   - Prevents infinite retry loops
   - Appropriate for security failures

5. **No permissive mode for JWT verification**
   - When trust_manager enabled, verification is mandatory
   - No "log warnings only" mode
   - Security is binary: on or off

### Open Questions Resolved

- **Q: Store JWT in a2a_context?** A: No, store verified claims only
- **Q: Store JWT in TaskExecutionContext?** A: Yes, in private attribute for delegation
- **Q: JWT in status updates?** A: No, only in task requests
- **Q: Validate JWT format in open source?** A: No, all validation in enterprise
- **Q: Permissive verification mode?** A: No, mandatory when enabled

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
