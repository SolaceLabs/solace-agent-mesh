# Artifact Handling

Guide to working with the artifact service in SAM agent plugins.

## Overview

The artifact service manages file storage and retrieval for agents. Access it through `tool_context._invocation_context.artifact_service`.

## Saving Artifacts

Use the `save_artifact_with_metadata` helper function:

```python
from datetime import datetime, timezone
from solace_agent_mesh.agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
)
from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id

async def save_file_tool(
    filename: str,
    content: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Save content to a file artifact."""

    inv_context = tool_context._invocation_context
    artifact_service = inv_context.artifact_service

    # Prepare content
    content_bytes = content.encode('utf-8')
    timestamp = datetime.now(timezone.utc)

    # Metadata for the artifact
    metadata_dict = {
        "description": f"File created by tool",
        "source_tool": "save_file_tool",
        "creation_timestamp": timestamp.isoformat(),
    }

    # Save artifact
    save_result = await save_artifact_with_metadata(
        artifact_service=artifact_service,
        app_name=inv_context.app_name,
        user_id=inv_context.user_id,
        session_id=get_original_session_id(inv_context),
        filename=filename,
        content_bytes=content_bytes,
        mime_type="text/plain",
        metadata_dict=metadata_dict,
        timestamp=timestamp,
        schema_max_keys=DEFAULT_SCHEMA_MAX_KEYS,
        tool_context=tool_context,
    )

    return {
        "status": "success" if save_result.get("status") != "error" else "error",
        "filename": filename,
        "version": save_result.get("data_version"),
    }
```

## Loading Artifacts

Handle both async and sync artifact service methods, and support `filename:version` format:

```python
import asyncio
import inspect

async def load_file_tool(
    image_filename: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Load a file artifact."""

    inv_context = tool_context._invocation_context
    artifact_service = inv_context.artifact_service

    # Parse filename:version format
    parts = image_filename.rsplit(":", 1)
    filename_base = parts[0]
    version_to_load = int(parts[1]) if len(parts) > 1 else None

    # Get latest version if not specified
    if version_to_load is None:
        list_versions_method = getattr(artifact_service, "list_versions")
        if inspect.iscoroutinefunction(list_versions_method):
            versions = await list_versions_method(
                app_name=inv_context.app_name,
                user_id=inv_context.user_id,
                session_id=get_original_session_id(inv_context),
                filename=filename_base,
            )
        else:
            versions = await asyncio.to_thread(
                list_versions_method,
                app_name=inv_context.app_name,
                user_id=inv_context.user_id,
                session_id=get_original_session_id(inv_context),
                filename=filename_base,
            )

        if not versions:
            raise FileNotFoundError(f"File '{filename_base}' not found")
        version_to_load = max(versions)

    # Load artifact
    load_artifact_method = getattr(artifact_service, "load_artifact")
    if inspect.iscoroutinefunction(load_artifact_method):
        artifact_part = await load_artifact_method(
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=filename_base,
            version=version_to_load,
        )
    else:
        artifact_part = await asyncio.to_thread(
            load_artifact_method,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=filename_base,
            version=version_to_load,
        )

    if not artifact_part or not artifact_part.inline_data:
        raise FileNotFoundError(f"Content for '{filename_base}' v{version_to_load} not found")

    # Get content
    content_bytes = artifact_part.inline_data.data
    content = content_bytes.decode('utf-8')

    return {
        "status": "success",
        "filename": filename_base,
        "version": version_to_load,
        "content": content,
    }
```

## Best Practices

1. **Always handle both async and sync** artifact service methods using `inspect.iscoroutinefunction`
2. **Support version specification** with `filename:version` format
3. **Use get_original_session_id** helper to get the correct session ID
4. **Include comprehensive metadata** when saving artifacts
5. **Handle errors gracefully** - return error dictionaries with descriptive messages
6. **Use appropriate MIME types** (text/plain, image/png, application/json, etc.)
7. **Log artifact operations** for debugging and auditing

## Common MIME Types

- Text: `text/plain`, `text/csv`, `text/html`
- Images: `image/png`, `image/jpeg`, `image/webp`, `image/gif`
- Documents: `application/pdf`, `application/json`, `application/xml`
- Archives: `application/zip`, `application/gzip`
