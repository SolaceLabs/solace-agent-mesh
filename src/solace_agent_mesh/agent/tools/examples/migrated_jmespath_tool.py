"""
Migrated transform_data_with_jmespath tool demonstrating new patterns.

This example shows how to migrate an existing tool to use:
1. ArtifactContent type hint for automatic artifact pre-loading
2. ToolContextFacade for simplified context/config access
3. ToolResult with DataObject for automatic artifact saving

BEFORE (old pattern):
- Manually extract invocation_context, app_name, user_id, session_id
- Manually call load_artifact_content_or_metadata() with all parameters
- Manually call save_artifact_with_metadata() with all parameters
- Return dict with status/message/output_filename

AFTER (new pattern):
- Annotate input parameter with ArtifactContent -> auto-loaded before call
- Use ToolContextFacade (ctx) for config access
- Return ToolResult with DataObject -> auto-saved based on disposition
"""

import logging
import json
import uuid
from typing import Optional

try:
    import jmespath
    JMESPATH_AVAILABLE = True
except ImportError:
    JMESPATH_AVAILABLE = False

try:
    import yaml
    PYYAML_AVAILABLE = True
except ImportError:
    PYYAML_AVAILABLE = False

from solace_agent_mesh.agent.tools import (
    register_tool,
    ToolResult,
    DataObject,
    DataDisposition,
    ArtifactContent,
)
from solace_agent_mesh.agent.utils import ToolContextFacade

log = logging.getLogger(__name__)


def _parse_input_data(content: bytes, filename: str) -> dict:
    """Parse input content based on file extension."""
    content_str = content.decode("utf-8") if isinstance(content, bytes) else content
    lower_filename = filename.lower()

    if lower_filename.endswith(".json"):
        return json.loads(content_str)
    elif lower_filename.endswith((".yaml", ".yml")):
        if not PYYAML_AVAILABLE:
            raise ImportError("PyYAML is required for YAML files")
        return yaml.safe_load(content_str)
    elif lower_filename.endswith(".csv"):
        # Convert CSV to list of dicts
        import csv
        import io
        reader = csv.DictReader(io.StringIO(content_str))
        return list(reader)
    else:
        # Try JSON first, then YAML
        try:
            return json.loads(content_str)
        except json.JSONDecodeError:
            if PYYAML_AVAILABLE:
                return yaml.safe_load(content_str)
            raise ValueError(f"Could not parse {filename} as JSON or YAML")


def _truncate_preview(data, max_items: int = 50, max_bytes: int = 2048) -> tuple:
    """Create a truncated preview of the result."""
    if isinstance(data, list):
        truncated = len(data) > max_items
        preview = data[:max_items] if truncated else data
    else:
        truncated = False
        preview = data

    preview_str = json.dumps(preview, indent=2)
    if len(preview_str) > max_bytes:
        preview_str = preview_str[:max_bytes] + "..."
        truncated = True

    return preview_str, truncated


@register_tool(
    name="transform_data_with_jmespath_v2",
    description=(
        "Applies a JMESPath expression to a JSON, YAML, or CSV artifact. "
        "The result is saved as a new JSON artifact and a preview is returned."
    ),
)
async def transform_data_with_jmespath(
    input_content: ArtifactContent,  # Auto-loaded by framework
    input_filename: str,  # Original filename (for parsing hint)
    jmespath_expression: str,
    output_filename: Optional[str] = None,
    result_description: Optional[str] = None,
    ctx: ToolContextFacade = None,  # Auto-injected by framework
) -> ToolResult:
    """
    Apply a JMESPath expression to transform data from an artifact.

    The input artifact is automatically loaded before this function is called
    thanks to the ArtifactContent type hint. The result is automatically saved
    as an artifact thanks to returning a ToolResult with DataObject.

    Args:
        input_content: The content of the input artifact (auto-loaded)
        input_filename: The filename of the input artifact (for format detection)
        jmespath_expression: The JMESPath expression to apply
        output_filename: Optional output filename (auto-generated if not provided)
        result_description: Optional description for the result artifact
        ctx: Context facade for config access (auto-injected)

    Returns:
        ToolResult containing the transformed data as an artifact
    """
    if not JMESPATH_AVAILABLE:
        return ToolResult.error(
            "The jmespath library is required but not installed."
        )

    log_id = f"[JMESPath:{input_filename}]"
    log.info("%s Applying expression: %s", log_id, jmespath_expression[:100])

    # Get config from context facade
    config = ctx.get_config() if ctx else {}
    max_preview_rows = config.get("max_result_preview_rows", 50)
    max_preview_bytes = config.get("max_result_preview_bytes", 2048)

    # Determine output filename
    final_output_filename = output_filename or f"jmespath_result_{uuid.uuid4().hex[:8]}.json"
    if not final_output_filename.endswith(".json"):
        final_output_filename += ".json"

    try:
        # Parse input data
        parsed_data = _parse_input_data(input_content, input_filename)

        # Apply JMESPath expression
        result = jmespath.search(jmespath_expression, parsed_data)

        if result is None:
            return ToolResult.error(
                f"JMESPath expression returned no results. "
                f"Expression: {jmespath_expression}"
            )

        # Serialize result to JSON bytes
        result_bytes = json.dumps(result, indent=2).encode("utf-8")

        # Create preview
        preview_str, truncated = _truncate_preview(
            result, max_preview_rows, max_preview_bytes
        )

        # Build description
        description = result_description or f"JMESPath transform of {input_filename}"
        full_description = f"{description}. Expression: `{jmespath_expression}`"

        # Return ToolResult with DataObject - artifact saving is automatic
        return ToolResult(
            message=f"Successfully transformed data. Output: {final_output_filename}",
            data=[
                DataObject(
                    data=result_bytes,
                    disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
                    filename=final_output_filename,
                    mime_type="application/json",
                    description=full_description,
                    metadata={
                        "source_artifact": input_filename,
                        "jmespath_expression": jmespath_expression,
                        "result_count": len(result) if isinstance(result, list) else 1,
                    },
                    preview=preview_str,
                )
            ],
            metadata={
                "output_filename": final_output_filename,
                "result_truncated": truncated,
            },
        )

    except jmespath.exceptions.JMESPathError as e:
        log.warning("%s Invalid JMESPath expression: %s", log_id, e)
        return ToolResult.error(f"Invalid JMESPath expression: {e}")
    except Exception as e:
        log.exception("%s Error during transform: %s", log_id, e)
        return ToolResult.error(f"Transform failed: {e}")


# =============================================================================
# COMPARISON: Old vs New Pattern
# =============================================================================
#
# OLD PATTERN (enterprise_builtin_data_analysis_tools.py):
# --------------------------------------------------------
# async def transform_data_with_jmespath(
#     input_filename: str,
#     jmespath_expression: str,
#     output_filename: Optional[str] = None,
#     result_description: Optional[str] = None,
#     tool_context: ToolContext = None,
# ) -> Dict[str, Any]:
#     # Extract context (boilerplate)
#     inv_context = tool_context._invocation_context
#     app_name = inv_context.app_name
#     user_id = inv_context.user_id
#     session_id = get_original_session_id(inv_context)
#
#     # Load artifact manually (boilerplate)
#     load_result = await load_artifact_content_or_metadata(
#         artifact_service=inv_context.artifact_service,
#         app_name=app_name,
#         user_id=user_id,
#         session_id=session_id,
#         filename=input_filename,
#         version=version,
#         return_raw_bytes=True,
#         component=host_component,
#     )
#
#     # ... process data ...
#
#     # Save artifact manually (boilerplate)
#     save_result = await save_artifact_with_metadata(
#         artifact_service=artifact_service,
#         app_name=app_name,
#         user_id=user_id,
#         session_id=session_id,
#         filename=output_filename,
#         content_bytes=result_bytes,
#         mime_type="application/json",
#         metadata_dict=metadata,
#         timestamp=datetime.now(timezone.utc),
#     )
#
#     # Return dict manually
#     return {
#         "status": "success",
#         "output_filename": output_filename,
#         "preview": preview,
#     }
#
#
# NEW PATTERN (this file):
# ------------------------
# @register_tool(name="...", description="...")
# async def transform_data_with_jmespath(
#     input_content: ArtifactContent,  # Auto-loaded!
#     input_filename: str,
#     jmespath_expression: str,
#     output_filename: Optional[str] = None,
#     result_description: Optional[str] = None,
#     ctx: ToolContextFacade = None,  # Auto-injected!
# ) -> ToolResult:
#     # Config access is simple
#     config = ctx.get_config()
#
#     # ... process data (same logic) ...
#
#     # Return ToolResult - artifact saving is automatic!
#     return ToolResult(
#         message="Success",
#         data=[DataObject(
#             data=result_bytes,
#             disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
#             filename=output_filename,
#             ...
#         )]
#     )
#
# BENEFITS:
# - ~50% less boilerplate code
# - No need to understand invocation_context internals
# - Automatic artifact loading via type hints
# - Automatic artifact saving via ToolResult/DataObject
# - Cleaner separation of concerns
# - Easier testing (mock ctx facade)
