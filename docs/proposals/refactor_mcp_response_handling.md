# Refactoring Proposal: MCP Tool Response Handling

**Status:** Proposed

## 1. Goal

The primary goal of this refactoring is to simplify, clarify, and improve the robustness of the logic responsible for handling and saving responses from MCP (Mission-Critical Plugin) tools.

## 2. Problem Statement

The current implementation for saving MCP tool responses as artifacts has become overly complex and difficult to maintain. The key issues are:

*   **Unclear Data Contract:** The function `save_mcp_response_as_artifact_intelligent` returns a generic dictionary with a conditional structure, forcing the calling function to perform complex and brittle checks to understand the outcome.
*   **Information Loss:** The current wrapper function arbitrarily selects a "primary artifact" when multiple artifacts are created, immediately losing information about other successfully saved items.
*   **Confusing Logic:** The presence of a redundant wrapper function (`_save_mcp_response_as_artifact`) adds an unnecessary layer of complexity and obscures the data flow.
*   **Poor Separation of Concerns:** The calling function (`manage_large_mcp_tool_responses_callback`) contains too much logic dedicated to interpreting the ambiguous return value from the save operation.

## 3. Requirements

The refactored implementation must meet the following requirements:

1.  **Establish a Clear Data Contract:** The result of the artifact saving operation must be returned in a predictable, type-safe, and self-describing data structure.
2.  **Preserve All Information:** The result must report on *all* artifacts that were successfully created, not just a single "primary" one.
3.  **Explicitly Signal Failure/Fallback:** The data structure must clearly and unambiguously distinguish between successfully created "intelligent" artifacts and any "fallback" artifact created as a recovery measure.
4.  **Simplify Consumer Logic:** The calling function must be able to easily understand the outcome of the save operation by inspecting the returned data structure, without needing complex conditional logic.
5.  **Improve Maintainability:** The code should be easier to read, test, and extend by removing redundant layers and clarifying the data flow.

## 4. Decisions

Based on the analysis, the following decisions have been made for the refactoring:

1.  **Introduce a Pydantic Model:** A new Pydantic model, `McpSaveResult`, will be created to serve as the strict data contract for the result of the save operation.
2.  **Model Structure:** The `McpSaveResult` model will include:
    *   A `status` field (Enum: `SUCCESS`, `PARTIAL_SUCCESS`, `ERROR`).
    *   A `message` field for a human-readable summary.
    *   An `artifacts_saved` field, which will be a list of all successfully created intelligent artifacts.
    *   A separate, optional `fallback_artifact` field. The presence of this field explicitly signals that the fallback mechanism was triggered.
3.  **Eliminate Redundancy:** The wrapper function `_save_mcp_response_as_artifact` in `src/solace_agent_mesh/agent/adk/callbacks.py` will be removed.
4.  **Direct Invocation:** The primary callback, `manage_large_mcp_tool_responses_callback`, will be updated to directly call `save_mcp_response_as_artifact_intelligent` and will be refactored to work with the new `McpSaveResult` model, simplifying its logic.
