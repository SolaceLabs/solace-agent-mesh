# Detailed Design: Unified Artifact Return Mechanism

## 1. Introduction

This document outlines the detailed technical design for the "Unified Artifact Return Mechanism" feature. The goal is to replace the current dual-method system (a tool call and a content embed) with a single, efficient, and consistent embed-based approach for returning files from an agent to a user. This design prioritizes agent simplicity, gateway control, and a consistent user experience.

## 2. Core Components to be Modified

This feature will involve changes to the following key areas of the codebase:

-   **Agent Tools (`src/solace_agent_mesh/agent/tools/`)**: Removal of the existing `signal_artifact_for_return` tool.
-   **Embed Utilities (`src/solace_agent_mesh/common/utils/embeds/`)**: Introduction of new embed types, signals, and context-aware resolution logic.
-   **Gateway Base Component (`src/solace_agent_mesh/gateway/base/`)**: Implementation of the primary `List[Part]` transformation logic.
-   **Agent Callbacks (`src/solace_agent_mesh/agent/adk/callbacks.py`)**: Updates to the system prompt to instruct the LLM on the new mechanism.

## 3. Detailed Design

### 3.1. Deprecation of `signal_artifact_for_return` Tool

The `signal_artifact_for_return` function and its corresponding `BuiltinTool` definition will be completely removed from `src/solace_agent_mesh/agent/tools/builtin_artifact_tools.py`. This eliminates the inefficient tool-based pathway for returning artifacts.

### 3.2. New `artifact_return` Embed

A new "late" embed type will be introduced to serve as the primary mechanism for returning existing artifacts.

-   **Syntax**: `«artifact_return:FILENAME:VERSION»`
    -   `FILENAME`: The name of the artifact in the artifact store.
    -   `VERSION`: The specific version to return (e.g., `1`, `2`). If omitted, it defaults to `"latest"`.
-   **Purpose**: When an LLM includes this embed in its response, it is a declarative instruction to the gateway to attach the specified artifact to the message.
-   **Resolution**: This is a "late" embed, meaning the agent produces it as plain text. The gateway is solely responsible for its parsing and processing.

### 3.3. Normalization of Binary `artifact_content`

To ensure all returned files are handled consistently, the behavior of the `«artifact_content:...»` embed will be normalized at the gateway level.

-   When an `artifact_content` embed resolves to binary data (e.g., an `image/*` or `application/pdf` MIME type), the gateway will **not** embed it as a data URI.
-   Instead, the gateway will intercept the binary content and transform it into a standard A2A `FilePart` with the content included as inline bytes.
-   The original `«artifact_content:...»` embed in the text will be replaced, and the new `FilePart` will be inserted into the message's part list at that location.

### 3.4. Context-Aware Embed Resolution

The embed resolution system will be made context-aware to ensure embeds are only processed where they make sense.

-   A `ResolutionMode` enum will be introduced with values such as:
    -   `A2A_MESSAGE_TO_USER`: For processing final messages in the gateway.
    -   `TOOL_PARAMETER`: For resolving embeds in tool arguments within the agent.
    -   `RECURSIVE_ARTIFACT_CONTENT`: For resolving embeds inside another artifact's content.
-   The `artifact_return` embed will **only** be active in the `A2A_MESSAGE_TO_USER` mode. In all other modes, it will be treated as plain text and ignored by the resolver.
-   This prevents unintended side effects, such as trying to "return a file" from within a tool parameter.

### 3.5. Gateway `Part` List Transformation

The most significant change will be in the gateway's processing logic. The embed resolution process will be elevated from a simple `string -> string` transformation to a `List[Part] -> List[Part]` transformation.

-   A new primary resolver function, `resolve_embeds_in_parts_list`, will be created for the gateway.
-   This function will iterate through the `parts` of an outgoing A2A message.
-   When it encounters a `TextPart` containing an `artifact_return` or a binary `artifact_content` embed, it will perform the following transformation:
    1.  The `TextPart` will be split at the location of the embed.
    2.  The embed will be processed to create a corresponding `FilePart` (either with a URI for `artifact_return` or with inline bytes for binary `artifact_content`).
    3.  The original `TextPart` will be replaced by a new sequence of parts, e.g., `[TextPart (before), FilePart (the artifact), TextPart (after)]`.
-   This preserves the LLM's intended placement of files within the conversational flow.

### 3.6. Signal-Based Processing

To facilitate the `Part` list transformation, the low-level embed resolver will use a signal-based system.

-   When `evaluate_embed` in `resolver.py` processes an `artifact_return` embed, it will not return text. Instead, it will return a signal tuple, e.g., `(None, "SIGNAL_ARTIFACT_RETURN", {"filename": "report.pdf", "version": 1})`.
-   Similarly, when it processes a binary `artifact_content` embed, it will return a `SIGNAL_INLINE_BINARY_CONTENT` signal containing the raw bytes, filename, and MIME type.
-   The higher-level `resolve_embeds_in_parts_list` function in the gateway will consume these signals to perform the part splitting and insertion logic described above.

### 3.7. Error Handling

The gateway will handle resolution errors gracefully:

-   If an `artifact_return` embed references an artifact that does not exist or that the user is not authorized to access, the gateway will replace the embed with a user-friendly error message in the final text (e.g., `[Error: Artifact 'report.pdf' not found.]`).

### 3.8. Prompt Engineering

The agent's system prompt, located in `src/solace_agent_mesh/agent/adk/callbacks.py`, will be updated to:

-   Remove all references and instructions related to the deprecated `signal_artifact_for_return` tool.
-   Provide clear, explicit instructions on how and when to use the new `«artifact_return:filename:version»` embed.
-   Clarify that this is the **only** correct way to return an existing artifact as a file attachment.
-   Explain that using `«artifact_content:...»` for binary files will result in them being automatically attached, so the LLM does not need to take special action.
