"""
Intelligent MCP Callback Functions

This module contains the refactored MCP callback functions that use intelligent
content processing to save MCP tool responses as appropriately typed artifacts.
"""

import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, TYPE_CHECKING, List, Optional
from enum import Enum
from pydantic import BaseModel

from google.adk.tools import ToolContext, BaseTool

from .mcp_content_processor import MCPContentProcessor, MCPContentProcessorConfig
from ...agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
)
from ...agent.utils.context_helpers import get_original_session_id

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ...agent.sac.component import SamAgentComponent


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

    Attributes:
        status: The overall status of the save operation.
        message: A human-readable summary of the outcome.
        artifacts_saved: A list of successfully created "intelligent" artifacts.
        fallback_artifact: An optional artifact representing the raw JSON response,
                           created only if intelligent processing failed.
    """

    status: McpSaveStatus
    message: str
    artifacts_saved: List[SavedArtifactInfo] = []
    fallback_artifact: Optional[SavedArtifactInfo] = None


async def save_mcp_response_as_artifact_intelligent(
    tool: BaseTool,
    tool_context: ToolContext,
    host_component: "SamAgentComponent",
    mcp_response_dict: Dict[str, Any],
    original_tool_args: Dict[str, Any],
) -> McpSaveResult:
    """
    Intelligently processes and saves MCP tool response content as typed artifacts.

    This function uses intelligent content processing to:
    - Detect and parse different content types (text, image, audio, resource)
    - Create appropriately typed artifacts with proper MIME types
    - Generate enhanced metadata based on content analysis
    - Fall back to raw JSON saving if intelligent processing fails

    Args:
        tool: The MCPTool instance that generated the response.
        tool_context: The ADK ToolContext.
        host_component: The A2A_ADK_HostComponent instance for accessing config and services.
        mcp_response_dict: The raw MCP tool response dictionary.
        original_tool_args: The original arguments passed to the MCP tool.

    Returns:
        An McpSaveResult object containing the structured result of the operation,
        including status, a list of successfully saved artifacts, and any
        fallback artifact.
    """
    log_identifier = f"[IntelligentMCPCallback:{tool.name}]"
    log.debug("%s Starting intelligent MCP response artifact saving...", log_identifier)

    processor_config_dict = host_component.get_config("mcp_intelligent_processing", {})
    processor_config = MCPContentProcessorConfig.from_dict(processor_config_dict)

    saved_artifacts: List[SavedArtifactInfo] = []
    failed_artifacts: List[Dict[str, Any]] = []
    fallback_artifact: Optional[SavedArtifactInfo] = None
    overall_status = McpSaveStatus.SUCCESS

    try:
        if not processor_config.enable_intelligent_processing:
            log.info(
                "%s Intelligent processing disabled, using raw JSON fallback.",
                log_identifier,
            )
            fallback_dict = await _save_raw_mcp_response_fallback(
                tool,
                tool_context,
                host_component,
                mcp_response_dict,
                original_tool_args,
            )
            if fallback_dict.get("status") in ["success", "partial_success"]:
                fallback_artifact = SavedArtifactInfo(**fallback_dict)
                status = McpSaveStatus.SUCCESS
            else:
                status = McpSaveStatus.ERROR
            return McpSaveResult(
                status=status,
                message="Intelligent processing disabled; saved raw JSON as fallback.",
                fallback_artifact=fallback_artifact,
            )

        processor = MCPContentProcessor(tool.name, original_tool_args)
        content_items = processor.process_mcp_response(mcp_response_dict)

        if not content_items:
            log.warning(
                "%s No content items found, falling back to raw JSON.", log_identifier
            )
            fallback_dict = await _save_raw_mcp_response_fallback(
                tool,
                tool_context,
                host_component,
                mcp_response_dict,
                original_tool_args,
            )
            if fallback_dict.get("status") in ["success", "partial_success"]:
                fallback_artifact = SavedArtifactInfo(**fallback_dict)
            return McpSaveResult(
                status=McpSaveStatus.PARTIAL_SUCCESS,
                message="No content items found in MCP response; saved raw JSON as fallback.",
                fallback_artifact=fallback_artifact,
            )

        log.info(
            "%s Processing %d content items intelligently.",
            log_identifier,
            len(content_items),
        )

        for item in content_items:
            try:
                if hasattr(item, "uri"):
                    item.uri = str(item.uri)
                result_dict = await _save_content_item_as_artifact(
                    item, tool_context, host_component
                )
                if result_dict.get("status") in ["success", "partial_success"]:
                    saved_artifacts.append(SavedArtifactInfo(**result_dict))
                else:
                    log.warning(
                        "%s Failed to save content item: %s",
                        log_identifier,
                        result_dict.get("message", "Unknown error"),
                    )
                    overall_status = McpSaveStatus.PARTIAL_SUCCESS
                    failed_artifacts.append(result_dict)
            except Exception as e:
                if not processor_config.fallback_to_raw_on_error:
                    raise
                log.exception("%s Error saving content item: %s", log_identifier, e)
                overall_status = McpSaveStatus.PARTIAL_SUCCESS
                failed_artifacts.append({"status": "error", "message": str(e)})

        if not saved_artifacts:
            if failed_artifacts:
                first_error_msg = failed_artifacts[0].get("message", "Unknown error")
                log.warning(
                    "%s No items saved successfully. First error: %s",
                    log_identifier,
                    first_error_msg,
                )
                return McpSaveResult(
                    status=McpSaveStatus.ERROR,
                    message=f"Content processing failed. First error: {first_error_msg}",
                )

            fallback_dict = await _save_raw_mcp_response_fallback(
                tool,
                tool_context,
                host_component,
                mcp_response_dict,
                original_tool_args,
            )
            if fallback_dict.get("status") in ["success", "partial_success"]:
                fallback_artifact = SavedArtifactInfo(**fallback_dict)
            return McpSaveResult(
                status=McpSaveStatus.PARTIAL_SUCCESS,
                message="Content processing failed for all items; saved raw JSON as fallback.",
                fallback_artifact=fallback_artifact,
            )

        if processor_config_dict.get("save_raw_alongside_intelligent", False):
            try:
                fallback_dict = await _save_raw_mcp_response_fallback(
                    tool,
                    tool_context,
                    host_component,
                    mcp_response_dict,
                    original_tool_args,
                )
                if fallback_dict.get("status") in ["success", "partial_success"]:
                    fallback_artifact = SavedArtifactInfo(**fallback_dict)
            except Exception as e:
                log.warning(
                    "%s Failed to save raw JSON alongside: %s", log_identifier, e
                )

        log.info(
            "%s Intelligent processing complete: %d artifacts saved, status: %s",
            log_identifier,
            len(saved_artifacts),
            overall_status.value,
        )
        return McpSaveResult(
            status=overall_status,
            artifacts_saved=saved_artifacts,
            fallback_artifact=fallback_artifact,
            message=f"Successfully processed {len(saved_artifacts)} content items.",
        )

    except Exception as e:
        log.exception(
            "%s Error in intelligent MCP response processing: %s", log_identifier, e
        )
        if processor_config.fallback_to_raw_on_error:
            log.info(
                "%s Falling back to raw JSON due to processing error.", log_identifier
            )
            try:
                fallback_dict = await _save_raw_mcp_response_fallback(
                    tool,
                    tool_context,
                    host_component,
                    mcp_response_dict,
                    original_tool_args,
                )
                if fallback_dict.get("status") in ["success", "partial_success"]:
                    fallback_artifact = SavedArtifactInfo(**fallback_dict)
                return McpSaveResult(
                    status=McpSaveStatus.PARTIAL_SUCCESS,
                    artifacts_saved=saved_artifacts,
                    fallback_artifact=fallback_artifact,
                    message=f"Intelligent processing failed, saved raw JSON as fallback: {e}",
                )
            except Exception as fallback_error:
                log.exception(
                    "%s Fallback also failed: %s", log_identifier, fallback_error
                )

        return McpSaveResult(
            status=McpSaveStatus.ERROR,
            artifacts_saved=saved_artifacts,
            fallback_artifact=None,
            message=f"Failed to save MCP response as artifact: {e}",
        )


async def _save_content_item_as_artifact(
    content_item,
    tool_context: ToolContext,
    host_component: "SamAgentComponent",
) -> Dict[str, Any]:
    """Save a single processed content item as an artifact."""

    log_identifier = f"[IntelligentMCPCallback:SaveContentItem:{content_item.filename}]"

    try:
        artifact_service = host_component.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available on host_component.")

        app_name = host_component.agent_name
        user_id = tool_context._invocation_context.user_id
        session_id = get_original_session_id(tool_context._invocation_context)
        schema_max_keys = host_component.get_config(
            "schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS
        )
        artifact_timestamp = datetime.now(timezone.utc)

        log.debug(
            "%s Saving content item: type=%s, mime_type=%s, size=%d bytes",
            log_identifier,
            content_item.content_type,
            content_item.mime_type,
            len(content_item.content_bytes),
        )

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=content_item.filename,
            content_bytes=content_item.content_bytes,
            mime_type=content_item.mime_type,
            metadata_dict=content_item.metadata,
            timestamp=artifact_timestamp,
            schema_max_keys=schema_max_keys,
            tool_context=tool_context,
        )

        log.info(
            "%s Content item saved as artifact '%s' (version %s). Status: %s",
            log_identifier,
            save_result.get("data_filename", content_item.filename),
            save_result.get("data_version", "N/A"),
            save_result.get("status"),
        )

        return save_result

    except Exception as e:
        log.exception("%s Error saving content item as artifact: %s", log_identifier, e)
        return {
            "status": "error",
            "data_filename": content_item.filename,
            "message": f"Failed to save content item as artifact: {e}",
        }


async def _save_raw_mcp_response_fallback(
    tool: BaseTool,
    tool_context: ToolContext,
    host_component: "SamAgentComponent",
    mcp_response_dict: Dict[str, Any],
    original_tool_args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Fallback function to save the raw MCP response as a JSON artifact.
    This is the original behavior, used when intelligent processing is disabled or fails.
    """
    log_identifier = f"[IntelligentMCPCallback:{tool.name}:RawFallback]"
    log.debug("%s Saving raw MCP response as JSON artifact...", log_identifier)

    try:
        a2a_context = tool_context.state.get("a2a_context", {})
        logical_task_id = a2a_context.get("logical_task_id", "unknownTask")
        task_id_suffix = logical_task_id[-6:]
        random_suffix = uuid.uuid4().hex[:6]
        filename = f"{task_id_suffix}_{tool.name}_raw_{random_suffix}.json"

        content_bytes = json.dumps(mcp_response_dict, indent=2).encode("utf-8")
        mime_type = "application/json"
        artifact_timestamp = datetime.now(timezone.utc)

        metadata_for_saving = {
            "description": f"Raw JSON response from MCP tool {tool.name}",
            "source_tool_name": tool.name,
            "source_tool_args": original_tool_args,
            "processing_type": "raw_fallback",
        }

        artifact_service = host_component.artifact_service
        app_name = host_component.agent_name
        user_id = tool_context._invocation_context.user_id
        session_id = get_original_session_id(tool_context._invocation_context)
        schema_max_keys = host_component.get_config(
            "schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS
        )

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            content_bytes=content_bytes,
            mime_type=mime_type,
            metadata_dict=metadata_for_saving,
            timestamp=artifact_timestamp,
            schema_max_keys=schema_max_keys,
            tool_context=tool_context,
        )

        log.info(
            "%s Raw MCP response saved as artifact '%s' (version %s). Status: %s",
            log_identifier,
            save_result.get("data_filename", filename),
            save_result.get("data_version", "N/A"),
            save_result.get("status"),
        )

        return save_result

    except Exception as e:
        log.exception(
            "%s Error saving raw MCP response as artifact: %s", log_identifier, e
        )
        return {
            "status": "error",
            "data_filename": filename if "filename" in locals() else "unknown_filename",
            "message": f"Failed to save raw MCP response as artifact: {e}",
        }
