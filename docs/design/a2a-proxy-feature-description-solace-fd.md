# DATAGO-104472 - Agent-to-Agent Communication for Standalone Agents - FD

## Epic Link

[DATAGO-104472](https://sol-jira.atlassian.net/browse/DATAGO-104472) - Agent-to-Agent Communication for Standalone Agents

## Table of Contents

- [Epic Link](#epic-link)
- [Table of Contents](#table-of-contents)
- [Feature Objective](#feature-objective)
- [Key Customer Outcomes](#key-customer-outcomes)
- [Confluence Feature Description](#confluence-feature-description)
- [Customer Context](#customer-context)
  - [How will the business benefit from this feature?](#how-will-the-business-benefit-from-this-feature)
- [New/Updated Customer Journey](#newupdated-customer-journey)
  - [UI Flow](#ui-flow)
- [Feature Description and Scope](#feature-description-and-scope)
  - [Scope/Overview](#scopeoverview)
  - [Feature Description](#feature-description)
  - [Feature/Functional Requirements](#featurefunctional-requirements)
  - [External REST API Requirements](#external-rest-api-requirements)
  - [Platforms](#platforms)
  - [Packaging & Distribution](#packaging--distribution)
  - [User Roles & Responsibilities](#user-roles--responsibilities)
  - [Out of Scope](#out-of-scope)
- [Knowledge Acquisition/High-Level Architecture](#knowledge-acquisitionhigh-level-architecture)
  - [Product Knowledge Acquisition Questions/Considerations](#product-knowledge-acquisition-questionsconsiderations)
  - [Knowledge Acquisition Outcomes](#knowledge-acquisition-outcomes)
- [High-Level UI Mocks](#high-level-ui-mocks)
- [Story Map](#story-map)
- [Quality Plan](#quality-plan)
- [Performance and Scalability Considerations](#performance-and-scalability-considerations)
- [Security Considerations](#security-considerations)
- [Other Considerations](#other-considerations)
- [Observability](#observability)
- [Product Metrics](#product-metrics)
- [Customer Documentation](#customer-documentation)
- [Support Considerations](#support-considerations)
- [Rollout Considerations](#rollout-considerations)
- [Product Marketing Summary and Enablement](#product-marketing-summary-and-enablement)
- [Customer Training Impact](#customer-training-impact)
- [Package Pricing Consideration](#package-pricing-consideration)

## Feature Objective

Enable Solace Agent Mesh (SAM) to integrate external A2A-compliant agents into the mesh through a proxy component that provides protocol translation, centralized security, and artifact management. This capability allows enterprises to federate access to AI agents built on diverse platforms while maintaining centralized governance, security, and compliance.

## Key Customer Outcomes

**Federated Agent Access**: Organizations can integrate agents built by different teams, divisions, or third-party vendors into a unified mesh without requiring those agents to understand Solace-specific concepts or protocols.

**SaaS Ecosystem Integration**: Organizations can leverage A2A-enabled capabilities from their existing SaaS vendors (CRM, ERP, ticketing systems, industry-specific platforms) by adding them to the mesh through simple configuration, creating a unified AI agent ecosystem that spans both internal and external services.

**Centralized Security Governance**: A single point of control for authentication, authorization, and credential management across all external agent interactions, supporting OAuth 2.0 (Client Credentials flow), bearer tokens, and API keys.

**Standards-Based Integration**: Full compliance with the A2A protocol specification enables seamless integration with the broader A2A ecosystem while maintaining protocol fidelity (A2A in → A2A out).

**Extended Data Management**: SAM's artifact management capabilities are transparently extended to external agents through automatic artifact resolution, enabling seamless data exchange without requiring external agents to implement Solace-specific artifact handling.

**Operational Efficiency**: Declarative YAML configuration and automatic discovery minimize the operational overhead of adding new external agents to the mesh.


## Customer Context

Modern enterprises are rapidly adopting AI agents to automate workflows, enhance decision-making, and improve operational efficiency. However, these agents are being built across organizational silos using diverse frameworks and platforms—LangChain in one division, CrewAI in another, custom implementations by third-party vendors. This fragmentation creates a critical challenge: **how can organizations enable these independently-developed agents to discover, communicate with, and leverage each other's capabilities while maintaining enterprise-grade security and governance?**

Consider Morgan, a Middleware Integrations Specialist at a large financial services company. His organization has:
- A legal compliance agent built by the Legal department using a third-party SaaS service
- A financial forecasting agent developed by the Finance team using LangChain
- A customer sentiment analysis agent created by Marketing using a vendor's A2A-compliant API
- Internal SAM-native agents for document processing and workflow automation

Each of these agents is powerful in isolation, but Morgan's challenge is enabling them to work together. The Finance team wants their forecasting agent to consult the Legal agent for compliance checks. The Marketing agent needs to access documents processed by SAM-native agents. However, these agents cannot communicate because:

1. **Security Fragmentation**: Each agent has its own authentication mechanism. There's no centralized way to enforce who can invoke which agent, making audit trails incomplete and compliance verification difficult.

2. **Protocol Incompatibility**: External agents expose A2A-over-HTTPS endpoints, but they don't understand Solace topics, SAM's artifact URIs, or the mesh's discovery mechanisms.

3. **Operational Overhead**: Each integration requires custom code, manual credential management, and ongoing maintenance. Adding a new external agent means weeks of development work.

4. **Data Exchange Barriers**: External agents can't access artifacts stored in SAM's artifact service, and SAM agents can't easily consume data produced by external agents without custom adapters.

The fundamental problem is that **SAM lacks a standardized way to integrate external A2A-compliant agents into the mesh**. Without this capability, organizations cannot realize the full value of their AI investments, and teams remain siloed despite using compatible protocols.

### How will the business benefit from this feature?

This feature enables SAM to act as a **secure, centralized gateway** for external A2A agents, providing:

**Accelerated AI Adoption**: Organizations can integrate third-party AI services and agents built by different teams without requiring those vendors or teams to modify their implementations or understand Solace-specific concepts. This reduces time-to-value from weeks to hours.

**Enterprise Security & Compliance**: A single point of control for authentication (OAuth 2.0, bearer tokens, API keys), authorization, and audit logging across all external agent interactions. Security teams gain visibility and control without impeding developer productivity.

**Reduced Integration Costs**: Declarative YAML configuration replaces custom integration code. Adding a new external agent requires only configuration changes, not development effort.

**Ecosystem Interoperability**: Full A2A protocol compliance ensures SAM can integrate with the growing ecosystem of A2A-compliant agents from vendors, open-source projects, and internal teams using different frameworks.

**Data Management Extension**: SAM's artifact service becomes accessible to external agents through transparent artifact resolution, enabling seamless data exchange without requiring external agents to implement Solace-specific storage logic.

## New/Updated Customer Journey

### UI Flow

This feature is primarily a backend integration capability with minimal direct UI impact. The user experience is focused on configuration and monitoring.

**Administrator Configuration Flow:**

1. **Add External Agent**: Administrator edits the proxy's YAML configuration file to add a new external agent entry:
   ```yaml
   proxied_agents:
     - name: "LegalComplianceAgent"
       url: "https://legal-agent.vendor.com"
       authentication:
         type: "oauth2_client_credentials"
         token_url: "https://auth.vendor.com/oauth/token"
         client_id: "${LEGAL_AGENT_CLIENT_ID}"
         client_secret: "${LEGAL_AGENT_CLIENT_SECRET}"
   ```

2. **Deploy Configuration**: Administrator deploys the updated configuration. The proxy automatically:
   - Fetches the agent's `AgentCard` from `https://legal-agent.vendor.com/.well-known/agent.json`
   - Validates the OAuth 2.0 configuration
   - Publishes the agent's card to the mesh discovery topic
   - Begins accepting requests for the agent

**Developer/Agent Usage Flow:**

1. **Discovery**: A SAM-native agent (or gateway) discovers the external agent through the standard mesh discovery mechanism. The external agent appears identical to native agents.

2. **Invocation**: The SAM agent sends a request to the external agent using standard A2A message format on the Solace topic `namespace/agent/requests/LegalComplianceAgent`.

3. **Transparent Proxying**: The proxy:
   - Receives the request from the Solace mesh
   - Resolves any `artifact://` URIs to raw bytes
   - Authenticates with the external agent (using cached OAuth token if applicable)
   - Forwards the request via HTTPS
   - Receives the response from the external agent
   - Saves any returned artifacts to SAM's artifact service and generates URIs
   - Publishes the response back to the mesh

4. **Response Handling**: The requesting agent receives the response on its reply topic, with artifacts accessible via standard `artifact://` URIs.

**Monitoring Flow:**

1. **Log Review**: Administrators can review proxy logs to monitor:
   - Request/response activity for each external agent
   - Authentication successes/failures
   - Artifact resolution operations
   - Error conditions

2. **Troubleshooting**: When issues occur, logs provide correlation IDs (task IDs) to trace requests end-to-end across the mesh and through the proxy.

## Feature Description and Scope

### Scope/Overview

The A2A Proxy is a protocol translation and security gateway component that enables external A2A-over-HTTPS agents to participate in the Solace Agent Mesh. It provides:

- **Protocol Translation**: Bidirectional translation between Solace topics (mesh-native) and HTTPS (external agents)
- **Centralized Security**: Authentication and authorization enforcement for all external agent interactions
- **Artifact Management**: Transparent resolution of SAM artifact URIs to/from raw bytes
- **Discovery Integration**: Automatic fetching and publishing of external agent cards to the mesh
- **Standards Compliance**: Full adherence to the A2A protocol specification

### Feature Description

**Core Capability**: The proxy acts as a bridge between the Solace event mesh and external A2A-compliant agents, enabling seamless integration without requiring external agents to understand Solace-specific concepts.

**Architecture Overview**: The proxy is built around five core components that work together to provide seamless integration. The **Discovery Service** acts as the proxy's eyes into the external agent ecosystem, periodically fetching `AgentCard` documents from configured agents and publishing them to the mesh discovery topic. This makes external agents immediately discoverable to all mesh participants without any manual registration steps.

Working in tandem, the **Request Router** accepts A2A requests from the mesh on agent-specific topics and intelligently forwards them to the appropriate external agent's HTTPS endpoint. The **Authentication Manager** handles the complexity of multiple authentication schemes—from simple static bearer tokens to sophisticated OAuth 2.0 Client Credentials flows with automatic token caching and refresh. This abstraction means that mesh agents never need to know or care about how external agents authenticate; the proxy handles all credential management transparently.

The **Artifact Resolver** is perhaps the most sophisticated component, providing bidirectional artifact translation. When a mesh agent sends a message containing an `artifact://` URI to an external agent, the resolver fetches the raw bytes from SAM's artifact service and embeds them in the outbound request. Conversely, when an external agent returns raw artifact bytes in its response, the resolver saves them to SAM's artifact service, generates a proper `artifact://` URI, and rewrites the response before forwarding it to the mesh. This transparent resolution means external agents can work with raw data while mesh agents continue to use SAM's efficient URI-based artifact references.

Finally, the **Response Handler** ensures protocol fidelity by translating responses from external agents back into properly formatted Solace messages, publishing them to the appropriate reply and status topics as specified by the A2A protocol.

**Deployment Model**: The proxy is deployed as a Solace AI Connector (SAC) application, configured via YAML, and runs as a single instance per agent mesh namespace.

### Feature/Functional Requirements

**FR1: Federated Agent Discovery**

Discovery is the foundation of the mesh's ability to dynamically adapt to new capabilities. The proxy must enable external agents to participate in this discovery mechanism without requiring those agents to understand Solace topics or publish to the mesh directly. This creates a seamless experience where external agents appear as native mesh participants from the perspective of other agents.

- FR1.1: Fetch `AgentCard` documents from external agents at configurable intervals
- FR1.2: Publish modified agent cards to the mesh discovery topic with rewritten URLs pointing to the proxy
- FR1.3: Support agent aliasing (mesh name may differ from external agent's actual name)
- FR1.4: Validate agent cards for A2A specification compliance before publishing

**FR2: Transparent Request/Response Proxying**

The core function of the proxy is to act as a transparent bridge, forwarding requests between the mesh and external agents while preserving A2A protocol semantics and maintaining end-to-end traceability. From the perspective of a mesh agent, invoking an external agent should be indistinguishable from invoking a native mesh agent.

- FR2.1: Accept A2A requests from mesh agents on agent-specific Solace topics
- FR2.2: Forward requests to external agents via HTTPS with preserved message content and metadata
- FR2.3: Translate responses back to Solace messages and publish to appropriate reply topics
- FR2.4: Preserve task IDs and context IDs throughout the proxying lifecycle
- FR2.5: Support both synchronous (request/response) and asynchronous (long-running) interaction patterns

**FR3: Real-Time Streaming Support**

Many AI agent interactions are long-running and benefit from real-time progress updates. The proxy must support A2A streaming interactions to enable this progressive feedback, ensuring that mesh agents receive status updates as external agents process their requests rather than waiting for a final response.

- FR3.1: Support A2A streaming requests (`message/stream` method)
- FR3.2: Forward intermediate status updates from external agents to mesh in real-time
- FR3.3: Support task cancellation and propagate cancellation requests to external agents
- FR3.4: Handle multiple event types (status updates, artifact updates, final completion)

**FR4: Artifact Data Management**

One of the proxy's most powerful features is its ability to extend SAM's artifact management capabilities to external agents through transparent URI resolution. This allows external agents to work with raw data while mesh agents continue to benefit from SAM's efficient URI-based artifact references, eliminating the need to transfer large files in every message.

- FR4.1: Resolve inbound `artifact://` URIs to raw bytes using SAM's artifact service before forwarding to external agents
- FR4.2: Save outbound artifacts from external agents to SAM's artifact service and generate URIs for mesh consumption
- FR4.3: Support all artifact types (text, binary, structured data)
- FR4.4: Preserve artifact metadata (MIME type, filename, description) during resolution

**FR5: Multi-Scheme Authentication**

External agents may use different authentication mechanisms depending on their hosting environment and security requirements. The proxy must support industry-standard authentication mechanisms to integrate with this diverse landscape, handling all credential management transparently so that mesh agents never need to know about authentication details.

- FR5.1: Support static bearer token authentication
- FR5.2: Support static API key authentication
- FR5.3: Support OAuth 2.0 Client Credentials flow with automatic token acquisition, caching, and refresh
- FR5.4: Allow per-agent authentication configuration
- FR5.5: Enforce HTTPS for OAuth token endpoints
- FR5.6: Implement automatic retry logic for transient authentication failures (401 errors)

**FR6: Resilient Error Handling**

In a distributed system, failures are inevitable. The proxy must provide robust error handling to ensure system stability and meaningful error reporting, preventing a single misbehaving external agent from impacting the entire mesh.

- FR6.1: Translate HTTP errors from external agents to A2A JSON-RPC error responses
- FR6.2: Provide meaningful error messages including agent name, task ID, and failure context
- FR6.3: Handle network timeouts gracefully with configurable per-agent timeout values
- FR6.4: Continue functioning for healthy agents even when one or more agents are unreachable

**FR7: Declarative Configuration**

Operational simplicity is a key design goal. The proxy must be configurable through standard YAML files consistent with SAM's configuration model, making it easy for administrators to add new external agents without writing code.

- FR7.1: Support YAML-based configuration for all proxy settings
- FR7.2: Support environment variable substitution for sensitive values
- FR7.3: Validate configuration at startup and fail fast on invalid settings
- FR7.4: Support per-agent configuration overrides (timeouts, authentication)

### External REST API Requirements

Not Applicable - The proxy does not expose external REST APIs. It consumes A2A-over-HTTPS APIs from external agents and communicates with the mesh via Solace topics.

### Platforms

The proxy is compatible with:
- Python 3.10 or higher
- A2A-compliant agents supporting version 0.3.0+ written in any language/framework
- Solace PubSub+ broker (cloud, software, appliance)

### Packaging & Distribution

The proxy is delivered as part of the Solace Agent Mesh framework - community edition:
- Packaged as a SAM component, running on the Solace AI Connector (SAC) framework
- Configuration managed through YAML files in the normal SAM configs directory

### User Roles & Responsibilities

**Platform Administrator / DevOps Engineer**:
- Configure the proxy's YAML file with external agent URLs and authentication credentials
- Deploy and manage the proxy as a SAC application
- Monitor proxy logs and health
- Rotate credentials and update authentication configuration as needed
- Troubleshoot integration issues using proxy logs and correlation IDs

**Agent Developer**:
- Develop SAM-native agents that interact with external agents through standard A2A messaging
- Use standard mesh discovery mechanisms to find external agents
- Handle responses from external agents identically to native agents
- No special code required to interact with proxied agents

**Security Administrator**:
- Define authentication policies for external agents
- Manage OAuth 2.0 client credentials and secrets
- Review audit logs for compliance verification
- Enforce HTTPS requirements for external agent endpoints

### Out of Scope

**Non-A2A Protocol Support**: This implementation focuses exclusively on A2A-over-HTTPS agents. Support for other agent protocols (gRPC, custom REST APIs, message queue protocols) is not in scope for the initial release.

**Multi-Instance High Availability**: The initial implementation supports a single proxy instance per mesh namespace. Multi-instance deployment for high availability and load balancing is a future enhancement.

**Dynamic Agent Registration**: Adding or removing external agents requires configuration file changes and proxy restart. A dynamic registration API or UI is not in scope.

**Advanced OAuth Flows**: Only OAuth 2.0 Client Credentials flow is supported. Authorization Code flow, Device Code flow, and user-delegated access scenarios are future enhancements.

**Mutual TLS (mTLS)**: Client certificate authentication is not supported in the initial release.

**Policy-Based Authorization**: Fine-grained, dynamic authorization policies (e.g., via Open Policy Agent) are not in scope. Authorization is handled by the external agents themselves.

**Rate Limiting**: Per-agent rate limiting to protect external agents from overload is a future enhancement.

**Circuit Breaker Pattern**: Automatic detection and isolation of failing external agents is a future enhancement.

**Distributed Token Caching**: OAuth tokens are cached in-memory per proxy instance. Distributed caching (e.g., Redis) for multi-instance deployments is a future enhancement.

**Real-Time Configuration Updates**: Configuration changes require proxy restart. Hot-reloading of configuration is not supported.

**Agent-Specific Protocol Customization**: The proxy implements standard A2A protocol translation. Custom protocol adaptations for specific external agents are not supported.

## Knowledge Acquisition/High-Level Architecture

### Product Knowledge Acquisition Questions/Considerations

**Integration Architecture**:
- What is the optimal deployment model for the proxy (single instance, multi-instance, sidecar)?
- How do we ensure protocol fidelity (A2A in → A2A out) while handling mesh-specific concerns like artifact URIs?

**Security & Authentication**:
- How do we support multiple authentication schemes (static tokens, OAuth 2.0) in a unified, configurable way?
- How do we securely manage and cache OAuth 2.0 tokens to minimize token acquisition overhead?
- How do we enforce HTTPS requirements and prevent credential leakage in logs?

**Artifact Management**:
- How do we transparently resolve artifact URIs for external agents that don't have access to SAM's artifact service?
- How do we handle artifacts returned by external agents and make them accessible to mesh agents?
- What is the appropriate scoping strategy for artifacts (namespace vs. app)?

**Operational Concerns**:
- How do we provide sufficient observability (logging, tracing) for troubleshooting integration issues?
- How do we handle failures gracefully (network errors, authentication failures, external agent errors)?
- How do we ensure the proxy doesn't become a single point of failure for the mesh?

### Knowledge Acquisition Outcomes

The design and architecture of the A2A proxy is documented across several specialized documents, each addressing a critical aspect of the implementation. These documents provide the technical depth necessary for implementation while this feature description maintains focus on business requirements and customer value.

**Reference Documents**:
- [A2A Proxy Architecture Document]
- [OAuth 2.0 Client Credentials Design Document]
- [Artifact Resolution Design Document]


## High-Level UI Mocks

Not Applicable - The A2A proxy is a backend integration component with no user interface. Configuration is performed through YAML files, and monitoring is performed through log analysis and standard observability tools.

## Story Map



## Quality Plan

The quality strategy for the A2A proxy emphasizes comprehensive integration testing over unit testing, reflecting the proxy's role as a protocol bridge. Rather than testing individual methods in isolation, the test suite validates end-to-end workflows using a declarative test framework that simulates real-world agent interactions.

**Test Infrastructure**:

At the heart of the testing approach is a declarative YAML-based test framework that allows test scenarios to be written as data rather than code. Each test scenario defines the input message, the expected behavior of the downstream agent (simulated by a test harness), and the expected output. This approach makes tests highly readable and maintainable—adding a new test scenario is as simple as creating a new YAML file.

The test infrastructure includes several key components:
- Declarative YAML-based test scenarios for reproducible, maintainable tests
- Test A2A agent server harness for simulating external agent behavior with configurable responses
- Automatic A2A message validation against the protocol specification for every message the proxy publishes
- Shared test artifact service for validating artifact resolution in both directions

**Test Coverage**:

The test suite is organized into four major categories that collectively validate all functional requirements:

1. **Happy Path Scenarios**: Verify core functionality under normal operating conditions, including simple request/response passthrough and full streaming responses with intermediate events.

2. **Artifact Handling**: Validate the bidirectional artifact resolution mechanism, ensuring that inbound URIs are correctly resolved to bytes and outbound bytes are correctly saved and converted to URIs.

3. **Error Handling**: Confirm that the proxy behaves predictably when things go wrong, including scenarios where downstream agents are unavailable, return HTTP errors, or send malformed A2A responses.

4. **Authentication**: Test all supported authentication schemes, including static bearer tokens, API keys, and OAuth 2.0 Client Credentials flow with token caching and refresh.

5. **Advanced Features**: Test sophisticated interactions like request cancellation, authentication passthrough, and timeout handling.

**Validation Approach**:

Every test scenario includes multiple layers of validation to ensure correctness:
- All A2A messages published by the proxy are automatically validated against the A2A JSON schema, ensuring protocol compliance
- Test scenarios validate both final responses and intermediate streaming events to confirm proper event sequencing
- Artifact resolution is validated by inspecting both the downstream request (to verify URI-to-bytes conversion) and the saved artifact state (to verify bytes-to-URI conversion)
- Authentication is validated by inspecting HTTP headers in captured downstream requests

**Quality Metrics**:
- Test coverage: All functional requirements covered by declarative test scenarios
- Protocol compliance: 100% of proxy-published messages pass A2A schema validation
- Error handling: All error scenarios produce valid A2A error responses
- Performance: Proxy overhead < 50ms for non-artifact requests (measured in integration tests)

## Performance and Scalability Considerations

**Scalability Targets**:
- Support at least 10 proxied agents per proxy instance
- Handle at least 100 concurrent requests across all proxied agents
- Resource footprint (memory, CPU) scales linearly with number of proxied agents

**Performance Considerations**:
- OAuth token caching minimizes authentication overhead (tokens acquired once per cache duration)
- Concurrent requests to different agents processed in parallel (no blocking)
- Artifact resolution optimized for small artifacts; large artifacts may require streaming support (future enhancement)

**Scalability Considerations**:
- The proxy may have multiple instances deployed in the same namespace
- Proxy designed to be stateless (except for in-memory token cache) to facilitate future horizontal scaling
- No artificial limits on message size, artifact size, or response length (limited only by transport, such as Solace broker event limits, and external agents)

## Security Considerations

**Authentication & Authorization**:
- Support for multiple authentication schemes (static bearer tokens, API keys, OAuth 2.0 Client Credentials)
- OAuth 2.0 tokens cached in memory only (not persisted to disk)
- Automatic token refresh on 401 errors for OAuth-authenticated agents
- HTTPS enforcement for all OAuth token endpoints and external agent communication

**Credential Management**:
- Sensitive credentials (client secrets, tokens) stored in environment variables or secrets management systems
- Credentials never logged (even at DEBUG level)
- Credentials never hardcoded in configuration files committed to version control

**Transport Security**:
- All communication with external agents occurs over HTTPS (TLS 1.2 or higher)
- HTTP URLs for external agents rejected with clear error message

**Data Security**:
- Proxy does not expose internal mesh topology or agent details to external agents beyond A2A protocol requirements
- Artifact resolution maintains SAM's artifact scoping and access control model

**Audit & Compliance**:
- All significant events are available to be stored within the persistent 'task_events' logger so that they are available for .stim files as needed
- Authentication failures logged with sufficient detail for troubleshooting (without exposing credentials)
- Integration with SAM's existing observability infrastructure for centralized log collection

**Security Review Required**: OAuth token handling and credential management require DevSecOps team review before production deployment.

## Observability

**Logging Strategy**:
- All significant events logged at appropriate levels (INFO, WARNING, ERROR, DEBUG)
- Correlation IDs (task IDs) included in all log messages for end-to-end tracing
- Standard log format consistent with SAM's logging conventions

**Key Log Events**:
- Agent discovery: Agent card fetch success/failure, card publication
- Request forwarding: Request received, forwarded, response received
- Authentication: Token acquisition, cache hits/misses, authentication failures
- Artifact resolution: Inbound URI resolution, outbound artifact saving
- Errors: Configuration errors, network errors, external agent errors

**Monitoring Recommendations**:
- Alert on repeated 401 errors after retry (indicates configuration issue)

**Integration with Observability Tools**:
- Compatible with standard log aggregation tools (Splunk, ELK, CloudWatch)
- Structured logging format enables automated parsing and analysis
- Correlation IDs enable distributed tracing across mesh components

## Customer Documentation
- Update SAM product documentation to include A2A proxy configuration and usage

**Target Messaging**:
- **For IT Leaders**: "Reduce integration costs and accelerate AI adoption by enabling seamless integration of third-party agents"
- **For Security Teams**: "Maintain centralized control over authentication, authorization, and audit logging for all external agent interactions"
- **For Developers**: "Use standard A2A messaging to interact with external agents—no custom integration code required"

## Package Pricing Consideration

Not Applicable - The A2A proxy is an internal infrastructure component of the Solace Agent Mesh framework and is not separately priced or packaged. It is included as part of the standard SAM offering.
