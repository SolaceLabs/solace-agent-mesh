# A2A Proxy Feature Description

## 1. Background & Context

### 1.1 The Solace Agent Mesh Ecosystem

The Solace Agent Mesh (SAM) is a platform for orchestrating AI agents, using the Solace PubSub+ event mesh as the communication backbone. Native SAM agents are built using the SAM framework and communicate via Solace topics, benefiting from built-in capabilities like:

- Automatic discovery through agent cards
- Centralized artifact management
- Session and memory services
- Integrated security and observability

These agents form a cohesive ecosystem where they can discover each other, collaborate on complex tasks, and share data seamlessly.

### 1.2 The Integration Challenge

Modern enterprises face a growing challenge: organizations are building AI agents on diverse platforms and frameworks, often independently across different teams and departments. Each division may develop specialized agents using their preferred tools and hosting them on separate infrastructure. This creates several problems:

- **Fragmentation**: Agents built on different frameworks cannot easily communicate or collaborate
- **Lack of Governance**: No unified security, authentication, or authorization layer across heterogeneous agents
- **Operational Complexity**: Each team must solve the same problems (discovery, security, data exchange) independently
- **Limited Collaboration**: Agents in one division cannot easily invoke or leverage agents in another division

What's needed is a way to provide federated access to these independently-developed agents while maintaining centralized control over security, discovery, and data management.

### 1.3 The A2A Protocol Standard

The Agent-to-Agent (A2A) protocol is an emerging open standard for agent interoperability. It defines:

- Standard message formats and interaction patterns
- A discovery mechanism via `AgentCard` documents
- Support for streaming, artifacts, and long-running tasks
- Integration with standard authentication schemes (OAuth 2.0, bearer tokens, API keys)

As A2A gains adoption, more agents are being built to expose A2A-compliant HTTP endpoints. However, these external agents cannot natively participate in the Solace mesh—they don't understand Solace topics, they don't integrate with SAM's artifact service, and they're not part of the mesh's security model.

### 1.4 The Gap This Feature Fills

The A2A Proxy bridges the gap between the Solace Agent Mesh and external A2A-compliant agents. It acts as a protocol translator and security gateway, enabling external agents to:

- Appear as native mesh participants for discovery purposes
- Receive requests from mesh agents via Solace topics
- Exchange artifacts using SAM's artifact management system
- Be secured through centralized authentication and authorization policies

Without the proxy, each external agent would require custom integration code, and there would be no centralized point for security enforcement or data management.

---

## 2. Goals & Objectives

### 2.1 Primary Goals

1. **Enable Seamless Integration**: Allow external A2A-over-HTTPS agents to participate in the Solace Agent Mesh without requiring modifications to the external agents themselves.

2. **Centralized Security**: Provide a single point for authentication, authorization, and credential management for all external agent interactions.

3. **Maintain Protocol Fidelity**: Preserve A2A protocol semantics end-to-end (A2A in → A2A out), ensuring external agents remain fully compliant and mesh agents interact with them identically to native agents.

### 2.2 Secondary Goals

1. **Minimize Operational Overhead**: Make it simple to add new external agents through declarative configuration (YAML).

2. **Support Full A2A Feature Set**: Handle all A2A interaction patterns including request/response, streaming, task cancellation, and artifact exchange.

3. **Enable Observability**: Provide comprehensive logging and integration with SAM's monitoring infrastructure to facilitate debugging and performance analysis. Remote agents are visible in agent views and requests/responses are shown in workflow diagrams.

### 2.3 Non-Goals

1. **General-Purpose API Gateway**: The proxy is specifically designed for A2A protocol translation, not as a generic HTTP proxy or API gateway.

2. **Visibilty of remote agent LLM and tool calling**: The proxy does not provide a way for users to see or manage the LLMs or tools used by remote agents. Remote agents are treated as black boxes.

3. **Non-A2A Protocol Support**: This initial implementation focuses exclusively on A2A-over-HTTPS agents. Support for other protocols is not in scope.

### 2.4 Extensibility Consideration

While this feature focuses on A2A-over-HTTPS agents, the architecture and implementation should be designed to facilitate future proxy types (e.g., gRPC-based agents, other agent protocols) without requiring a complete rewrite of the proxy infrastructure. The design should separate protocol-agnostic concerns (discovery, routing, artifact handling) from protocol-specific translation logic.

---

## 3. Use Cases & User Stories

### 3.1 Primary Use Cases

#### UC1: Integrating Third-Party SaaS A2A Agents

**Actor**: Platform Administrator 

**Scenario**: A company uses a SaaS platform (e.g., Salesforce, ServiceNow, Zendesk, or a specialized industry solution) that has recently added A2A agent capabilities to their service. The SaaS vendor has exposed an A2A-compliant agent endpoint (e.g., `https://api.vendor.com/a2a`) that provides domain-specific functionality such as:
- CRM data analysis and customer insights
- Automated ticket routing and resolution
- Industry-specific compliance checking
- Specialized data processing workflows

The administrator wants to make this SaaS vendor's agent available to their SAM-native agents without requiring the vendor to understand Solace concepts or modify their A2A implementation. This enables the organization to leverage their existing SaaS investments as part of their AI agent ecosystem.

**Steps**:
1. Administrator obtains the SaaS vendor's A2A endpoint URL and OAuth 2.0 credentials (typically provided in the vendor's admin console or API documentation)
2. Administrator adds the external agent's URL and authentication credentials to the proxy's configuration file
3. Proxy fetches the agent's `AgentCard` from the vendor's endpoint and publishes it to the mesh discovery topic
4. Mesh-native agents discover the SaaS agent and can invoke it like any other agent
5. The proxy handles all protocol translation, authentication, and artifact resolution transparently

**Outcome**: The SaaS vendor's agent appears as a native mesh participant, with full discovery, security, and artifact support. The vendor requires no changes to their A2A implementation, and the organization can now build workflows that combine their internal agents with the vendor's specialized capabilities. For example, a SAM agent could automatically create and route support tickets in ServiceNow, analyze CRM data in Salesforce, or perform industry-specific compliance checks using the vendor's domain expertise.

#### UC2: Federated Agent Access Across Organizational Boundaries

**Actor**: Enterprise Architect / Security Administrator (Morgan)

**Scenario**: A large enterprise has multiple divisions (e.g., Finance, HR, Legal, Operations) that have independently developed their own AI agents using different frameworks (LangChain, CrewAI, custom implementations) and hosting them on separate infrastructure (different cloud providers, on-premises servers). The enterprise needs:

- **Unified Discovery**: A central catalog where all agents across divisions can discover each other's capabilities
- **Centralized Security**: OAuth 2.0-based authentication and authorization to control which agents can invoke which services, enforced at a single point
- **Governance & Compliance**: A single layer for auditing, logging, and policy enforcement across all agent interactions
- **Secure Cross-Division Communication**: The ability for agents in one division to securely invoke agents in another division without requiring direct network access, shared credentials, or custom integration code

**Steps**:
1. Each division deploys their agents with A2A-compliant endpoints
2. Security administrator configures the proxy with OAuth 2.0 credentials for each division's agents
3. Proxy publishes all agent cards to a shared mesh namespace
4. Agents from any division can discover and invoke agents from other divisions
5. All requests flow through the proxy, which enforces authentication and logs all interactions

**Outcome**: The proxy acts as a secure, centralized gateway that federates access to agents across organizational silos. It enforces enterprise-wide security policies while allowing teams to maintain autonomy over their agent implementations. Security administrators have a single point of control for access policies, credential rotation, and audit logging.

---

## 4. Functional Requirements

### FR1: Agent Discovery & Registration

**FR1.1**: The proxy MUST fetch the `AgentCard` from each configured external agent's `/.well-known/agent.json` endpoint at startup.

**FR1.2**: The proxy MUST publish a modified `AgentCard` to the Solace mesh discovery topic, rewriting the agent's `url` field to point to the proxy's Solace topic (e.g., `solace:namespace/agent/requests/AgentName`).

**FR1.3**: The proxy MUST support periodic re-fetching of `AgentCard`s (configurable interval) to detect capability changes in external agents.

**FR1.4**: The proxy MUST allow administrators to assign a mesh-local alias to each external agent. The name used on the mesh may differ from the agent's actual name as declared in its `AgentCard`.

**FR1.5**: The proxy MUST validate that each external agent's `AgentCard` is well-formed and compliant with the A2A specification before publishing it to the mesh.

### FR2: Request/Response Proxying

**FR2.1**: The proxy MUST accept A2A requests from the Solace mesh on the appropriate agent-specific topic (e.g., `namespace/agent/requests/AgentName`).

**FR2.2**: The proxy MUST forward these requests to the external agent's HTTP endpoint using the A2A-over-HTTPS protocol, preserving all message content, metadata, and protocol semantics.

**FR2.3**: The proxy MUST translate responses from the external agent back into Solace messages and publish them to the appropriate reply topics as specified in the original request's user properties.

**FR2.4**: The proxy MUST preserve the task ID and context ID from the original request throughout the proxying lifecycle, ensuring end-to-end traceability.

**FR2.5**: The proxy MUST handle both synchronous (request/response) and asynchronous (long-running task) interaction patterns as defined by the A2A protocol.

### FR3: Streaming Support

**FR3.1**: The proxy MUST support A2A streaming requests (`message/stream` method).

**FR3.2**: The proxy MUST forward intermediate status updates (`TaskStatusUpdateEvent`) from the external agent to the mesh in real-time, publishing them to the status topic specified in the original request.

**FR3.3**: The proxy MUST support task cancellation requests (`tasks/cancel` method) and propagate them to the external agent.

**FR3.4**: The proxy MUST handle streaming responses from external agents that may include multiple events (status updates, artifact updates, final task completion).

### FR4: Artifact Resolution

**FR4.1 - Inbound Resolution**: When a mesh agent sends a message containing an `artifact://` URI to a proxied agent, the proxy MUST:
- Resolve the URI to raw bytes using SAM's artifact service
- Replace the URI with the raw bytes (or a base64-encoded representation, depending on the part type)
- Forward the modified message to the external agent

**FR4.2 - Outbound Resolution**: When an external agent returns a response containing raw artifact bytes (e.g., in a `FilePart` with inline bytes), the proxy MUST:
- Save the artifact to SAM's artifact service
- Generate an `artifact://` URI for the saved artifact
- Rewrite the response to replace the bytes with the URI
- Forward the modified response to the mesh

**FR4.3**: The proxy MUST support all artifact types defined by the A2A protocol, including text files, binary files, and structured data.

**FR4.4**: The proxy MUST preserve artifact metadata (MIME type, filename, description) during resolution and storage.

**FR4.5**: The proxy MUST handle artifacts in both `Message` objects and `Artifact` objects within `Task` responses.

### FR5: Authentication & Authorization

**FR5.1**: The proxy MUST support multiple authentication schemes for communicating with external agents, including:
- Static bearer tokens
- Static API keys
- OAuth 2.0 Client Credentials flow

**FR5.2**: The proxy MUST allow per-agent authentication configuration, enabling different agents to use different authentication methods.

**FR5.3**: For OAuth 2.0 Client Credentials flow, the proxy MUST:
- Automatically acquire access tokens from the configured token endpoint
- Cache tokens in memory with configurable expiration (default: 55 minutes)
- Automatically refresh tokens when they expire or when a 401 Unauthorized response is received
- Retry failed requests once after refreshing the token

**FR5.4**: The proxy MUST NOT log or expose sensitive credentials in any form, including:
- OAuth 2.0 client secrets
- Access tokens
- Static bearer tokens or API keys

**FR5.5**: The proxy MUST enforce HTTPS for all OAuth 2.0 token endpoints. HTTP token endpoints MUST be rejected with a clear error message.

**FR5.6**: The proxy MUST validate authentication configuration at startup and fail fast if required parameters are missing or invalid.

### FR6: Error Handling & Resilience

**FR6.1**: The proxy MUST translate HTTP errors from external agents (e.g., 404, 500, 503) into appropriate A2A JSON-RPC error responses.

**FR6.2**: The proxy MUST implement automatic retry logic for transient authentication failures:
- On receiving a 401 Unauthorized response from an OAuth 2.0-authenticated agent, invalidate the cached token and retry once with a fresh token
- Do not retry for static token authentication (401 indicates invalid credentials)

**FR6.3**: The proxy MUST provide meaningful error messages to mesh agents when external agents are unreachable, misconfigured, or return errors. Error messages should include:
- The agent name
- The task ID
- A description of the failure
- Sufficient context for debugging (without exposing sensitive information)

**FR6.4**: The proxy MUST handle network timeouts gracefully:
- Support configurable per-agent timeout values
- Provide a default timeout (e.g., 300 seconds)
- Return a timeout error to the mesh if the external agent does not respond within the configured time

**FR6.5**: The proxy MUST continue to function for healthy agents even if one or more agents are unreachable or failing.

### FR7: Configuration & Management

**FR7.1**: The proxy MUST be configurable via YAML files, consistent with SAM's configuration model.

**FR7.2**: The proxy MUST support environment variable substitution for sensitive values (e.g., `${CLIENT_SECRET}`, `${API_KEY}`).

**FR7.3**: The proxy MUST validate its configuration at startup, including:
- Required fields are present
- URLs are well-formed and use HTTPS where required
- Authentication parameters are complete for the specified auth type
- Timeout values are positive integers

**FR7.4**: The proxy MUST fail fast on invalid configuration, providing clear error messages that identify the specific configuration problem.

**FR7.5**: The proxy configuration MUST support:
- A list of proxied agents, each with its own URL, authentication, and optional timeout
- A shared artifact service configuration
- A discovery interval for periodic agent card refresh
- A default request timeout that can be overridden per agent

---

## 5. Non-Functional Requirements

### NFR1: Performance

**NFR1.1**: The proxy MUST add minimal latency to request/response cycles. Target overhead: < 50ms for non-artifact requests (excluding network time to the external agent).

**NFR1.2**: OAuth 2.0 token caching MUST achieve a cache hit rate > 99% under normal operating conditions (assuming typical 60-minute token lifetimes and 55-minute cache duration).

**NFR1.3**: The proxy MUST support concurrent requests to multiple external agents without blocking. Requests to different agents should be processed in parallel.

**NFR1.4**: Artifact resolution (inbound and outbound) MUST not significantly degrade performance for small artifacts (< 1MB). Target: < 100ms overhead for artifact operations.

### NFR2: Scalability

**NFR2.1**: A single proxy instance MUST support at least 10 proxied agents without performance degradation.

**NFR2.2**: The proxy MUST handle at least 100 concurrent requests across all proxied agents.

**NFR2.3**: The proxy's resource footprint (memory, CPU) MUST scale linearly with the number of proxied agents and concurrent requests.

**NFR2.4**: The proxy MUST not impose artificial limits on message size, artifact size, or response length (beyond what is imposed by the underlying transport and the external agents themselves).

### NFR3: Reliability

**NFR3.1**: The proxy MUST NOT crash or become unresponsive due to a single misbehaving external agent (e.g., an agent that returns malformed responses, hangs, or sends excessive data).

**NFR3.2**: The proxy MUST continue to function for healthy agents even if one or more agents are unreachable, misconfigured, or returning errors.

**NFR3.3**: The proxy MUST recover gracefully from transient network failures, including:
- Temporary loss of connectivity to the Solace broker
- Temporary loss of connectivity to external agents
- Temporary failures of the artifact service

**NF R3.4**: The proxy MUST handle task cancellation gracefully, ensuring that cancelled tasks do not leave resources in an inconsistent state.

### NFR4: Security

**NFR4.1**: All communication with external agents MUST occur over HTTPS (TLS 1.2 or higher). The proxy MUST reject HTTP URLs for external agents.

**NFR4.2**: Credentials (OAuth 2.0 client secrets, static tokens, API keys) MUST be stored securely:
- Preferably in environment variables or secrets management systems (e.g., AWS Secrets Manager, HashiCorp Vault)
- Never hardcoded in configuration files committed to version control
- Never logged or exposed in error messages

**NFR4.3**: The proxy MUST NOT expose internal mesh topology, agent details, or user information to external agents beyond what is necessary for A2A protocol compliance.

**NFR4.4**: OAuth 2.0 token caching MUST be secure:
- Tokens stored in memory only (not persisted to disk)
- Tokens cleared on proxy shutdown
- No token sharing between proxy instances (if multiple instances are deployed in the future)

### NFR5: Observability

**NFR5.1**: The proxy MUST log all significant events at appropriate log levels:
- INFO: Agent discovery, successful request forwarding, token acquisition
- WARNING: Retries, deprecated configuration usage, non-fatal errors
- ERROR: Configuration errors, authentication failures, external agent errors
- DEBUG: Cache hits/misses, detailed request/response data (excluding sensitive information)

**NFR5.2**: The proxy MUST include correlation IDs (task IDs, request IDs) in all log messages to enable end-to-end request tracing across the mesh.

**NFR5.3**: The proxy MUST integrate with SAM's existing observability infrastructure, including:
- A2A message validation (in test environments)
- Standard log formats and log levels
- Compatibility with centralized logging systems

**NFR5.4**: The proxy MUST provide sufficient logging to diagnose common issues:
- Authentication failures (with details about the auth type and endpoint, but not credentials)
- Network connectivity problems
- Configuration errors
- External agent errors or timeouts

---

## 7. Constraints & Assumptions

### 7.1 Technical Constraints

**C1**: The proxy MUST operate within the Solace AI Connector (SAC) framework, adhering to its component model and lifecycle management.

**C2**: The proxy MUST use the official A2A Python SDK (`a2a-sdk`) for client-side communication with external agents.

**C3**: The proxy MUST support A2A protocol version 0.3.0 or higher.

**C4**: The proxy MUST use Python 3.10 or higher.

### 7.2 Operational Constraints

**C5**: The proxy is deployed as a single instance per mesh namespace in the initial implementation. Multi-instance support (for high availability or load balancing) is a future enhancement.

**C6**: The proxy requires network connectivity to:
- The Solace PubSub+ broker
- All configured external agents
- The artifact service (if not in-memory)
- OAuth 2.0 token endpoints (if using OAuth 2.0 authentication)

**C7**: The proxy must be restarted to pick up configuration changes (dynamic reconfiguration is a future enhancement).

### 7.3 Assumptions About External Agents

**A1**: External agents MUST expose a valid `AgentCard` at the `/.well-known/agent.json` endpoint (or a configured alternative path).

**A2**: External agents MUST implement the A2A-over-HTTPS protocol correctly, including:
- Accepting JSON-RPC 2.0 requests
- Returning valid JSON-RPC 2.0 responses
- Supporting the required A2A methods (`message/send`, `message/stream`, `tasks/cancel`)

**A3**: External agents MUST be reachable via HTTPS. HTTP endpoints are not supported for security reasons.

**A4**: External agents MUST support at least one of the authentication schemes the proxy offers (bearer token, API key, OAuth 2.0 Client Credentials).

**A5**: External agents MAY return artifacts as raw bytes in `FilePart` objects. The proxy will handle conversion to URIs.

**A6**: External agents do NOT need to understand Solace-specific concepts (topics, artifact URIs, etc.). The proxy handles all Solace-specific translation.

---

## 8. Future Considerations

### 8.1 Enhancements Not in Scope for V1

**Distributed Token Caching**: Support for Redis or other distributed caches to enable multi-instance proxy deployments with shared token state.

**Full OAuth 2.0 Flow Support**: 
- Authorization Code flow for user-delegated access
- Device Code flow for headless agents
- Refresh Token support for long-lived sessions
- PKCE (Proof Key for Code Exchange) for public clients

**Mutual TLS (mTLS)**: Client certificate authentication for external agents that require certificate-based security.

**Advanced Observability**:
- Prometheus metrics (request counts, latency histograms, error rates, cache hit rates)
- Distributed tracing with OpenTelemetry
- Health check endpoints for load balancers and monitoring systems

**Dynamic Agent Registration**: API or UI for adding/removing proxied agents without restarting the proxy.

**Policy-Based Authorization**: Integration with policy engines (e.g., Open Policy Agent) for fine-grained, dynamic authorization decisions.

**Rate Limiting**: Per-agent rate limiting to protect external agents from overload.

**Circuit Breaker Pattern**: Automatic detection and isolation of failing external agents to prevent cascading failures.

### 8.2 Extensibility for Future Protocols

The base proxy architecture (discovery, request routing, artifact handling, authentication) should be designed to be reusable for future proxy types:

**gRPC-based Agents**: A new `GrpcProxyComponent` that translates Solace messages to gRPC calls, while reusing the base proxy's discovery, artifact, and authentication logic.

**Custom Agent Protocols**: A plugin system for protocol-specific adapters, allowing third parties to add support for proprietary or emerging agent protocols.

**Legacy REST APIs**: A "REST-to-A2A" adapter that wraps non-A2A-compliant REST services, making them appear as A2A agents to the mesh.

**Message Queue Protocols**: Support for agents that communicate via AMQP, MQTT, or other message queue protocols.

### 8.3 Integration with Other SAM Features

**Agent Orchestration**: Future versions of SAM may include workflow engines or agent orchestrators (e.g., LangGraph, CrewAI orchestrators) that could leverage the proxy to include external agents in complex, multi-step workflows.

**Centralized Policy Enforcement**: Integration with a policy engine to enforce fine-grained authorization rules at the proxy level, such as:
- Which mesh agents can invoke which external agents
- Rate limits per agent or per user
- Data access policies (e.g., PII restrictions)

**Multi-Tenancy**: Support for multiple isolated namespaces within a single proxy instance, enabling SaaS deployments where different customers' agents are logically separated.

**Agent Marketplace**: Integration with an agent marketplace or catalog service, where external agents can be discovered, evaluated, and provisioned dynamically.

---

## 9. Glossary

**A2A (Agent-to-Agent Protocol)**: An open standard protocol for AI agent communication, defining message formats, discovery mechanisms, and interaction patterns. Supports both synchronous and asynchronous interactions, streaming, and artifact exchange.

**Agent Card**: A JSON document (typically served at `/.well-known/agent.json`) that describes an agent's identity, capabilities, skills, endpoint URL, and supported authentication schemes. Used for agent discovery.

**Artifact**: A file or data object (e.g., CSV, PDF, image, JSON document) produced or consumed by an agent during task execution.

**Artifact URI**: A Solace-specific URI scheme (`artifact://app_name/user_id/session_id/filename?version=N`) used to reference artifacts stored in SAM's artifact service. Enables agents to share data without transferring large files in messages.

**Context ID**: An identifier that groups related tasks into a single conversation or session. Equivalent to a session ID in traditional applications.

**Federated Access**: The ability for agents across different organizational units, teams, or security domains to discover and invoke each other through a centralized gateway that enforces consistent security policies.

**JSON-RPC 2.0**: A lightweight remote procedure call protocol encoded in JSON. The A2A protocol uses JSON-RPC 2.0 as its message envelope format.

**OAuth 2.0 Client Credentials Flow**: An OAuth 2.0 grant type for service-to-service authentication where a client (the proxy) authenticates using a client ID and secret to obtain an access token. No user interaction is required.

**Proxied Agent**: An external A2A-compliant agent that is made accessible to the Solace mesh via the proxy. The agent is unaware it is being proxied.

**SAM (Solace Agent Mesh)**: The Solace-based platform for orchestrating and managing AI agents, providing services like discovery, artifact management, session management, and event-driven communication.

**Task**: In A2A, a stateful unit of work representing a single agent interaction. A task has a unique ID, a lifecycle (submitted → working → completed/failed), and can include multiple messages, artifacts, and status updates.

**Task ID**: A unique identifier for a task, used to correlate requests, responses, and status updates throughout the task's lifecycle.
