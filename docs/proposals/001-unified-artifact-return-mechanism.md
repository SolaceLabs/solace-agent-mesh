# Project Proposal: Unified Artifact Return Mechanism

## 1. Problem Statement

Currently, AI agents have two distinct mechanisms for returning files or artifacts to the user:

1.  **Tool-based Signaling:** The agent can call the `signal_artifact_for_return` tool to flag an existing artifact for return.
2.  **Content-based Embedding:** The agent can use the `«artifact_content:...»` embed to inject the raw content of an artifact (as text or a data URI) directly into its response.

This dual approach has several significant drawbacks:
*   **Inefficiency and Cost:** The tool-based method requires an additional, often unnecessary, turn with the LLM, which increases latency and operational costs.
*   **Inconsistent User Experience:** The two methods result in different data structures being sent to the frontend, leading to inconsistent rendering of returned files and a disjointed user experience.
*   **Increased Complexity:** Supporting and testing two separate pathways for the same core function complicates the agent's logic, the gateway's processing, and our overall testing strategy.

## 2. Goals and Objectives

This project aims to refactor and unify the artifact return process to address the problems above. The primary goals are:

*   **Improve Efficiency:** Eliminate the extra LLM turn required for returning artifacts, reducing both latency and cost.
*   **Unify the Mechanism:** Consolidate all file-return actions into a single, declarative, embed-based system.
*   **Enhance User Experience:** Ensure all returned files, regardless of their origin (existing artifacts or generated content), are presented to the user in a consistent and predictable manner.
*   **Simplify Agent Logic:** Abstract away the complexities of message construction from the agent, allowing it to focus solely on reasoning and generating text-based instructions.

## 3. High-Level Requirements

The new system must meet the following requirements:

1.  **Deprecate Tool-Based Return:** The `signal_artifact_for_return` tool must be completely removed from the system.
2.  **Introduce New `artifact_return` Embed:** A new embed, `«artifact_return:filename:version»`, will be introduced as the sole method for an agent to signal that an existing artifact should be returned to the user.
3.  **Gateway-Side Processing:** The new `artifact_return` embed must be processed by the gateway (i.e., "late resolution"). The agent will be unaware of the processing details.
4.  **Standardized `FilePart` Transformation:** The gateway must be responsible for transforming the `artifact_return` embed into a standard A2A `FilePart` object within the message stream.
5.  **Support Inline Placement:** The system must respect the LLM's intended placement of the artifact within its response. If the embed is placed in the middle of a sentence, the gateway will split the `TextPart` and insert the `FilePart` at the correct position in the message's part list.
6.  **Normalize Binary `artifact_content`:** `artifact_content` embeds that resolve to binary data (e.g., images, PDFs) must be automatically converted by the gateway into a standard `FilePart` with inline bytes, rather than being embedded as a data URI.
7.  **Update Agent Prompting:** The agent's system prompt must be updated to remove instructions for the old tool and clearly explain the usage and purpose of the new `artifact_return` embed.

## 4. Key Decisions Made

During the planning phase, the following key architectural decisions have been made:

*   **Resolution Strategy (Late vs. Early):** We have chosen **late resolution** for the `artifact_return` embed. This means the gateway, not the agent, is responsible for processing the embed. This decision prioritizes agent simplicity and centralizes presentation logic and security enforcement in the gateway.
*   **Inline File Placement:** To provide a superior user experience, the gateway will split `TextPart`s to insert `FilePart`s at the location specified by the LLM, preserving the conversational flow.
*   **`artifact_content` Normalization:** To ensure consistency, binary content from `artifact_content` embeds will be converted into `FilePart`s with inline bytes, avoiding the creation of temporary artifacts and standardizing the output format.
*   **Context-Aware Resolution:** The new `artifact_return` embed will be processed **only** in the context of final messages being sent to a user. It will be ignored in other contexts, such as tool parameter resolution or recursive artifact processing, to prevent unintended side effects.

## 5. Out of Scope

*   A detailed technical design and implementation plan. This will be developed in a subsequent phase.
*   Major changes to the frontend rendering logic. This project aims to provide a consistent data structure that the existing frontend can already handle or can be adapted to handle with minimal changes.
*   Changes to the underlying `ArtifactService` interface or storage mechanisms.

## 6. Implementation Status

**Status:** Implemented
**Commit:** [Final Commit Hash]
