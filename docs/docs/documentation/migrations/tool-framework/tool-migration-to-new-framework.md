---
title: "Migration Guide: Upgrading to the New Tool Framework"
sidebar_position: 10
---

This guide is for developers who have built custom tools for Solace Agent Mesh. A recent architectural update introduces a new tool framework that significantly reduces boilerplate code and provides better patterns for artifact handling, context access, and return values.

This document provides a comprehensive guide to migrating your existing tools to the new framework patterns.

## Why the Change?

The migration to the new tool framework provides several key benefits:

* **Reduced Boilerplate:** Automatic artifact loading and saving eliminates 15+ lines of repetitive code per tool.
* **Type Safety:** New type hints (`ArtifactContent`, `ToolResult`) provide better IDE support and catch errors earlier.
* **Cleaner Context Access:** The `ToolContextFacade` provides a simple, read-only interface instead of accessing internal implementation details.
* **Explicit Data Handling:** `DataDisposition` makes it clear how tool outputs should be handled (inline, artifact, or preview).
* **Future-Proofing:** Insulates your tools from internal implementation changes in the framework.

## New Framework Components

The new tool framework introduces four key components:

1. **ToolResult** - Structured return type with automatic artifact handling
2. **ArtifactContent** - Type hint for automatic artifact pre-loading
3. **ToolContextFacade** - Simplified read-only access to context and artifacts
4. **DataObject** - Explicit data disposition (inline, artifact, or preview)

## Quick Reference

| Old Pattern | New Pattern |
|-------------|-------------|
| Return `{"status": "success", ...}` | Return `ToolResult(message=..., data=[...])` |
| Manual `load_artifact_content_or_metadata()` | Type hint `ArtifactContent` or `ctx.load_artifact()` |
| Manual `save_artifact_with_metadata()` | `DataObject(disposition=ARTIFACT)` in ToolResult |
| Access `tool_context._invocation_context` | Use `ToolContextFacade` (ctx) |
| Access config via `host_component.get_config()` | Use `ctx.get_config()` |

## Migration Steps

### Step 1: Update Imports

```python
# Old imports
from google.adk.tools import ToolContext
from solace_agent_mesh.agent.utils.artifact_helpers import (
    load_artifact_content_or_metadata,
    save_artifact_with_metadata,
)
from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id

# New imports
from solace_agent_mesh.agent.tools import (
    register_tool,
    ToolResult,
    DataObject,
    DataDisposition,
    ArtifactContent,  # Only if using type hint for pre-loading
)
from solace_agent_mesh.agent.utils import ToolContextFacade
```

### Step 2: Update Function Signature

```python
# Old signature
async def my_tool(
    input_filename: str,
    param1: str,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:

# New signature (with artifact pre-loading)
@register_tool(name="my_tool", description="...")
async def my_tool(
    input_content: ArtifactContent,  # Auto-loaded
    input_filename: str,  # Keep for format detection
    param1: str,
    ctx: ToolContextFacade = None,  # Auto-injected
) -> ToolResult:

# New signature (without artifact pre-loading)
@register_tool(name="my_tool", description="...")
async def my_tool(
    input_filename: str,
    param1: str,
    ctx: ToolContextFacade = None,  # Auto-injected
) -> ToolResult:
    # Use ctx.load_artifact() inside function
```

### Step 3: Update Context Access

```python
# Old pattern - accessing context internals
inv_context = tool_context._invocation_context
app_name = inv_context.app_name
user_id = inv_context.user_id
session_id = get_original_session_id(inv_context)
host_component = getattr(inv_context.agent, "host_component", None)
config = host_component.get_config("key", default) if host_component else default

# New pattern - using facade
config = ctx.get_config()
# Access session_id, user_id, app_name via ctx properties if needed
session_id = ctx.session_id
user_id = ctx.user_id
app_name = ctx.app_name
```

### Step 4: Update Artifact Loading

**Option A: Use ArtifactContent Type Hint (Recommended for Single Files)**

```python
# Old pattern
async def my_tool(input_filename: str, tool_context: ToolContext = None):
    inv_context = tool_context._invocation_context
    # Parse filename:version format (rsplit to handle colons in filenames)
    parts = input_filename.rsplit(":", 1)
    if len(parts) == 2 and parts[1].isdigit():
        filename_base = parts[0]
        version = int(parts[1])
    else:
        filename_base = input_filename
        version = "latest"

    load_result = await load_artifact_content_or_metadata(
        artifact_service=inv_context.artifact_service,
        app_name=inv_context.app_name,
        user_id=inv_context.user_id,
        session_id=get_original_session_id(inv_context),
        filename=filename_base,
        version=version,
        return_raw_bytes=True,
        component=host_component,
    )
    if load_result["status"] != "success":
        return {"status": "error", "message": load_result["message"]}
    content = load_result["raw_bytes"]

# New pattern - content is pre-loaded automatically!
@register_tool(name="my_tool", description="...")
async def my_tool(
    input_content: ArtifactContent,  # Framework loads this before calling
    input_filename: str,
    ctx: ToolContextFacade = None,
) -> ToolResult:
    # input_content is already loaded - use it directly
    content = input_content  # bytes or str
```

**Option B: Use ctx.load_artifact() (For Dynamic/Multiple Files)**

```python
# New pattern for dynamic loading
@register_tool(name="my_tool", description="...")
async def my_tool(
    input_files: Dict[str, str],  # Multiple files
    ctx: ToolContextFacade = None,
) -> ToolResult:
    for table_name, filename in input_files.items():
        # Parse filename:version format (rsplit to handle colons in filenames)
        parts = filename.rsplit(":", 1)
        if len(parts) == 2 and parts[1].isdigit():
            filename_base = parts[0]
            version = int(parts[1])
        else:
            filename_base = filename
            version = "latest"

        # Simple one-liner instead of 15+ lines
        content = await ctx.load_artifact(filename_base, version=version)
        metadata = await ctx.load_artifact_metadata(filename_base, version=version)
```

### Step 5: Update Return Values

```python
# Old pattern - dict with manual status
return {
    "status": "success",
    "message": "Operation completed",
    "output_filename": "result.json",
    "output_version": version,
    "preview": preview_data,
}

# Old error pattern
return {"status": "error", "message": "Something went wrong"}

# New pattern - structured ToolResult
return ToolResult(
    message="Operation completed",
    data=[
        DataObject(
            data=result_bytes,
            disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
            filename="result.json",
            mime_type="application/json",
            description="Result of operation",
            metadata={"key": "value"},
            preview=preview_data,
        )
    ],
    metadata={
        "output_filename": "result.json",
    },
)

# New error pattern
return ToolResult.error("Something went wrong")
```

### Step 6: Update Artifact Saving

```python
# Old pattern - manual save
artifact_service = inv_context.artifact_service
save_result = await save_artifact_with_metadata(
    artifact_service=artifact_service,
    app_name=inv_context.app_name,
    user_id=inv_context.user_id,
    session_id=get_original_session_id(inv_context),
    filename=output_filename,
    content_bytes=result_bytes,
    mime_type="application/json",
    metadata_dict={"description": "..."},
    timestamp=datetime.now(timezone.utc),
    schema_max_keys=schema_max_keys,
)
if save_result["status"] == "error":
    raise IOError(save_result["message"])

# New pattern - automatic via ToolResult
# Just include DataObject in your ToolResult - framework handles saving!
return ToolResult(
    message="Success",
    data=[
        DataObject(
            data=result_bytes,
            disposition=DataDisposition.ARTIFACT,  # Will be saved automatically
            filename=output_filename,
            mime_type="application/json",
            description="...",
            metadata={...},
        )
    ],
)
```

## DataDisposition Options

| Disposition | Behavior |
|-------------|----------|
| `AUTO` | Framework decides based on size/type |
| `INLINE` | Return directly to LLM, no artifact |
| `ARTIFACT` | Save as artifact, return filename to LLM |
| `ARTIFACT_WITH_PREVIEW` | Save as artifact + include preview in response |

## Working with Multiple Artifacts

### Use List[ArtifactContent] for Multiple Pre-loaded Artifacts

When your tool needs multiple artifacts of the same type, use `List[ArtifactContent]`:

```python
from typing import List
from solace_agent_mesh.agent.tools import (
    ArtifactContent, ToolResult, DataObject, DataDisposition, register_tool
)
from solace_agent_mesh.agent.utils import ToolContextFacade

@register_tool(name="merge_files", description="Merge multiple files together")
async def merge_files(
    input_files: List[ArtifactContent],  # LLM provides list of filenames
    output_name: str,
    ctx: ToolContextFacade = None,
) -> ToolResult:
    # input_files is already a list of loaded content (bytes or str)
    merged = b"".join(f if isinstance(f, bytes) else f.encode() for f in input_files)

    return ToolResult(
        message=f"Merged {len(input_files)} files",
        data=[DataObject(
            data=merged,
            disposition=DataDisposition.ARTIFACT,
            filename=output_name,
        )]
    )
```

**Schema Translation:**
- `List[ArtifactContent]` -> LLM sees: `array of strings` (artifact filenames)
- Tool receives: `list` of artifact contents

**Supported Type Patterns:**
| Type Hint | LLM Schema | Tool Receives |
|-----------|------------|---------------|
| `ArtifactContent` | `string` | `bytes` or `str` |
| `List[ArtifactContent]` | `array of strings` | `list[bytes]` or `list[str]` |
| `Optional[ArtifactContent]` | `string` (nullable) | `bytes`, `str`, or `None` |
| `Optional[List[ArtifactContent]]` | `array` (nullable) | `list` or `None` |

## When to Use Which Pattern

### Use ArtifactContent Type Hint When:
- Tool has a single, known input artifact
- The artifact filename is a direct parameter
- You want zero-boilerplate artifact loading

### Use List[ArtifactContent] Type Hint When:
- Tool needs multiple artifacts of the same type
- The number of artifacts is variable but known at call time
- All artifacts should be loaded before tool execution

### Use ctx.load_artifact() When:
- Tool has multiple input files with different roles (e.g., dict mapping)
- Input files are determined dynamically during execution
- You need to load artifacts conditionally

### Use ToolResult + DataObject When:
- Tool produces output that should be saved as artifact
- You want explicit control over data disposition
- You need to include metadata with the artifact

## Executor Tools (Lambda/HTTP): Using `type: artifact`

For executor-based tools (Lambda, HTTP), use `type: artifact` directly in the parameters schema:

```yaml
tools:
  - tool_type: executor
    name: process_file
    description: Process a data file
    executor: lambda
    function_arn: arn:aws:lambda:us-east-1:123456789:function:process

    parameters:
      properties:
        input_file:
          type: artifact              # Single artifact - translated to string for LLM
          description: Input file to process (supports filename:version format)
        input_files:
          type: array
          items:
            type: artifact            # List of artifacts - translated to array of strings
          description: Multiple files to merge
        output_name:
          type: string                # Regular string - no pre-loading
          description: Output filename
      required:
        - input_file
        - output_name
```

**How it works:**
1. `type: artifact` is translated to `string` in the LLM schema
2. `type: array` with `items.type: artifact` is translated to `array of strings`
3. The framework automatically pre-loads artifact content before calling the executor
4. Supports `filename:version` format (e.g., `data.csv:2` for version 2)

**Benefits over deprecated `artifact_content_args`:**
- Type info is co-located with parameter definition
- No separate lists to maintain
- Cleaner, more intuitive configuration

## Complete Examples

For complete migration examples, see the example tool implementations in the source code:
- `src/solace_agent_mesh/agent/tools/examples/migrated_jmespath_tool.py` - Uses ArtifactContent type hint
- `src/solace_agent_mesh/agent/tools/examples/migrated_sql_tool.py` - Uses ctx.load_artifact() for multiple files

Both demonstrate the full migration from old to new patterns.
