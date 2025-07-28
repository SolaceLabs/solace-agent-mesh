# Feature Proposal: A2A Protocol Translation Layer for Proxy

This document outlines a proposal to implement a protocol translation layer within the `A2AProxyComponent`.

## 1. Goals

The primary goals of this feature are to:

-   **Enable Interoperability:** Allow the `A2AProxyComponent` to communicate successfully with modern, spec-compliant A2A agents that use the official `a2a-python` SDK and protocol.
-   **Maintain Backward Compatibility:** Allow the existing Solace Agent Mesh (SAM) ecosystem, including agents and gateways, to continue operating on the current legacy A2A protocol without requiring an immediate, system-wide refactor.
-   **Unblock Development and Testing:** Enable the creation of robust, declarative integration tests for the proxy component by allowing it to interact with a controllable, spec-compliant test agent.
-   **Isolate Complexity:** Confine all logic related to the protocol mismatch to a single, well-defined component, creating a clear "seam" for future upgrades.

## 2. Requirements

To achieve these goals, the `A2AProxyComponent` must meet the following requirements:

1.  **Legacy Protocol Ingress:** The component must continue to accept and understand requests formatted according to the legacy SAM A2A protocol (e.g., methods like `tasks/send` and `tasks/sendSubscribe`).
2.  **Modern Protocol Egress:** The component must translate incoming legacy requests into the modern A2A specification format (e.g., methods like `message/send` and `message/stream`) before forwarding them to a downstream agent.
3.  **Modern Client Implementation:** The component must use the official `a2a-python` client library (`a2a.client.A2AClient`) to handle all communication with the downstream agent, ensuring correctness and adherence to the modern spec.
4.  **Modern Protocol Ingress (Responses):** The component must be able to receive and parse responses and event streams from the downstream agent, which will be in the modern A2A format.
5.  **Legacy Protocol Egress (Responses):** The component must translate the modern A2A responses back into the legacy SAM A2A format before publishing them to the Solace event mesh for consumption by the original requester.
6.  **Data Model Mapping:** The translation layer must correctly map key fields between the two protocol versions, including but not limited to:
    -   RPC method names.
    -   Task and session/context identifiers (`sessionId` vs. `context_id`).
    -   Request and response payload structures (`TaskSendParams` vs. `MessageSendParams`).

## 3. Decisions

Based on the goals and requirements, the following key decisions have been made:

1.  **Location of Logic:** All translation logic will be implemented and encapsulated entirely within the `A2AProxyComponent`. No other components in the SAM framework will be modified as part of this feature.
2.  **Proxy's Dual Role:** The proxy will be designed to operate with two "faces":
    -   A **"Server Face"** that listens on the Solace mesh and speaks the legacy SAM A2A protocol.
    -   A **"Client Face"** that communicates over HTTP and speaks the modern A2A protocol, powered by the `a2a-python` client library.
3.  **Acceptance of Technical Debt:** This translation layer is explicitly recognized as a form of technical debt. It is a pragmatic, temporary solution to bridge the two protocol versions. It should be tracked and scheduled for removal once the entire SAM framework is upgraded to the modern A2A specification.
4.  **Handling of Superset Features:** The modern A2A specification includes features not present in the legacy protocol (e.g., `tasks/pushNotificationConfig/list`). The proxy's server-facing side will not expose these features, as no legacy client would know how to invoke them. The proxy's client-facing side, however, will be capable of using them if ever required by internal logic.
