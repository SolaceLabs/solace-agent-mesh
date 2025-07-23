"""
ADK Tools for the SQL Database Agent Plugin.
"""

import json
import yaml
import csv
import io
import asyncio
import datetime
from typing import Any, Dict, List, Optional, Literal

from google.adk.tools import ToolContext
from google.genai import types as adk_types

try:
    from solace_ai_connector.common.log import log
except ImportError:
    import logging

    log = logging.getLogger(__name__)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .services.database_service import DatabaseService

from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id
from solace_agent_mesh.agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
    ensure_correct_extension,
)


async def execute_sql_query(
    query: str,
    output_filename: Optional[str] = None,
    result_description: Optional[str] = None,
    response_format: Literal["yaml", "json", "csv"] = "csv",
    inline_result: bool = True,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes a SQL query against the configured database, formats the results,
    and either returns them inline or saves them as an artifact.

    Args:
        query: The SQL query string to execute. May contain embeds.
        output_filename: Optional. A base name for the output artifact. The correct extension will be added.
        result_description: Optional description of the results of this query (e.g. "Top orders for company X").
                 This is stored in the result file's metadata.
        response_format: The desired format for the query results ('yaml', 'json', 'csv').
                         Defaults to 'csv'. May contain embeds.
        inline_result: If True, attempts to return results inline if they are small enough.
                       Note that the result will always be saved as an artifact regardless of this setting
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary containing the status of the operation, query results (or artifact details),
        and any relevant messages.
    """
    if not tool_context:
        return {
            "status": "error",
            "error_message": "ToolContext is missing, cannot execute SQL query.",
            "sql_query_attempted": query,
        }

    log_identifier = f"[SQLExecuteTool:{tool_context._invocation_context.agent.name}]"
    log.info(
        "%s Executing SQL query. Format: %s, Inline: %s",
        log_identifier,
        response_format,
        inline_result,
    )
    log.debug("%s SQL Query: %s", log_identifier, query)

    host_component = getattr(
        tool_context._invocation_context.agent, "host_component", None
    )
    if not host_component:
        return {
            "status": "error",
            "error_message": "Host component not found, cannot access database handler.",
            "sql_query_attempted": query,
        }

    db_handler_obj = host_component.get_agent_specific_state("db_handler")
    db_handler: Optional["DatabaseService"] = db_handler_obj
    response_guidelines: str = host_component.get_agent_specific_state(
        "db_response_guidelines", ""
    )
    max_inline_result_size_bytes: int = host_component.get_agent_specific_state(
        "max_inline_result_size_bytes", 2048
    )

    if not db_handler:
        return {
            "status": "error",
            "error_message": "Database handler not initialized. Cannot execute query.",
            "sql_query_attempted": query,
        }

    valid_formats = ["yaml", "json", "csv"]
    if response_format.lower() not in valid_formats:
        return {
            "status": "error",
            "error_message": f"Invalid response_format '{response_format}'. Must be one of {valid_formats}.",
            "sql_query_attempted": query,
        }

    try:
        results: List[Dict[str, Any]] = await asyncio.to_thread(
            db_handler.execute_query, query
        )
        log.info(
            "%s SQL query executed successfully. Number of rows returned: %d",
            log_identifier,
            len(results),
        )

        formatted_content_str: str
        output_mime_type: str
        file_extension: str

        if response_format == "yaml":
            formatted_content_str = yaml.dump(
                results, allow_unicode=True, sort_keys=False
            )
            output_mime_type = "application/yaml"
            file_extension = "yaml"
        elif response_format == "json":
            formatted_content_str = json.dumps(results, indent=2, default=str)
            output_mime_type = "application/json"
            file_extension = "json"
        else:
            if not results:
                formatted_content_str = "No results found."
            else:
                output = io.StringIO()
                fieldnames = list(results[0].keys()) if results else []
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
                formatted_content_str = output.getvalue()
            output_mime_type = "text/csv"
            file_extension = "csv"

        content_bytes = formatted_content_str.encode("utf-8")

        inline_truncated_warning = ""
        if inline_result and len(content_bytes) > max_inline_result_size_bytes:
            formatted_content_str = (
                formatted_content_str[: max_inline_result_size_bytes - 3] + "..."
            )
            inline_truncated_warning = (
                f"\n\n**Warning:** Result size ({len(content_bytes)} bytes) exceeds "
                f"inline limit ({max_inline_result_size_bytes} bytes). "
                "Returning truncated result inline. Fetch artifact for full results.\n\n"
            )

        # Determine base filename
        base_filename = (
            output_filename or f"sql_query_result_{tool_context.function_call_id[-8:]}"
        )
        # Ensure correct extension
        artifact_filename = ensure_correct_extension(base_filename, file_extension)

        log.info(
            "%s Result size (%d bytes) or inline_result=False. Saving as artifact: %s",
            log_identifier,
            len(content_bytes),
            artifact_filename,
        )

        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError(
                "ArtifactService is not available in the context for saving SQL result."
            )

        MAX_QUERY_LEN_IN_DESCRIPTION = 1000
        result_description = f"{result_description}\n" if result_description else ""
        save_metadata = {
            "description": f"{result_description}Results of SQL query: {query[:MAX_QUERY_LEN_IN_DESCRIPTION]}{'...' if len(query) > MAX_QUERY_LEN_IN_DESCRIPTION else ''}",
            "response_format": response_format,
            "row_count": len(results),
        }
        schema_max_keys = host_component.get_config(
            "schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS
        )

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=artifact_filename,
            content_bytes=content_bytes,
            mime_type=output_mime_type,
            metadata_dict=save_metadata,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            schema_max_keys=schema_max_keys,
            tool_context=tool_context,
        )

        if save_result["status"] == "error":
            raise IOError(
                f"Failed to save query result artifact: {save_result.get('message', 'Unknown error')}"
            )

        version = save_result["data_version"]
        message_to_llm = f"SQL query executed. Results saved to artifact '{artifact_filename}' (version {version})."
        if response_guidelines:
            message_to_llm += f"\n\n### RESPONSE GUIDELINES - FOLLOW THESE EXACTLY ###\n{response_guidelines}\n### END GUIDELINES ###"

        if inline_truncated_warning:
            message_to_llm += "\n" + inline_truncated_warning

        return {
            "status": "success_artifact_saved",
            "message_to_llm": message_to_llm,
            "artifact_filename": artifact_filename,
            "artifact_version": version,
            "row_count": len(results),
            "content": formatted_content_str,
        }

    except Exception as e:
        log.exception(
            "%s Error executing SQL query or processing results: %s", log_identifier, e
        )
        error_message = f"Failed to execute SQL query: {type(e).__name__} - {str(e)}"
        if response_guidelines:
            error_message += f"\n\nGuidelines: {response_guidelines}"
        return {
            "status": "error",
            "error_message": error_message,
            "sql_query_attempted": query,
        }
