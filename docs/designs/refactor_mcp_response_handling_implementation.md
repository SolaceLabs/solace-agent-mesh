# Implementation Plan: Refactor MCP Tool Response Handling

This document outlines the detailed steps to implement the refactoring of the MCP tool response handling logic, as described in the corresponding proposal.

## 1. Define New Data Models

In `src/solace_agent_mesh/agent/adk/intelligent_mcp_callbacks.py`, we will introduce new Pydantic models to create a clear and type-safe data contract for the result of the save operation.

```python
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional

class McpSaveStatus(str, Enum):
    """Enumeration for the status of an MCP save operation."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    ERROR = "error"

class SavedArtifactInfo(BaseModel):
    """
    A Pydantic model to hold the details of a successfully saved artifact.
    This mirrors the dictionary structure returned by save_artifact_with_metadata.
    """
    status: str
    data_filename: str
    data_version: int
    metadata_filename: str
    metadata_version: int
    message: str

class McpSaveResult(BaseModel):
    """
    The definitive, type-safe result of an MCP response save operation.
    """
    status: McpSaveStatus
    message: str
    artifacts_saved: List[SavedArtifactInfo] = []
    fallback_artifact: Optional[SavedArtifactInfo] = None
```

## 2. Refactor `save_mcp_response_as_artifact_intelligent`

The function `save_mcp_response_as_artifact_intelligent` in `src/solace_agent_mesh/agent/adk/intelligent_mcp_callbacks.py` will be modified:

1.  **Change Signature:** The function's return type hint will be changed from `-> Dict[str, Any]` to `-> McpSaveResult`.
2.  **Update Return Logic:** Instead of returning a dictionary with keys like `status`, `artifacts_saved`, and `fallback_artifact`, the function will instantiate and return an `McpSaveResult` object. All existing logic paths (success, partial success, error, fallback) will be updated to populate this model correctly. The `artifacts_saved` and `fallback_artifact` will be populated with `SavedArtifactInfo` models.

## 3. Refactor `manage_large_mcp_tool_responses_callback`

The primary consumer of the save logic, `manage_large_mcp_tool_responses_callback` in `src/solace_agent_mesh/agent/adk/callbacks.py`, will be updated as follows:

1.  **Direct Invocation:** The call to the wrapper function `_save_mcp_response_as_artifact` will be replaced with a direct `await` call to `save_mcp_response_as_artifact_intelligent`.
2.  **Simplified Logic:** The complex conditional logic that checks for keys like `"status"`, `"artifacts_saved"`, and `"fallback_artifact"` in the returned dictionary will be removed.
3.  **Use New Model:** The function will now receive an `McpSaveResult` object. The logic to construct the `final_llm_response_dict` will be simplified to directly access the attributes of this model (e.g., `save_result.status`, `save_result.artifacts_saved`, `save_result.fallback_artifact`). This will make the code cleaner, more readable, and less error-prone.

## 4. Remove Redundant Wrapper Function

The function `_save_mcp_response_as_artifact` in `src/solace_agent_mesh/agent/adk/callbacks.py` will be **deleted**. Its responsibilities are now fully handled by the improved `save_mcp_response_as_artifact_intelligent` and the simplified logic in its consumer.

## 5. Update Docstrings and Comments

All relevant docstrings and comments in the modified files will be updated to reflect the new data structures, the simplified call chain, and the removal of the wrapper function. This ensures the code remains self-documenting.
