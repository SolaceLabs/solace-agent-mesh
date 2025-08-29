# Refactoring Proposal: Gateway-Centric Artifact Handling

**Date:** 2025-08-29
**Status:** Proposed

## 1. Goals

The primary goal of this refactoring is to establish a robust, scalable, and consistent mechanism for handling file attachments within the A2A (Agent-to-Agent) protocol. This initiative aims to:

*   **Centralize Policy:** Move artifact handling logic from individual clients and agents into the gateway layer, making the gateway the single point of policy enforcement.
*   **Improve Scalability & Stability:** Prevent large file payloads from being sent over the event mesh, which can cause performance issues or violate message size limits.
*   **Simplify Implementations:** Reduce the complexity of client-side applications and backend agents by providing a clear, standardized method for file exchange.
*   **Enhance Flexibility:** Support multiple file handling strategies (inline vs. referenced) through clear configuration, allowing the system to be adapted for different use cases and network environments.

## 2. Requirements

To achieve these goals, the following requirements must be met:

1.  **Hybrid Client-Side Upload:** The primary web UI client (`http_sse` gateway) must implement a hybrid upload strategy.
    *   Files smaller than a defined threshold (**1 MB**) shall be sent inline as base64-encoded data.
    *   Files larger than or equal to the threshold shall be uploaded to the artifact store, and a standard `artifact://` URI shall be sent.

2.  **Gateway-Level Normalization Policy:** The `BaseGatewayComponent` must be responsible for normalizing `FilePart` objects before publishing them to the A2A mesh. This policy will be controlled by a new `artifact_handling_mode` configuration parameter.

3.  **Configurable `artifact_handling_mode`:** The gateway configuration must support the following modes:
    *   **`reference` (Default):** The gateway ensures all `FilePart` objects in an outgoing A2A message contain a URI. If it receives a part with inline `bytes`, it will save the content to the artifact store and replace the `bytes` with the corresponding `artifact://` URI.
    *   **`embed`:** The gateway ensures all `FilePart` objects contain inline `bytes`. If it receives a part with a `uri`, it will resolve the URI, fetch the content, and replace the `uri` with the base64-encoded `bytes`. This is useful for agents that may not have access to the artifact store.
    *   **`passthrough`:** The gateway does not modify `FilePart` objects and sends them to the agent exactly as they were received from the client.

4.  **Standardized URI Management:**
    *   A centralized utility for formatting and parsing `artifact://` URIs must be created to ensure consistency across the system.
    *   The artifact upload endpoint (`/api/artifacts/{filename}`) must be updated to return a valid `artifact://` URI upon successful upload.

5.  **Agent Simplification:** The agent's responsibility should be simplified. When the gateway is in the default `reference` mode, agents only need to be concerned with resolving `artifact://` URIs, not with handling inline file data from external clients.

## 3. Key Decisions

Based on the goals and requirements, the following architectural decisions have been made:

1.  **Threshold for Inline Files:** The size threshold for sending files inline from the client will be **1 MB**. This provides a reasonable balance between the convenience of inline data for small files and the performance benefits of referenced data for larger ones.

2.  **Centralized Logic in Base Gateway:** All normalization logic for file handling (`reference` and `embed` modes) will be implemented in the `BaseGatewayComponent`. This ensures the functionality is available to all current and future gateway implementations and promotes a consistent architecture.

3.  **Default Gateway Behavior:** The default `artifact_handling_mode` for all gateways will be `reference`. This is the most robust and scalable option, prioritizing system stability by keeping A2A message payloads small by default.

4.  **URI Utility Location:** The new URI formatting and parsing utilities will be located in `src/solace_agent_mesh/agent/utils/artifact_helpers.py`. This file already contains related artifact management functions, making it the most logical and discoverable location.

5.  **Frontend Responsibility:** The frontend (`ChatProvider`) is responsible for implementing the initial size-based check to decide whether to send a file inline (`bytes`) or as a reference (`uri`). This offloads the initial processing from the gateway and aligns with the hybrid upload requirement.
