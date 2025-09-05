"""
Built-in ADK Tools for Data Analysis (SQL, JQ, Plotly).
"""

import uuid
import json
import os
import tempfile
import sqlite3
import io
from typing import Any, Dict, Tuple, Optional, Literal
from datetime import datetime, timezone

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

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

try:
    import plotly.io as pio
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True

except ImportError:
    PLOTLY_AVAILABLE = False


from google.adk.tools import ToolContext
from google.genai import types as adk_types
from solace_ai_connector.common.log import log

from solace_agent_mesh.agent.utils.artifact_helpers import (
    ensure_correct_extension,
    save_artifact_with_metadata,
    load_artifact_content_or_metadata,
    METADATA_SUFFIX,
    DEFAULT_SCHEMA_MAX_KEYS,
)

from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id    

from solace_agent_mesh.agent.tools.tool_definition import BuiltinTool   
from solace_agent_mesh.agent.tools.registry import tool_registry    


SQLITE_DB_MIME_TYPE = "application/vnd.sqlite3"
DEFAULT_SQLITE_TABLE_NAME = "data"
DEFAULT_DATA_TOOLS_CONFIG = {
    "sqlite_memory_threshold_mb": 10,
    "max_result_preview_rows": 50,
    "max_result_preview_bytes": 2048,
}


async def _query_dataframe_with_sql(
    df: pd.DataFrame,
    sql_query: str,
    tool_context: ToolContext,
    output_filename_base: str,
    output_format: Literal["csv", "json"] = "csv",
    result_description: Optional[str] = None,
    source_metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Core logic to run a SQL query on a pandas DataFrame and save the result.
    """
    log_identifier = f"[DataTool:_query_dataframe_with_sql:{output_filename_base}]"
    log.info(
        "%s Processing request. Query: '%s'", log_identifier, sql_query[:100] + "..."
    )

    config = _get_data_tools_config(tool_context)
    output_filename = ensure_correct_extension(output_filename_base, output_format)
    output_mime_type = "text/csv" if output_format == "csv" else "application/json"

    conn = None
    result_df = None

    try:
        db_path = ":memory:"
        log.debug("%s Using in-memory SQLite DB.", log_identifier)
        conn = sqlite3.connect(db_path)
        try:
            df.to_sql(DEFAULT_SQLITE_TABLE_NAME, conn, if_exists="replace", index=False)
            log.debug(
                "%s Loaded DataFrame into table '%s'.",
                log_identifier,
                DEFAULT_SQLITE_TABLE_NAME,
            )
        except Exception as load_err:
            raise ValueError(
                f"Failed to load DataFrame into SQLite: {load_err}"
            ) from load_err

        log.debug("%s Executing SQL query...", log_identifier)
        result_df = pd.read_sql_query(sql_query, conn)
        num_rows = len(result_df)
        log.info(
            "%s SQL query executed successfully. Result rows: %d",
            log_identifier,
            num_rows,
        )

        result_bytes: bytes
        if output_format == "csv":
            csv_buffer = io.StringIO()
            result_df.to_csv(csv_buffer, index=False)
            result_bytes = csv_buffer.getvalue().encode("utf-8")
        elif output_format == "json":
            result_json = result_df.to_json(orient="records", indent=2)
            result_bytes = result_json.encode("utf-8")
        else:
            raise ValueError(f"Invalid output_format: {output_format}")

        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")
        host_component = getattr(inv_context.agent, "host_component", None)
        schema_max_keys = (
            host_component.get_config("schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS)
            if host_component
            else DEFAULT_SCHEMA_MAX_KEYS
        )

        source_filename_for_desc = (
            source_metadata.get("filename", "data") if source_metadata else "data"
        )
        base_description = (
            result_description or f"Result of SQL query on {source_filename_for_desc}"
        )
        description = f"{base_description}. SQL Query: `{sql_query}`"

        save_metadata_dict = {
            "description": description,
            "source_sql_query": sql_query,
            "result_rows": num_rows,
        }
        if source_metadata:
            save_metadata_dict["source_artifact"] = source_metadata.get("filename")
            save_metadata_dict["source_artifact_version"] = source_metadata.get(
                "version"
            )

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=output_filename,
            content_bytes=result_bytes,
            mime_type=output_mime_type,
            metadata_dict=save_metadata_dict,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=schema_max_keys,
        )
        if save_result["status"] == "error":
            raise IOError(
                f"Failed to save query result artifact: {save_result.get('message', 'Unknown error')}"
            )

        preview_data, truncated = _truncate_result(
            result_df.to_dict(orient="records"), config
        )
        preview_message = f"Query executed successfully ({num_rows} rows). Full result saved as '{output_filename}' v{save_result['data_version']}."
        if truncated:
            preview_message += f" Preview shows first {len(preview_data)} rows."

        return {
            "status": "success",
            "message": preview_message,
            "output_filename": output_filename,
            "output_version": save_result["data_version"],
            "result_preview": preview_data,
            "result_truncated": truncated,
            "result_rows": num_rows,
        }

    except (ValueError, IOError, pd.errors.DatabaseError, sqlite3.Error) as e:
        log.warning("%s Error during SQL query execution: %s", log_identifier, e)
        return {"status": "error", "message": f"SQL Error: {e}"}
    except Exception as e:
        log.exception(
            "%s Unexpected error in _query_dataframe_with_sql: %s", log_identifier, e
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        if conn:
            conn.close()
            log.debug("%s Closed SQLite connection.", log_identifier)


def _get_data_tools_config(tool_context: ToolContext) -> Dict:
    """Safely retrieves the data_tools_config dictionary."""
    try:
        host_component = getattr(
            tool_context._invocation_context.agent, "host_component", None
        )
        if host_component:
            return host_component.get_config(
                "data_tools_config", DEFAULT_DATA_TOOLS_CONFIG
            )
        else:
            log.warning(
                "[DataToolsHelper] Could not access host component config. Using defaults."
            )
            return DEFAULT_DATA_TOOLS_CONFIG
    except Exception as e:
        log.warning(
            "[DataToolsHelper] Error accessing host component config: %s. Using defaults.",
            e,
        )
        return DEFAULT_DATA_TOOLS_CONFIG


def _truncate_result(data: Any, config: Dict) -> Tuple[Any, bool]:
    """Truncates result data based on config (rows or bytes)."""
    max_rows = config.get("max_result_preview_rows", 50)
    max_bytes = config.get("max_result_preview_bytes", 4096)
    truncated = False
    preview_data = data

    if isinstance(data, list):
        if len(data) > max_rows:
            preview_data = data[:max_rows]
            truncated = True
    elif isinstance(data, str):
        if len(data.encode("utf-8")) > max_bytes:
            encoded = data.encode("utf-8")
            preview_data = encoded[:max_bytes].decode("utf-8", errors="ignore") + "..."
            truncated = True
    elif isinstance(data, bytes):
        if len(data) > max_bytes:
            preview_data = data[:max_bytes]
            truncated = True

    return preview_data, truncated


async def query_data_with_sql(
    input_filename: str,
    sql_query: str,
    output_filename: Optional[str] = None,
    result_description: Optional[str] = None,
    output_format: Literal["csv", "json"] = "csv",
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Executes a SQL query against data from a CSV or SQLite artifact.

    If the input is CSV, it's loaded into a temporary SQLite database.
    The result is saved as a new artifact (CSV or JSON) with a specified or
    generated name, and a preview is returned. Assumes 'pandas' is installed.

    Args:
        input_filename: The filename (and optional :version) of the input CSV or SQLite artifact.
        sql_query: The SQL query to execute.
        output_filename: Optional. A base name for the output artifact. The correct extension will be added.
        result_description: Optional description for the result artifact's metadata.
        output_format: The desired format for the output artifact ('csv' or 'json'). Default 'csv'.
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary with status, output artifact details, and a preview of the result.
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext is missing."}
    if not PANDAS_AVAILABLE:
        return {
            "status": "error",
            "message": "The pandas library is required for SQL queries but it is not installed.",
        }

    log_identifier = f"[DataTool:query_data_with_sql:{input_filename}]"
    log.info(
        "%s Processing request. Query: '%s'", log_identifier, sql_query[:100] + "..."
    )

    temp_db_file = None

    try:
        app_name = tool_context._invocation_context.app_name
        user_id = tool_context._invocation_context.user_id
        session_id = get_original_session_id(tool_context._invocation_context)

        parts = input_filename.split(":", 1)
        filename_base = parts[0]
        version_str = parts[1] if len(parts) > 1 else "latest"
        version = int(version_str) if version_str.isdigit() else "latest"

        host_component = getattr(
            tool_context._invocation_context.agent, "host_component", None
        )
        load_result = await load_artifact_content_or_metadata(
            artifact_service=tool_context._invocation_context.artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename_base,
            version=version,
            return_raw_bytes=True,
            component=host_component,
            log_identifier_prefix=log_identifier,
        )

        if load_result["status"] != "success":
            raise FileNotFoundError(load_result["message"])

        input_bytes = load_result["raw_bytes"]
        input_mime_type = load_result["mime_type"]
        metadata = load_result.get("metadata", {})
        metadata["filename"] = filename_base
        metadata["version"] = load_result.get("version")

        df: pd.DataFrame
        if input_mime_type == "text/csv":
            df = pd.read_csv(io.BytesIO(input_bytes))
        elif input_mime_type == SQLITE_DB_MIME_TYPE:
            temp_db_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
            db_path = temp_db_file.name
            with open(db_path, "wb") as f:
                f.write(input_bytes)

            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                if not tables:
                    raise ValueError("SQLite artifact contains no tables.")
                table_name_to_query = tables[0][0]
                df = pd.read_sql_query(f"SELECT * FROM {table_name_to_query}", conn)
        else:
            raise ValueError(
                f"Unsupported input MIME type for SQL query: {input_mime_type}"
            )

        output_filename_base_to_use = output_filename or f"sql_result_{filename_base}"

        return await _query_dataframe_with_sql(
            df=df,
            sql_query=sql_query,
            tool_context=tool_context,
            output_filename_base=output_filename_base_to_use,
            output_format=output_format,
            result_description=result_description,
            source_metadata=metadata,
        )

    except FileNotFoundError as e:
        log.warning("%s File not found error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except ValueError as e:
        log.warning("%s Value error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        log.exception(
            "%s Unexpected error in query_data_with_sql: %s", log_identifier, e
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        if temp_db_file:
            try:
                os.remove(temp_db_file.name)
                log.debug(
                    "%s Removed temporary DB file: %s",
                    log_identifier,
                    temp_db_file.name,
                )
            except OSError as e:
                log.error(
                    "%s Failed to remove temporary DB file %s: %s",
                    log_identifier,
                    temp_db_file.name,
                    e,
                )


async def create_sqlite_db(
    input_filename: str,
    output_db_filename: str,
    table_name: str = DEFAULT_SQLITE_TABLE_NAME,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Creates an SQLite database artifact from a CSV or JSON artifact.
    Assumes 'pandas' is installed.

    Args:
        input_filename: The filename (and optional :version) of the input CSV or JSON artifact.
        output_db_filename: The desired filename for the output SQLite database artifact.
        table_name: The name of the table to create in the SQLite database. Default 'data'.
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary with status and output artifact details.
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext is missing."}
    if not PANDAS_AVAILABLE:
        return {
            "status": "error",
            "message": "The pandas library is required for creating SQLite DBs but it is not installed.",
        }

    log_identifier = f"[DataTool:create_sqlite_db:{input_filename}]"
    log.info(
        "%s Processing request to create DB '%s' from '%s'.",
        log_identifier,
        output_db_filename,
        input_filename,
    )

    conn = None
    temp_db_file = None

    try:
        app_name = tool_context._invocation_context.app_name
        user_id = tool_context._invocation_context.user_id
        session_id = get_original_session_id(tool_context._invocation_context)

        parts = input_filename.split(":", 1)
        filename_base = parts[0]
        version_str = parts[1] if len(parts) > 1 else None
        version = int(version_str) if version_str else None

        metadata_filename = f"{filename_base}{METADATA_SUFFIX}"
        if version is None:
            artifact_service = tool_context._invocation_context.artifact_service
            versions = await artifact_service.list_versions(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base,
            )
            if not versions:
                raise FileNotFoundError(f"Artifact '{filename_base}' not found.")
            version = max(versions)
            log.debug("%s Using latest version: %d", log_identifier, version)

        try:
            artifact_service = tool_context._invocation_context.artifact_service
            metadata_part = await artifact_service.load_artifact(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=metadata_filename,
                version=version,
            )
            if not metadata_part or not metadata_part.inline_data:
                raise FileNotFoundError(
                    f"Metadata for artifact '{filename_base}' v{version} not found or empty."
                )
            metadata = json.loads(metadata_part.inline_data.data.decode("utf-8"))
            input_mime_type = metadata.get("mime_type", "").lower()
        except (
            FileNotFoundError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as meta_err:
            log.warning(
                "%s Could not load or parse metadata for '%s' v%d: %s. Attempting direct load.",
                log_identifier,
                filename_base,
                version,
                meta_err,
            )
            input_part = await tool_context.load_artifact(
                filename=filename_base, version=version
            )
            if not input_part:
                raise FileNotFoundError(
                    f"Artifact '{filename_base}' v{version} not found."
                )
            input_mime_type = (input_part.inline_data.mime_type or "").lower()

        input_part = await tool_context.load_artifact(
            filename=filename_base, version=version
        )
        if not input_part or not input_part.inline_data:
            raise ValueError("Failed to load input artifact content.")
        input_bytes = input_part.inline_data.data

        temp_db_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        db_path = temp_db_file.name
        conn = sqlite3.connect(db_path)
        log.debug("%s Created temporary DB file: %s", log_identifier, db_path)

        df: pd.DataFrame
        if input_mime_type == "text/csv":
            log.debug("%s Parsing input as CSV.", log_identifier)
            try:
                csv_io = io.BytesIO(input_bytes)
                df = pd.read_csv(csv_io)
            except Exception as parse_err:
                raise ValueError(
                    f"Failed to parse CSV input: {parse_err}"
                ) from parse_err
        elif input_mime_type == "application/json":
            log.debug("%s Parsing input as JSON.", log_identifier)
            try:
                json_str = input_bytes.decode("utf-8")
                json_data = json.loads(json_str)
                df = pd.json_normalize(json_data)
            except (UnicodeDecodeError, json.JSONDecodeError) as parse_err:
                raise ValueError(
                    f"Failed to parse JSON input: {parse_err}"
                ) from parse_err
            except Exception as norm_err:
                raise ValueError(
                    f"Failed to normalize JSON data: {norm_err}"
                ) from norm_err
        else:
            raise ValueError(
                f"Unsupported input MIME type for DB creation: {input_mime_type}. Expected 'text/csv' or 'application/json'."
            )

        try:
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            log.debug("%s Loaded data into table '%s'.", log_identifier, table_name)
        except Exception as load_err:
            raise ValueError(
                f"Failed to load data into SQLite table '{table_name}': {load_err}"
            ) from load_err
        finally:
            if conn:
                conn.close()
                conn = None

        with open(db_path, "rb") as f:
            db_bytes = f.read()

        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")
        host_component = getattr(inv_context.agent, "host_component", None)
        schema_max_keys = (
            host_component.get_config("schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS)
            if host_component
            else DEFAULT_SCHEMA_MAX_KEYS
        )

        final_output_filename = ensure_correct_extension(output_db_filename, "sqlite")

        save_metadata_dict = {
            "description": f"SQLite database created from {input_filename}",
            "source_artifact": input_filename,
            "source_artifact_version": version,
            "table_name": table_name,
        }
        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=final_output_filename,
            content_bytes=db_bytes,
            mime_type=SQLITE_DB_MIME_TYPE,
            metadata_dict=save_metadata_dict,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=schema_max_keys,
        )
        if save_result["status"] == "error":
            raise IOError(
                f"Failed to save SQLite DB artifact: {save_result.get('message', 'Unknown error')}"
            )

        log.info(
            "%s Successfully created SQLite DB artifact '%s' v%d.",
            log_identifier,
            final_output_filename,
            save_result["data_version"],
        )
        return {
            "status": "success",
            "message": f"SQLite database '{final_output_filename}' v{save_result['data_version']} created successfully from '{input_filename}'.",
            "output_filename": final_output_filename,
            "output_version": save_result["data_version"],
        }

    except FileNotFoundError as e:
        log.warning("%s File not found error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except ValueError as e:
        log.warning("%s Value error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        log.exception("%s Unexpected error in create_sqlite_db: %s", log_identifier, e)
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        if conn:
            conn.close()
            log.debug("%s Closed SQLite connection (in finally).", log_identifier)
        if temp_db_file:
            try:
                os.remove(temp_db_file.name)
                log.debug(
                    "%s Removed temporary DB file: %s",
                    log_identifier,
                    temp_db_file.name,
                )
            except OSError as e:
                log.error(
                    "%s Failed to remove temporary DB file %s: %s",
                    log_identifier,
                    temp_db_file.name,
                    e,
                )


async def transform_data_with_jmespath(
    input_filename: str,
    jmespath_expression: str,
    output_filename: Optional[str] = None,
    result_description: Optional[str] = None,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Applies a JMESPath expression to a JSON, YAML, or CSV artifact.

    CSV files are converted to a list of dictionaries before applying the JMESPath filter.
    The result is saved as a new JSON artifact and a preview is returned.
    Assumes 'jmespath', 'PyYAML', and 'pandas' libraries are installed.

    Args:
        input_filename: The filename (and optional :version) of the input JSON, YAML, or CSV artifact.
        jmespath_expression: The JMESPath expression string.
        output_filename: Optional. The desired filename for the output JSON artifact.
        result_description: Optional. A description for the result artifact's metadata.
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary with status, output artifact details, and a preview of the result.
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext is missing."}
    if not JMESPATH_AVAILABLE:
        return {
            "status": "error",
            "message": "The jmespath library is required for this tool but it is not installed.",
        }

    log_identifier = f"[DataTool:transform_data_with_jmespath:{input_filename}]"
    log.info(
        "%s Processing request. JMESPath Expression: '%s'",
        log_identifier,
        jmespath_expression[:100] + "...",
    )

    config = _get_data_tools_config(tool_context)
    if output_filename:
        final_output_filename = ensure_correct_extension(output_filename, "json")
    else:
        final_output_filename = f"jmespath_result_{uuid.uuid4().hex[:8]}.json"
    output_mime_type = "application/json"

    try:
        app_name = tool_context._invocation_context.app_name
        user_id = tool_context._invocation_context.user_id
        session_id = get_original_session_id(tool_context._invocation_context)

        parts = input_filename.split(":", 1)
        filename_base = parts[0]
        version_str = parts[1] if len(parts) > 1 else None
        version = int(version_str) if version_str else None

        metadata_filename = f"{filename_base}{METADATA_SUFFIX}"
        if version is None:
            artifact_service = tool_context._invocation_context.artifact_service
            versions = await artifact_service.list_versions(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base,
            )
            if not versions:
                raise FileNotFoundError(f"Artifact '{filename_base}' not found.")
            version = max(versions)
            log.debug("%s Using latest version: %d", log_identifier, version)

        try:
            artifact_service = tool_context._invocation_context.artifact_service
            metadata_part = await artifact_service.load_artifact(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=metadata_filename,
                version=version,
            )
            if not metadata_part or not metadata_part.inline_data:
                raise FileNotFoundError(
                    f"Metadata for artifact '{filename_base}' v{version} not found or empty."
                )
            metadata = json.loads(metadata_part.inline_data.data.decode("utf-8"))
            input_mime_type = metadata.get("mime_type", "").lower()
        except (
            FileNotFoundError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as meta_err:
            log.warning(
                "%s Could not load or parse metadata for '%s' v%d: %s. Attempting direct load.",
                log_identifier,
                filename_base,
                version,
                meta_err,
            )
            input_part = await tool_context.load_artifact(
                filename=filename_base, version=version
            )
            if not input_part:
                raise FileNotFoundError(
                    f"Artifact '{filename_base}' v{version} not found."
                )
            input_mime_type = (input_part.inline_data.mime_type or "").lower()

        input_part = await tool_context.load_artifact(
            filename=filename_base, version=version
        )
        if not input_part or not input_part.inline_data:
            raise ValueError("Failed to load input artifact content.")
        input_bytes = input_part.inline_data.data

        parsed_data: Any
        if input_mime_type == "application/json":
            log.debug("%s Parsing input as JSON.", log_identifier)
            try:
                json_str = input_bytes.decode("utf-8")
                parsed_data = json.loads(json_str)
            except (UnicodeDecodeError, json.JSONDecodeError) as parse_err:
                raise ValueError(
                    f"Failed to parse JSON input: {parse_err}"
                ) from parse_err
        elif input_mime_type in [
            "application/yaml",
            "text/yaml",
            "application/x-yaml",
            "text/x-yaml",
        ]:
            log.debug("%s Parsing input as YAML.", log_identifier)
            try:
                if not PYYAML_AVAILABLE:
                    raise ImportError(
                        "PyYAML library is required for YAML input but it is not installed."
                    )
                yaml_str = input_bytes.decode("utf-8")
                parsed_data = yaml.safe_load(yaml_str)
            except (UnicodeDecodeError, yaml.YAMLError) as parse_err:
                raise ValueError(
                    f"Failed to parse YAML input: {parse_err}"
                ) from parse_err
        elif input_mime_type == "text/csv":
            if not PANDAS_AVAILABLE:
                raise ImportError(
                    "The pandas library is required for CSV input to JMESPath transform but it is not installed."
                )
            log.debug("%s Parsing input as CSV.", log_identifier)
            try:
                csv_io = io.BytesIO(input_bytes)
                df = pd.read_csv(csv_io)
                parsed_data = df.to_dict(orient="records")
            except Exception as parse_err:
                raise ValueError(
                    f"Failed to parse CSV input: {parse_err}"
                ) from parse_err
        else:
            raise ValueError(
                f"Unsupported input MIME type for JMESPath transform: {input_mime_type}. Expected JSON, YAML, or CSV."
            )

        log.debug("%s Executing JMESPath expression...", log_identifier)
        try:
            jmespath_result = jmespath.search(jmespath_expression, parsed_data)
            log.info("%s JMESPath expression executed successfully.", log_identifier)
        except Exception as jmespath_err:
            raise ValueError(
                f"JMESPath execution failed: {jmespath_err}"
            ) from jmespath_err

        try:
            result_bytes = json.dumps(jmespath_result, indent=2).encode("utf-8")
        except TypeError as json_err:
            raise ValueError(
                f"Failed to serialize JMESPath result to JSON: {json_err}"
            ) from json_err
        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")
        host_component = getattr(inv_context.agent, "host_component", None)
        schema_max_keys = (
            host_component.get_config("schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS)
            if host_component
            else DEFAULT_SCHEMA_MAX_KEYS
        )
        base_description = (
            result_description or f"Result of JMESPath transform on {input_filename}"
        )
        final_description = (
            f"{base_description}. JMESPath Expression used: `{jmespath_expression}`"
        )

        save_metadata_dict = {
            "description": final_description,
            "source_artifact": input_filename,
            "source_artifact_version": version,
            "source_jmespath_expression": jmespath_expression,
        }
        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=final_output_filename,
            content_bytes=result_bytes,
            mime_type=output_mime_type,
            metadata_dict=save_metadata_dict,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=schema_max_keys,
        )
        if save_result["status"] == "error":
            raise IOError(
                f"Failed to save JMESPath result artifact: {save_result.get('message', 'Unknown error')}"
            )

        preview_data, truncated = _truncate_result(jmespath_result, config)
        preview_message = f"JMESPath expression executed successfully. Full result saved as '{final_output_filename}' v{save_result['data_version']}."
        if truncated:
            if isinstance(preview_data, list):
                preview_message += f" Preview shows first {len(preview_data)} items."
            else:
                preview_message += f" Preview may be truncated."

        return {
            "status": "success",
            "message": preview_message,
            "output_filename": final_output_filename,
            "output_version": save_result["data_version"],
            "result_preview": preview_data,
            "result_truncated": truncated,
        }

    except FileNotFoundError as e:
        log.warning("%s File not found error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except ValueError as e:
        log.warning("%s Value error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except ImportError as e:
        log.warning("%s Missing library error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        log.exception(
            "%s Unexpected error in transform_data_with_jmespath: %s", log_identifier, e
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}

query_data_with_sql_tool_def = BuiltinTool(
    name="query_data_with_sql",
    implementation=query_data_with_sql,
    description="Executes a SQL query against a CSV or SQLite artifact. The result is saved as a new artifact with a specified or generated name. Use standard SQL syntax. For CSV inputs, the data is loaded into a table named 'data'.",
    category="data_analysis",
    required_scopes=["tool:data:sql"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "input_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The filename (and optional :version) of the input CSV or SQLite artifact.",
            ),
            "sql_query": adk_types.Schema(
                type=adk_types.Type.STRING, description="The SQL query to execute."
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional. A base name for the output artifact. The correct extension (.csv or .json) will be added automatically. If not provided, a name is generated.",
                nullable=True,
            ),
            "result_description": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional description for the result artifact's metadata.",
                nullable=True,
            ),
            "output_format": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The desired format for the output artifact ('csv' or 'json').",
                enum=["csv", "json"],
                nullable=True,
            ),
        },
        required=["input_filename", "sql_query"],
    ),
    examples=[],
)

create_sqlite_db_tool_def = BuiltinTool(
    name="create_sqlite_db",
    implementation=create_sqlite_db,
    description="Converts a CSV or JSON artifact into an SQLite database artifact. Input filename can include version. Specify the desired output DB filename and optionally the table name within the DB. Use this for large datasets you plan to query multiple times with `query_data_with_sql`.",
    category="data_analysis",
    required_scopes=["tool:data:create_db", "tool:artifact:create"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "input_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The filename (and optional :version) of the input CSV or JSON artifact.",
            ),
            "output_db_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The desired filename for the output SQLite database artifact.",
            ),
            "table_name": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The name of the table to create in the SQLite database. Defaults to 'data'.",
                nullable=True,
            ),
        },
        required=["input_filename", "output_db_filename"],
    ),
    examples=[],
)

transform_data_with_jmespath_tool_def = BuiltinTool(
    name="transform_data_with_jmespath",
    implementation=transform_data_with_jmespath,
    description=(
        "A powerful, sandboxed tool that applies a JMESPath expression to a JSON, YAML, or CSV artifact to query, filter, reshape, and extract data. The result is always a new JSON artifact.\n"
        "This tool is sandboxed and CANNOT access environment variables or the local filesystem, making it safe to use.\n\n"
        "--- Data Format Handling ---\n"
        "- **JSON/YAML**: The data is parsed directly. You MUST know the data structure.\n"
        "- **CSV**: The data is converted into a JSON array of objects, where each object represents a row and keys are taken from the header row.\n\n"
        "--- Key JMESPath Syntax Concepts ---\n"
        "1.  **Accessing Keys**: Use dot notation for nested objects. Example: `store.bicycle.color`\n"
        "2.  **Accessing Array Elements**: Use `[index]` for a specific element (e.g., `store.book[0]`) or `[]` to iterate over all elements. Example: `store.book[].title` gets all book titles.\n"
        "3.  **Filtering Arrays**: Use `[?expression]` to filter. The expression is evaluated against each element. Example: `store.book[?price < 10]` finds books with a price less than 10.\n"
        "4.  **String Comparisons**: When filtering by a string value, enclose the string in backticks `` ` ``. Example: `store.book[?author == \\`Nigel Rees\\`]`.\n"
        "5.  **Reshaping to a New Object**: Use multiselect hash `{}` to create new objects. Example: `store.book[].{bookTitle: title, writer: author}` creates a new list of objects with `bookTitle` and `writer` keys.\n"
        "6.  **Functions**: Use functions like `length()` to get the size of an array or object. Example: `length(store.book)`.\n\n"
        '**CRITICAL:** Your expression MUST account for the top-level structure of the JSON. If data is wrapped in a `{"users": [...]}` object, your expression must start with `users`.'
    ),
    category="data_analysis",
    required_scopes=["tool:data:jmespath"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "input_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The filename of the input JSON, YAML, or CSV artifact to be transformed.",
            ),
            "jmespath_expression": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The JMESPath expression string to apply. Example: `users[?active].name`",
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional. The desired filename for the output JSON artifact. If not provided, a unique name is generated.",
                nullable=True,
            ),
            "result_description": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional. A description for the result artifact's metadata.",
                nullable=True,
            ),
        },
        required=["input_filename", "jmespath_expression"],
    ),
    examples=[
        {
            "user_query": "From the `users.json` file, can you get me the names of all the active users?",
            "thought": "The user wants to filter the `users.json` artifact. First, I need to access the top-level `users` array. Then, I need to filter this array for elements where the `active` key is true using `[?active]`. Finally, I need to project the `name` field from the filtered results. The final JMESPath expression should be `users[?active].name`.",
            "tool_code": 'transform_data_with_jmespath(input_filename="users.json", jmespath_expression="users[?active].name", output_filename="active_users.json", result_description="A list of names of active users.")',
        },
        {
            "user_query": "Please process `books.json` and create a new file containing a simplified list, showing just the title and author of each book, but rename the keys to 'book_title' and 'written_by'.",
            "thought": "The user wants to reshape the data from `books.json`. I need to iterate over the `store.book` array. For each book, I will create a new object using the multiselect hash syntax `{}`. I'll map the original `title` key to a new `book_title` key and the `author` key to `written_by`. The expression will be `store.book[].{book_title: title, written_by: author}`.",
            "tool_code": 'transform_data_with_jmespath(input_filename="books.json", jmespath_expression="store.book[].{book_title: title, written_by: author}", output_filename="simplified_book_list.json")',
        },
        {
            "user_query": "How many books are in the `books.json` artifact?",
            "thought": "The user wants to count the number of elements in the `store.book` array within `books.json`. I can use the `length()` function in JMESPath for this. The expression is simply `length(store.book)`.",
            "tool_code": 'transform_data_with_jmespath(input_filename="books.json", jmespath_expression="length(store.book)", output_filename="book_count.json")',
        },
        {
            "user_query": "I have a `sales_data.csv` file with 'Region', 'Product', and 'UnitsSold' columns. Can you extract all sales from the 'North' region where more than 50 units were sold?",
            "thought": "The user has a CSV file. I know the tool will convert this to an array of objects. I need to filter this array. The first condition is that the `Region` key must equal 'North'. I must use backticks for the string literal: `Region  \\\\`North\\\\``. The second condition is `UnitsSold > 50`. I can combine these with `&&`. The full expression is `[?Region  \\`North\\` && UnitsSold > \\`50\\`]`.",
            "tool_code": 'transform_data_with_jmespath(input_filename="sales_data.csv", jmespath_expression="[?Region == \\`North\\` && UnitsSold > `50`]", output_filename="north_region_top_sales.json")',
        },
    ],
)

tool_registry.register(query_data_with_sql_tool_def)
tool_registry.register(create_sqlite_db_tool_def)
tool_registry.register(transform_data_with_jmespath_tool_def)
