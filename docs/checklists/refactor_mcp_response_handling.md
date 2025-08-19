# Implementation Checklist: Refactor MCP Response Handling

1.  **Define Data Models:** In `src/solace_agent_mesh/agent/adk/intelligent_mcp_callbacks.py`, create the Pydantic models: `McpSaveStatus` (Enum), `SavedArtifactInfo`, and `McpSaveResult`.

2.  **Refactor `save_mcp_response_as_artifact_intelligent`:**
    -   Change the function signature in `intelligent_mcp_callbacks.py` to return `-> McpSaveResult`.
    -   Update all `return` statements in the function to instantiate and return an `McpSaveResult` object instead of a dictionary.

3.  **Delete Wrapper Function:**
    -   In `src/solace_agent_mesh/agent/adk/callbacks.py`, delete the entire `_save_mcp_response_as_artifact` function.

4.  **Refactor `manage_large_mcp_tool_responses_callback`:**
    -   In `src/solace_agent_mesh/agent/adk/callbacks.py`, find the call to `_save_mcp_response_as_artifact`.
    -   Replace it with a direct `await` call to `save_mcp_response_as_artifact_intelligent`.
    -   Simplify the logic that follows the call to use the attributes of the returned `McpSaveResult` object (e.g., `save_result.status`, `save_result.artifacts_saved`).

5.  **Update Documentation:**
    -   Review and update the docstrings for all modified functions to reflect the new data models and simplified call chain.
