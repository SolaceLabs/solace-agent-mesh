"""
ADK Tool for the MongoDB Agent Plugin.
"""

import json
import yaml
import csv
import io
from typing import Any, Dict, Optional, Literal
import datetime

from google.adk.tools import ToolContext

try:
    from solace_ai_connector.common.log import log
except ImportError:
    import logging

    log = logging.getLogger(__name__)

from .services.database_service import MongoDatabaseService
from solace_agent_mesh.agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
)
from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id

MAX_QUERY_LEN_IN_DESCRIPTION = 1000


async def mongo_query(
    pipeline_str: str,
    response_format: Literal["yaml", "json", "csv", "markdown"] = "json",
    result_description: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes a MongoDB aggregation pipeline and returns the results.
    This tool is intended to be called by the LLM after it has generated the pipeline.

    Args:
        pipeline_str (str): The aggregation pipeline as a JSON string.
        response_format (Literal["yaml", "json", "csv", "markdown"]): The format in which to return the results.
        result_description (Optional[str]): A description of the results to be saved as metadata.
    """
    if not tool_context or not tool_config:
        return {"status": "error", "error_message": "Tool context or config missing."}

    log_identifier = f"[{tool_context._invocation_context.agent.name}:mongo_query]"

    collection = tool_config.get("collection")
    if not collection:
        return {
            "status": "error",
            "error_message": "Missing 'collection' in tool_config.",
        }

    log.info("%s Executing aggregation on collection '%s'.", log_identifier, collection)

    try:
        pipeline = json.loads(pipeline_str)
        log.debug(f"{log_identifier} Pipeline: {pipeline}")
    except json.JSONDecodeError as e:
        log.error(f"{log_identifier} Invalid JSON in pipeline_str: {e}")
        return {
            "status": "error",
            "error_message": f"Invalid pipeline format. Expected a valid JSON string. Error: {e}",
        }

    host_component = getattr(
        tool_context._invocation_context.agent, "host_component", None
    )
    if not host_component:
        return {"status": "error", "error_message": "Host component not found."}

    db_handler: Optional[MongoDatabaseService] = (
        host_component.get_agent_specific_state("db_handler")
    )
    if not db_handler:
        return {"status": "error", "error_message": "Database handler not initialized."}

    max_inline_results: int = host_component.get_agent_specific_state(
        "max_inline_results", 10
    )

    try:
        results = db_handler.execute_query(collection, pipeline)
        log.info(
            "%s Query executed successfully. Rows returned: %d",
            log_identifier,
            len(results),
        )

        if response_format == "yaml":
            content = yaml.dump(results, allow_unicode=True)
            file_extension = "yaml"
        elif response_format == "markdown":
            if not results:
                content = "No results found."
            else:
                headers = results[0].keys()
                content = "| " + " | ".join(headers) + " |\n"
                content += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                for row in results:
                    content += (
                        "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |\n"
                    )
            file_extension = "md"
        elif response_format == "json":
            content = json.dumps(results, indent=2, default=str)
            file_extension = "json"
        else:
            if not results:
                content = ""
            else:
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
                content = output.getvalue()
            file_extension = "csv"

        content_bytes = content.encode("utf-8")

        inv_context = tool_context._invocation_context
        artifact_filename = (
            f"mongo_query_result_{tool_context.function_call_id[-8:]}.{file_extension}"
        )

        description = result_description or f"Results of MongoDB aggregation. "
        description += f"Collection: {collection}, Pipeline: {pipeline_str[:MAX_QUERY_LEN_IN_DESCRIPTION]}{'...' if len(pipeline_str) > MAX_QUERY_LEN_IN_DESCRIPTION else pipeline_str}"
        save_metadata = {
            "description": description,
            "row_count": len(results),
        }

        save_result = await save_artifact_with_metadata(
            artifact_service=inv_context.artifact_service,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=artifact_filename,
            content_bytes=content_bytes,
            mime_type=f"text/{file_extension}",
            metadata_dict=save_metadata,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            schema_max_keys=DEFAULT_SCHEMA_MAX_KEYS,
            tool_context=tool_context,
        )

        if save_result["status"] == "error":
            raise IOError(
                f"Failed to save query result artifact: {save_result.get('message', 'Unknown error')}"
            )

        version = save_result["data_version"]
        message_to_llm = f"Aggregation executed. Results saved to artifact '{artifact_filename}' (version {version})."

        inline_content = ""
        if len(results) <= max_inline_results:
            inline_content = content
        else:
            message_to_llm += f" A preview is not available as the number of results ({len(results)}) exceeds the inline limit ({max_inline_results})."

        return {
            "status": "success",
            "message_to_llm": message_to_llm,
            "artifact_filename": artifact_filename,
            "artifact_version": version,
            "row_count": len(results),
            "content": inline_content,
        }

    except Exception as e:
        log.exception("%s Error executing aggregation: %s", log_identifier, e)
        return {"status": "error", "error_message": str(e)}
