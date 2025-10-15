# SAM Trust Service Proposal

## 1. Overview and Purpose

As SAM integrates with enterprise OAuth systems for user authentication (see DATAGO-101537), we need a mechanism to ensure that user identity claims remain trustworthy as they flow through the distributed agent system. When a user authenticates at a gateway and their identity (including userId, name, roles, and scopes) is passed to agents and sub-agents, we must guarantee that:

- The identity claims originated from a legitimate SAM gateway that performed proper authentication
- The claims have not been tampered with during transit
- The claims are still valid (not expired or replayed)

Without this capability, a malicious actor could forge user identity claims, impersonate users, or replay captured authentication data to gain unauthorized access to agent capabilities.

**Primary Use Case**: A gateway authenticates a user via OAuth, extracts their claims (userId, name, roles, scopes), signs these claims cryptographically, and includes the signature with every A2A message in the task flow. Agents verify the signature before processing requests, ensuring they're acting on behalf of a legitimately authenticated user.

## 2. Trust Service Architecture

We are introducing a **Trust Service** to SAM that enables any component (gateway, agent, or future component type) to:

1. **Sign data** using its private key
2. **Verify signatures** from other components using their public keys
3. **Publish trust credentials** so other components can validate its signatures
4. **Discover and validate** other components' trust credentials

The Trust Service is a general-purpose security infrastructure that can be used for multiple purposes:
- **Now**: Signing user identity claims at gateways
- **Future**: Agents signing analysis results, components attesting to data provenance, etc.

Every SAM component that enables the Trust Service will:
- Generate or load an ECDSA (ES256) key pair on startup
- Publish a "Trust Card" containing its public key
- Subscribe to other components' Trust Cards
- Use the service to sign outgoing data and verify incoming signatures

The Trust Service is **optional and configurable** - it can be disabled for development environments or enabled for production security requirements.

## 3. Trust Card Distribution and Key Management

### Trust Card Publication

Each component periodically publishes a **Trust Card** to a well-known topic:
```
{namespace}/a2a/v1/trust/{client-username}
```

The Trust Card contains:
- Component identity (type, ID, namespace)
- Public key (PEM format)
- Key ID (for supporting multiple keys)
- Issuance and expiration timestamps
- Self-signature (signed with the component's private key)

**Example Trust Card**:
```json
{
  "component_type": "gateway",
  "component_id": "web-gateway-01",
  "namespace": "myorg/production",
  "public_key": "-----BEGIN PUBLIC KEY-----...",
  "key_algorithm": "ES256",
  "key_id": "web-gateway-01-key-1",
  "issued_at": 1234567890,
  "expires_at": 1237159890,
  "signature": "base64-encoded-self-signature"
}
```

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
3. Verify the card's self-signature using the embedded public key
4. Check the card hasn't expired
5. Store the public key in a local Trust Registry for future signature verification

### Key Rotation Support

Following security best practices, the Trust Service supports key rotation:
- Components can publish Trust Cards with new keys before old keys expire
- Verifiers maintain up to 2 active keys per component (current + previous)
- Signatures can be verified against either key during the overlap period
- Old keys are automatically removed after expiration

This enables zero-downtime key rotation without breaking existing task flows.

## 4. User Identity Signing and Replay Protection

### Signing User Claims

When a gateway authenticates a user and creates an A2A task, it signs the user's identity claims:

**Signed Payload**:
```json
{
  "taskId": "task-123",
  "userId": "matt.mays@solace.com",
  "name": "Matt Mays",
  "roles": ["user", "admin"],
  "scopes": ["read:data", "write:reports"],
  "authenticatedAt": 1234567890,
  "expiresAt": 1234571490
}
```

**Signature Object**:
```json
{
  "signedBy": "web-gateway-01",
  "algorithm": "ES256",
  "keyId": "web-gateway-01-key-1",
  "signature": "base64-encoded-ecdsa-signature",
  "signedAt": 1234567890
}
```

Both objects are included in the Solace message **user properties** and propagate through the entire task chain (including sub-agent calls).

### Replay Attack Prevention

The signature includes multiple time-based protections:

1. **Task-Specific Binding**: The `taskId` is included in the signed payload, binding the signature to a specific task instance
2. **Expiration Time**: The `expiresAt` timestamp limits the signature's lifetime (configurable, typically 1 hour)
3. **Authentication Timestamp**: The `authenticatedAt` timestamp records when the user originally authenticated
4. **Signature Timestamp**: The `signedAt` timestamp records when the signature was created

Agents verify:
- Current time < `expiresAt` (signature hasn't expired)
- `taskId` in signature matches the task being processed
- Clock skew tolerance (configurable, typically ±5 minutes)

This prevents:
- **Replay attacks**: Expired signatures are rejected
- **Cross-task replay**: Signatures are bound to specific task IDs
- **Signature reuse**: Each task gets a fresh signature with a new expiration

### Verification Flow

When an agent receives a task:
1. Extract `userIdentity` and `userIdentitySignature` from user properties
2. Look up the gateway's public key from the Trust Registry (using `signedBy`)
3. Verify the signature using ECDSA (ES256)
4. Check that current time < `expiresAt`
5. Verify `taskId` matches the current task
6. If all checks pass, trust the user claims and process the task
7. If any check fails, reject the task with a security error

Sub-agents perform the same verification using the **same signature** from the original gateway - signatures are not re-signed, they propagate through the entire task chain.

---

## Summary

The Trust Service provides SAM with enterprise-grade security for user identity propagation:
- **Cryptographic proof** that user claims originated from a legitimate gateway
- **Tamper protection** through ECDSA signatures
- **Replay prevention** through expiration and task binding
- **Decentralized trust** through broker-enforced ACLs and public key distribution
- **Future extensibility** for signing any component-to-component data

This foundation enables SAM to meet enterprise security requirements while maintaining the flexibility and scalability of a distributed agent architecture.
