# SAM Trust Manager Proposal

## 1. Overview and Purpose

As SAM integrates with enterprise OAuth systems for user authentication (see DATAGO-101537), we need a mechanism to ensure that user identity claims remain trustworthy as they flow through the distributed agent system. When a user authenticates at a gateway and their identity (including userId, name, roles, and scopes) is passed to agents and sub-agents, we must guarantee that:

- The identity claims originated from a legitimate SAM gateway that performed proper authentication
- The claims have not been tampered with during transit
- The claims are still valid (not expired or replayed)

Without this capability, a malicious actor could forge user identity claims, impersonate users, or replay captured authentication data to gain unauthorized access to agent capabilities.

**Primary Use Case**: A gateway authenticates a user via OAuth, extracts their claims (userId, name, roles, scopes), signs these claims as a JWT (JSON Web Token), and includes the JWT with every A2A message in the task flow. Agents verify the JWT before processing requests, ensuring they're acting on behalf of a legitimately authenticated user.

## 2. Trust Manager Architecture

We are introducing a **Trust Manager** to SAM that enables any component (gateway, agent, or future component type) to:

1. **Sign data as JWTs** using its private key
2. **Verify JWTs** from other components using their public keys
3. **Publish trust credentials** (JWKS - JSON Web Key Sets) so other components can validate its signatures
4. **Discover and validate** other components' trust credentials

The Trust Manager is a general-purpose security infrastructure that can be used for multiple purposes:
- **Now**: Signing user identity claims at gateways as JWTs
- **Future**: Agents signing analysis results, components attesting to data provenance, etc.

Every SAM component that enables the Trust Manager will:
- Generate or load an ECDSA (ES256) key pair on startup
- Publish a "Trust Card" containing its JWKS (JSON Web Key Set)
- Subscribe to other components' Trust Cards
- Use the manager to sign outgoing data as JWTs and verify incoming JWTs

The Trust Manager is **optional and configurable** - it can be disabled for development environments or enabled for production security requirements.

**Technology Standards**: The Trust Manager uses industry-standard JWT (RFC 7519) for signed data and JWKS (RFC 7517) for public key distribution. This ensures compatibility with enterprise security tools and provides well-understood security properties backed by IETF RFCs.

## 3. Trust Card Distribution and Key Management

### Trust Card Publication

Each component periodically publishes a **Trust Card** to a well-known topic:
```
{namespace}/a2a/v1/trust/{client-username}
```

The Trust Card contains:
- Component identity (type, ID, namespace)
- JWKS (JSON Web Key Set) with public keys
- Issuance and expiration timestamps

**Example Trust Card**:
```json
{
  "component_type": "gateway",
  "component_id": "web-gateway-01",
  "namespace": "myorg/production",
  "jwks": {
    "keys": [
      {
        "kty": "EC",
        "crv": "P-256",
        "x": "base64url-encoded-x-coordinate",
        "y": "base64url-encoded-y-coordinate",
        "use": "sig",
        "kid": "web-gateway-01-key-1",
        "alg": "ES256"
      }
    ]
  },
  "issued_at": 1234567890,
  "expires_at": 1237159890
}
```

**JWKS Format**: The Trust Card uses JWKS (JSON Web Key Set) format as defined in RFC 7517. This provides:
- Native JSON representation (no PEM strings in JSON)
- Key metadata (algorithm, key ID, usage)
- Native support for multiple keys (key rotation)
- Standard format recognized by JWT libraries and security tools

### Security Through Broker ACLs

Trust Cards are protected against impersonation through **Solace broker ACL enforcement**:
- Each component has unique Solace credentials (client-username)
- Broker ACLs ensure a component can ONLY publish to topics containing its own client-username
- Example: Component "web-gateway-01" can only publish to `*/a2a/v1/trust/web-gateway-01`

This creates a **root of trust**: if the broker allows the publish, the client-username in the topic is authentic, therefore the public key in that Trust Card is authentic.

### Trust Card Verification

When a component receives a Trust Card:
1. Extract the client-username from the topic
2. Verify it matches the `component_id` in the card payload
3. Validate the JWKS format and extract public keys
4. Check the card hasn't expired
5. Store the JWKS in a local Trust Registry for future JWT verification

### Key Rotation Support

Following security best practices, the Trust Manager supports key rotation:
- Components can publish Trust Cards with multiple keys in the JWKS (current + next)
- JWKS natively supports multiple keys with unique `kid` (key ID) values
- JWTs include the `kid` in their header, indicating which key was used
- Verifiers can verify JWTs against any valid key in the component's JWKS
- Old keys are automatically removed from JWKS after expiration

This enables zero-downtime key rotation without breaking existing task flows. The JWKS format makes key rotation straightforward and follows industry best practices.

## 4. User Identity Signing and Replay Protection

### Signing User Claims with JWT

When a gateway authenticates a user and creates an A2A task, it signs the user's identity claims as a **JWT (JSON Web Token)** using standard OIDC (OpenID Connect) claims:

**JWT Header**:
```json
{
  "alg": "ES256",
  "typ": "JWT",
  "kid": "web-gateway-01-key-1"
}
```

**JWT Payload (Claims)**:
```json
{
  "iss": "web-gateway-01",
  "sub": "matt.mays@solace.com",
  "exp": 1234571490,
  "iat": 1234567890,
  "name": "Matt Mays",
  "email": "matt.mays@solace.com",
  "roles": ["user", "admin"],
  "scopes": ["read:data", "write:reports"],
  "task_id": "task-123"
}
```

**Standard OIDC Claims Used**:
- `iss` (issuer): Component ID that signed the JWT (e.g., "web-gateway-01")
- `sub` (subject): User identifier (email or user ID)
- `exp` (expiration): Expiration timestamp (Unix epoch seconds)
- `iat` (issued at): Issuance timestamp (Unix epoch seconds)
- `name`: User's full name
- `email`: User's email address

**Custom SAM Claims**:
- `task_id`: Binds JWT to specific SAM task
- `roles`: User's roles in the system
- `scopes`: OAuth scopes granted to the user

The complete JWT (header.payload.signature) is included in the Solace message **user properties** as a single string and propagates through the entire task chain (including sub-agent calls).

**Example User Properties**:
```json
{
  "userId": "matt.mays@solace.com",
  "taskId": "task-123",
  "clientId": "web-gateway-01",
  "userIdentityJWT": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IndlYi1nYXRld2F5LTAxLWtleS0xIn0.eyJpc3MiOiJ3ZWItZ2F0ZXdheS0wMSIsInN1YiI6Im1hdHQubWF5c0Bzb2xhY2UuY29tIiwiZXhwIjoxMjM0NTcxNDkwLCJpYXQiOjEyMzQ1Njc4OTAsIm5hbWUiOiJNYXR0IE1heXMiLCJlbWFpbCI6Im1hdHQubWF5c0Bzb2xhY2UuY29tIiwicm9sZXMiOlsidXNlciIsImFkbWluIl0sInNjb3BlcyI6WyJyZWFkOmRhdGEiLCJ3cml0ZTpyZXBvcnRzIl0sInRhc2tfaWQiOiJ0YXNrLTEyMyJ9.signature"
}
```

### Replay Attack Prevention

The JWT includes multiple time-based protections using standard JWT claims:

1. **Task-Specific Binding**: The `task_id` claim binds the JWT to a specific task instance
2. **Expiration Time**: The `exp` (expiration) claim limits the JWT's lifetime (configurable, typically 1 hour)
3. **Issuance Timestamp**: The `iat` (issued at) claim records when the JWT was created

Agents verify:
- Current time < `exp` (JWT hasn't expired) - standard JWT validation
- `task_id` claim matches the task being processed
- `iss` (issuer) claim identifies a trusted gateway component
- Clock skew tolerance (configurable, typically ±5 minutes) - standard JWT practice

This prevents:
- **Replay attacks**: Expired JWTs are rejected (standard JWT behavior)
- **Cross-task replay**: JWTs are bound to specific task IDs via `task_id` claim
- **Token reuse**: Each task gets a fresh JWT with a new expiration
- **Impersonation**: Only gateways can issue user identity JWTs (verified via `iss` claim and component type)

### Verification Flow

When an agent receives a task:
1. Extract `userIdentityJWT` from user properties
2. Parse JWT header to get `kid` (key ID) and `alg` (algorithm)
3. Extract `iss` (issuer) claim from JWT payload
4. Look up the issuer's JWKS from the Trust Registry
5. Find the matching public key using `kid`
6. Verify the issuer's `component_type` is "gateway" (authorization check)
7. Verify the JWT signature using the public key and ES256 algorithm
8. Validate standard JWT claims:
   - Current time < `exp` (not expired)
   - `iat` is reasonable (not too far in past/future)
9. Verify `task_id` claim matches the current task
10. If all checks pass, extract and trust the user claims (`sub`, `name`, `roles`, `scopes`)
11. If any check fails, reject the task with a security error

**Authorization Layer**: Agents only accept user identity JWTs from components with `component_type: "gateway"`. This prevents other agents from forging user identities even though they have valid signing keys.

Sub-agents perform the same verification using the **same JWT** from the original gateway - JWTs are not re-signed, they propagate through the entire task chain.

**JWT Library**: SAM will use standard Python JWT libraries (PyJWT or python-jose) for all JWT operations, ensuring compliance with RFC 7519 and leveraging well-tested cryptographic implementations.

---

## Summary

The Trust Manager provides SAM with enterprise-grade security for user identity propagation using industry-standard technologies:

**Security Properties**:
- **Cryptographic proof** that user claims originated from a legitimate gateway (JWT signatures)
- **Tamper protection** through ECDSA signatures (ES256 algorithm)
- **Replay prevention** through standard JWT expiration (`exp` claim) and task binding
- **Authorization control** through component type verification (only gateways can sign user identities)
- **Decentralized trust** through broker-enforced ACLs and JWKS distribution

**Standards Compliance**:
- **JWT (RFC 7519)** for signed user identity claims
- **JWKS (RFC 7517)** for public key distribution
- **OIDC standard claims** (`iss`, `sub`, `exp`, `iat`, `name`, `email`)
- **ES256 (ECDSA with P-256)** for signatures

**Benefits**:
- Well-understood security properties backed by IETF RFCs
- Compatible with enterprise security tools and auditing processes
- Extensive library support and tooling
- Clear security analysis and documentation for customer security reviews
- Future extensibility for signing any component-to-component data

This foundation enables SAM to meet enterprise security requirements while maintaining the flexibility and scalability of a distributed agent architecture.
