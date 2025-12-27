"""
Migrated query_data_with_sql tool demonstrating new patterns.

This example shows how to migrate a complex multi-file tool to use:
1. ToolContextFacade for simplified context/config access AND dynamic artifact loading
2. ToolResult with DataObject for automatic artifact saving

Note: This tool cannot use ArtifactContent type hints because the number of
input files is dynamic (determined by input_files dict). Instead, it uses
ctx.load_artifact() for each file. This demonstrates that both patterns
can coexist - use type hints for simple cases, ctx.load_artifact() for dynamic.

BEFORE (old pattern):
- ~300 lines including manual context extraction and artifact handling
- Direct access to inv_context._artifact_service
- Manual calls to load_artifact_content_or_metadata() for each file
- Manual calls to save_artifact_with_metadata() for output

AFTER (new pattern):
- ~200 lines with cleaner separation
- ctx.load_artifact() for each input file
- ToolResult with DataObject for automatic output saving
"""

import logging
import json
import io
import os
import sqlite3
import tempfile
import uuid
from typing import Any, Dict, List, Literal, Optional

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

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
)
from solace_agent_mesh.agent.utils import ToolContextFacade

log = logging.getLogger(__name__)

SQLITE_DB_MIME_TYPE = "application/vnd.sqlite3"


def _create_dataframe_from_data(
    data: Any, mime_type: str, filename: str, config: dict, log_id: str
) -> "pd.DataFrame":
    """Create a pandas DataFrame from loaded data based on MIME type."""
    if mime_type == "text/csv":
        log.debug("%s Parsing as CSV.", log_id)
        if isinstance(data, bytes):
            return pd.read_csv(io.BytesIO(data))
        else:
            return pd.read_csv(io.StringIO(data))

    elif mime_type == "application/json":
        log.debug("%s Parsing as JSON.", log_id)
        if isinstance(data, bytes):
            data = json.loads(data.decode("utf-8"))
        elif isinstance(data, str):
            data = json.loads(data)
        return _normalize_to_dataframe(data, config, log_id)

    elif mime_type in ["application/yaml", "text/yaml", "application/x-yaml", "text/x-yaml"]:
        if not PYYAML_AVAILABLE:
            raise ImportError(f"PyYAML is required for YAML input '{filename}'")
        log.debug("%s Parsing as YAML.", log_id)
        if isinstance(data, bytes):
            data = yaml.safe_load(data.decode("utf-8"))
        elif isinstance(data, str):
            data = yaml.safe_load(data)
        return _normalize_to_dataframe(data, config, log_id)

    else:
        raise ValueError(
            f"Unsupported MIME type '{mime_type}' for '{filename}'. "
            f"Supported: text/csv, application/json, application/yaml"
        )


def _normalize_to_dataframe(data: Any, config: dict, log_id: str) -> "pd.DataFrame":
    """Normalize JSON/YAML data to a DataFrame."""
    max_columns = config.get("max_columns", 100)

    if isinstance(data, list):
        if not data:
            raise ValueError("Empty list cannot be converted to DataFrame")
        df = pd.json_normalize(data)
    elif isinstance(data, dict):
        # Check if columnar format (dict of lists)
        if all(isinstance(v, list) for v in data.values()):
            df = pd.DataFrame(data)
        else:
            # Single record
            df = pd.json_normalize([data])
    else:
        raise ValueError(f"Cannot convert {type(data).__name__} to DataFrame")

    if len(df.columns) > max_columns:
        log.warning(
            "%s DataFrame has %d columns, truncating to %d",
            log_id, len(df.columns), max_columns
        )
        df = df.iloc[:, :max_columns]

    return df


def _truncate_preview(
    data: List[Dict], max_rows: int = 50, max_bytes: int = 2048
) -> tuple:
    """Create a truncated preview of the result."""
    truncated = len(data) > max_rows
    preview = data[:max_rows] if truncated else data

    preview_str = json.dumps(preview, indent=2, default=str)
    if len(preview_str) > max_bytes:
        preview_str = preview_str[:max_bytes] + "..."
        truncated = True

    return preview, truncated


@register_tool(
    name="query_data_with_sql_v2",
    description=(
        "Executes a SQL query against one or more data artifacts. "
        "Supports CSV, JSON, and YAML files. Multiple files can be loaded into "
        "separate tables for JOIN operations. Use standard SQL syntax."
    ),
)
async def query_data_with_sql(
    input_files: Dict[str, str],
    sql_query: str,
    output_filename: Optional[str] = None,
    result_description: Optional[str] = None,
    output_format: Literal["csv", "json"] = "csv",
    ctx: ToolContextFacade = None,  # Auto-injected by framework
) -> ToolResult:
    """
    Execute a SQL query across one or more data artifacts.

    Unlike the JMESPath tool, this cannot use ArtifactContent type hints because
    the input files are determined dynamically. Instead, we use ctx.load_artifact()
    for each file. This demonstrates the flexibility of the new patterns.

    Args:
        input_files: Dict mapping table names to filenames (with optional :version)
                    Example: {"users": "users.csv", "orders": "orders.json:2"}
        sql_query: SQL query to execute across the loaded tables
        output_filename: Optional base name for output artifact
        result_description: Optional description for result metadata
        output_format: Output format ('csv' or 'json')
        ctx: Context facade for config and artifact access (auto-injected)

    Returns:
        ToolResult containing the query results as an artifact
    """
    if not PANDAS_AVAILABLE:
        return ToolResult.error(
            "The pandas library is required but not installed."
        )
    if not input_files:
        return ToolResult.error(
            "No input files provided. The input_files dictionary cannot be empty."
        )

    table_names = ", ".join(input_files.keys())
    log_id = f"[SQL:{table_names}]"
    log.info("%s Executing query across tables", log_id)

    # Get config from context facade
    config = ctx.get_config() if ctx else {}
    max_preview_rows = config.get("max_result_preview_rows", 50)
    max_preview_bytes = config.get("max_result_preview_bytes", 2048)

    temp_db_files = []
    conn = None

    try:
        # Create in-memory SQLite database
        conn = sqlite3.connect(":memory:")
        log.debug("%s Created in-memory SQLite database", log_id)

        # Track metadata for all source files
        source_metadata = []

        # Load each file into a separate table using ctx.load_artifact()
        for table_name, input_filename in input_files.items():
            table_log_id = f"{log_id}[{table_name}]"
            log.debug("%s Loading '%s'...", table_log_id, input_filename)

            # Parse filename and version
            parts = input_filename.split(":", 1)
            filename_base = parts[0]
            version_str = parts[1] if len(parts) > 1 else "latest"
            version = int(version_str) if version_str.isdigit() else "latest"

            # Use ToolContextFacade for simplified artifact loading
            try:
                content = await ctx.load_artifact(filename_base, version=version)
                metadata = await ctx.load_artifact_metadata(filename_base, version=version)
            except Exception as load_err:
                raise FileNotFoundError(
                    f"Failed to load '{input_filename}': {load_err}"
                )

            # Track source metadata
            source_metadata.append({
                "table_name": table_name,
                "filename": filename_base,
                "version": metadata.get("version") if metadata else version,
            })

            # Determine MIME type from metadata or filename
            mime_type = metadata.get("mime_type", "") if metadata else ""
            if not mime_type:
                lower_name = filename_base.lower()
                if lower_name.endswith(".csv"):
                    mime_type = "text/csv"
                elif lower_name.endswith(".json"):
                    mime_type = "application/json"
                elif lower_name.endswith((".yaml", ".yml")):
                    mime_type = "application/yaml"

            # Create DataFrame from content
            df = _create_dataframe_from_data(
                content, mime_type, input_filename, config, table_log_id
            )

            # Load DataFrame into SQLite
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            log.debug(
                "%s Loaded %d rows, %d columns into table '%s'",
                log_id, len(df), len(df.columns), table_name
            )

        # Execute the SQL query
        log.debug("%s Executing SQL query...", log_id)
        result_df = pd.read_sql_query(sql_query, conn)
        num_rows = len(result_df)
        log.info("%s Query returned %d rows", log_id, num_rows)

        # Prepare output
        if output_format == "csv":
            csv_buffer = io.StringIO()
            result_df.to_csv(csv_buffer, index=False)
            result_bytes = csv_buffer.getvalue().encode("utf-8")
            output_mime_type = "text/csv"
        else:
            result_json = result_df.to_json(orient="records", indent=2)
            result_bytes = result_json.encode("utf-8")
            output_mime_type = "application/json"

        # Generate output filename
        if output_filename:
            final_output_filename = output_filename
            if not final_output_filename.endswith(f".{output_format}"):
                final_output_filename = f"{final_output_filename}.{output_format}"
        else:
            first_table = list(input_files.keys())[0]
            final_output_filename = f"sql_result_{first_table}.{output_format}"

        # Build description
        source_summary = ", ".join(
            f"{m['table_name']} ({m['filename']})" for m in source_metadata
        )
        base_description = result_description or f"SQL query result on {source_summary}"
        full_description = f"{base_description}. Query: `{sql_query}`"

        # Create preview
        preview_data, truncated = _truncate_preview(
            result_df.to_dict(orient="records"),
            max_preview_rows,
            max_preview_bytes,
        )

        # Return ToolResult with DataObject - artifact saving is automatic!
        return ToolResult(
            message=f"Query executed successfully ({num_rows} rows). "
                   f"Results saved as '{final_output_filename}'.",
            data=[
                DataObject(
                    data=result_bytes,
                    disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
                    filename=final_output_filename,
                    mime_type=output_mime_type,
                    description=full_description,
                    metadata={
                        "source_sql_query": sql_query,
                        "result_rows": num_rows,
                        "source_tables": source_metadata,
                    },
                    preview=json.dumps(preview_data, indent=2, default=str),
                )
            ],
            metadata={
                "output_filename": final_output_filename,
                "result_rows": num_rows,
                "result_truncated": truncated,
            },
        )

    except FileNotFoundError as e:
        log.warning("%s File not found: %s", log_id, e)
        return ToolResult.error(str(e))
    except ValueError as e:
        log.warning("%s Value error: %s", log_id, e)
        return ToolResult.error(str(e))
    except (pd.errors.DatabaseError, sqlite3.Error) as e:
        log.warning("%s SQL error: %s", log_id, e)
        return ToolResult.error(f"SQL Error: {e}")
    except Exception as e:
        log.exception("%s Unexpected error: %s", log_id, e)
        return ToolResult.error(f"Unexpected error: {e}")
    finally:
        if conn:
            conn.close()
        for temp_file in temp_db_files:
            try:
                os.remove(temp_file)
            except OSError:
                pass


# =============================================================================
# KEY DIFFERENCES: Old vs New Pattern
# =============================================================================
#
# 1. CONTEXT ACCESS (simplified)
#    OLD:
#        inv_context = tool_context._invocation_context
#        app_name = inv_context.app_name
#        user_id = inv_context.user_id
#        session_id = get_original_session_id(inv_context)
#        artifact_service = inv_context.artifact_service
#
#    NEW:
#        # ctx is auto-injected, provides clean API
#        config = ctx.get_config()
#        # session_id, user_id, app_name available as ctx.session_id etc if needed
#
# 2. ARTIFACT LOADING (simplified)
#    OLD:
#        load_result = await load_artifact_content_or_metadata(
#            artifact_service=inv_context.artifact_service,
#            app_name=app_name,
#            user_id=user_id,
#            session_id=session_id,
#            filename=filename_base,
#            version=version,
#            return_raw_bytes=True,
#            component=host_component,
#            log_identifier_prefix=log_id,
#        )
#        if load_result["status"] != "success":
#            raise FileNotFoundError(load_result["message"])
#        content = load_result["raw_bytes"]
#
#    NEW:
#        content = await ctx.load_artifact(filename_base, version=version)
#        metadata = await ctx.load_artifact_metadata(filename_base, version=version)
#        # Raises exception on failure, no status checking needed
#
# 3. ARTIFACT SAVING (automatic)
#    OLD:
#        save_result = await save_artifact_with_metadata(
#            artifact_service=artifact_service,
#            app_name=app_name,
#            user_id=user_id,
#            session_id=session_id,
#            filename=output_filename,
#            content_bytes=result_bytes,
#            mime_type=output_mime_type,
#            metadata_dict=metadata,
#            timestamp=datetime.now(timezone.utc),
#            schema_max_keys=schema_max_keys,
#        )
#        if save_result["status"] == "error":
#            raise IOError(...)
#
#    NEW:
#        return ToolResult(
#            message="Success",
#            data=[DataObject(
#                data=result_bytes,
#                disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
#                filename=output_filename,
#                mime_type=output_mime_type,
#                metadata={...},
#            )]
#        )
#        # Framework handles saving automatically!
#
# 4. RETURN VALUE (structured)
#    OLD:
#        return {
#            "status": "success",
#            "message": preview_message,
#            "output_filename": final_output_filename,
#            "output_version": save_result["data_version"],
#            "result_preview": preview_data,
#        }
#
#    NEW:
#        return ToolResult(
#            message="...",
#            data=[DataObject(...)],
#            metadata={...}
#        )
#        # Structured, type-safe, with automatic artifact handling
#
# SUMMARY:
# - Old: ~300 lines with manual plumbing
# - New: ~200 lines with cleaner separation of concerns
# - Artifact loading: Use ArtifactContent type hint for simple cases,
#   ctx.load_artifact() for dynamic cases (like this multi-file tool)
# - Artifact saving: Always use ToolResult + DataObject
