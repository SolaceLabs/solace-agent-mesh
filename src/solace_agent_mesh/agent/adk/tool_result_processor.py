"""
Processes ToolResult objects, handling artifact storage and response transformation.

This processor is invoked in the after_tool_callback chain and handles:
1. Detection of ToolResult vs raw dict returns
2. Processing DataObjects based on their disposition
3. Storing artifacts with metadata
4. Constructing the final dict response for the LLM
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from google.adk.tools import ToolContext

from ..tools.tool_result import ToolResult, DataObject, DataDisposition
from ..utils.artifact_helpers import (
    save_artifact_with_metadata,
    is_filename_safe,
    DEFAULT_SCHEMA_MAX_KEYS,
)
from ..utils.context_helpers import get_original_session_id
from ...common.utils.mime_helpers import is_text_based_mime_type

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent

log = logging.getLogger(__name__)


# Default configuration values
DEFAULT_AUTO_ARTIFACT_THRESHOLD_BYTES = 4096
DEFAULT_INLINE_TRUNCATION_BYTES = 8192
DEFAULT_PREVIEW_LENGTH_CHARS = 500


class ToolResultProcessorConfig:
    """Configuration for ToolResultProcessor behavior."""

    def __init__(
        self,
        auto_artifact_threshold_bytes: int = DEFAULT_AUTO_ARTIFACT_THRESHOLD_BYTES,
        inline_truncation_bytes: int = DEFAULT_INLINE_TRUNCATION_BYTES,
        preview_length_chars: int = DEFAULT_PREVIEW_LENGTH_CHARS,
        enabled: bool = True,
    ):
        self.auto_artifact_threshold_bytes = auto_artifact_threshold_bytes
        self.inline_truncation_bytes = inline_truncation_bytes
        self.preview_length_chars = preview_length_chars
        self.enabled = enabled

    @classmethod
    def from_component(cls, host_component: "SamAgentComponent") -> "ToolResultProcessorConfig":
        """Load configuration from host component."""
        return cls(
            auto_artifact_threshold_bytes=host_component.get_config(
                "tool_result_auto_artifact_threshold_bytes",
                DEFAULT_AUTO_ARTIFACT_THRESHOLD_BYTES,
            ),
            inline_truncation_bytes=host_component.get_config(
                "tool_result_inline_truncation_bytes",
                DEFAULT_INLINE_TRUNCATION_BYTES,
            ),
            preview_length_chars=host_component.get_config(
                "tool_result_preview_length_chars",
                DEFAULT_PREVIEW_LENGTH_CHARS,
            ),
            enabled=host_component.get_config(
                "tool_result_processing_enabled",
                True,
            ),
        )


class ToolResultProcessor:
    """
    Processes ToolResult objects, converting DataObjects to artifacts as needed.

    This processor handles:
    - Detection of ToolResult instances vs raw dict returns
    - Processing DataObjects based on their disposition (AUTO, ARTIFACT, INLINE, etc.)
    - Storing artifacts with metadata
    - Generating previews for large content
    - Constructing the final dict response for the LLM
    """

    def __init__(
        self,
        host_component: "SamAgentComponent",
        config: Optional[ToolResultProcessorConfig] = None,
    ):
        self.host_component = host_component
        self.config = config or ToolResultProcessorConfig.from_component(host_component)
        self.log_identifier = "[ToolResultProcessor]"

    async def process(
        self,
        tool_response: Any,
        tool_context: ToolContext,
        tool_name: str,
    ) -> Dict[str, Any]:
        """
        Process a tool response, handling ToolResult or passing through raw dicts.

        Args:
            tool_response: The raw response from the tool (ToolResult, dict, or other)
            tool_context: The ADK ToolContext for accessing services
            tool_name: Name of the tool for logging

        Returns:
            A dictionary suitable for return to the LLM
        """
        log_id = f"{self.log_identifier}:{tool_name}"

        # If processing is disabled, pass through
        if not self.config.enabled:
            log.debug("%s ToolResult processing is disabled, passing through", log_id)
            return tool_response

        # Handle None responses
        if tool_response is None:
            return None

        # Check if this is a ToolResult instance
        if isinstance(tool_response, ToolResult):
            log.info("%s Processing ToolResult object", log_id)
            return await self._process_tool_result(tool_response, tool_context, log_id)

        # Check if this is a dict with data_objects (duck-typing ToolResult)
        if isinstance(tool_response, dict) and "data_objects" in tool_response:
            if isinstance(tool_response.get("data_objects"), list):
                log.info("%s Detected dict with data_objects, converting to ToolResult", log_id)
                try:
                    tool_result = ToolResult(**tool_response)
                    return await self._process_tool_result(tool_result, tool_context, log_id)
                except Exception as e:
                    log.warning(
                        "%s Failed to convert dict to ToolResult: %s. Passing through.",
                        log_id,
                        e,
                    )

        # Pass through raw dict responses unchanged (backward compatibility)
        if isinstance(tool_response, dict):
            log.debug("%s Passing through raw dict response", log_id)
            return tool_response

        # Wrap non-dict responses in a dict
        log.debug("%s Wrapping non-dict response (type: %s)", log_id, type(tool_response).__name__)
        return {"result": tool_response}

    async def _process_tool_result(
        self,
        result: ToolResult,
        tool_context: ToolContext,
        log_id: str,
    ) -> Dict[str, Any]:
        """Process a ToolResult, handling all DataObjects."""
        final_response: Dict[str, Any] = {
            "status": result.status,
        }

        if result.message:
            final_response["message"] = result.message

        if result.error_code:
            final_response["error_code"] = result.error_code

        # Include inline data if present
        if result.data:
            final_response.update(result.data)

        # Process each DataObject
        if result.data_objects:
            artifacts_created: List[Dict[str, Any]] = []
            inline_contents: List[Dict[str, Any]] = []

            for data_obj in result.data_objects:
                processed = await self._process_data_object(data_obj, tool_context, log_id)

                if processed.get("stored_as_artifact"):
                    artifacts_created.append({
                        "filename": processed.get("filename"),
                        "version": processed.get("version"),
                        "description": processed.get("description"),
                        "mime_type": processed.get("mime_type"),
                        "size_bytes": processed.get("size_bytes"),
                        "preview": processed.get("preview"),
                    })
                else:
                    inline_contents.append({
                        "name": processed.get("name"),
                        "content": processed.get("content"),
                        "truncated": processed.get("truncated", False),
                    })

            # Add artifact info to response
            if artifacts_created:
                final_response["artifacts_created"] = artifacts_created

            # Add inline content to response
            if inline_contents:
                if len(inline_contents) == 1:
                    # Single inline content - add directly
                    final_response["content"] = inline_contents[0]["content"]
                    if inline_contents[0].get("truncated"):
                        final_response["content_truncated"] = True
                else:
                    # Multiple inline contents
                    final_response["inline_outputs"] = inline_contents

        inline_count = len(final_response.get("inline_outputs", []))
        inline_count += 1 if "content" in final_response else 0
        log.debug(
            "%s Processed ToolResult: status=%s, artifacts=%d, inline=%d",
            log_id,
            result.status,
            len(final_response.get("artifacts_created", [])),
            inline_count,
        )

        return final_response

    async def _process_data_object(
        self,
        data_obj: DataObject,
        tool_context: ToolContext,
        log_id: str,
    ) -> Dict[str, Any]:
        """Process a single DataObject based on its disposition."""
        # Resolve AUTO disposition
        disposition = self._resolve_disposition(data_obj)

        log.debug(
            "%s Processing DataObject '%s': disposition=%s (resolved from %s)",
            log_id,
            data_obj.name,
            disposition,
            data_obj.disposition,
        )

        if disposition in (DataDisposition.ARTIFACT, DataDisposition.ARTIFACT_WITH_PREVIEW):
            return await self._store_as_artifact(data_obj, tool_context, log_id, disposition)
        else:
            return self._return_inline(data_obj, log_id)

    def _resolve_disposition(self, data_obj: DataObject) -> DataDisposition:
        """Resolve AUTO disposition to a concrete disposition."""
        if data_obj.disposition != DataDisposition.AUTO:
            return DataDisposition(data_obj.disposition)

        # Get content size
        content = data_obj.content
        if isinstance(content, bytes):
            content_size = len(content)
        else:
            content_size = len(content.encode("utf-8")) if content else 0

        # Binary content always goes to artifact
        if isinstance(content, bytes):
            return DataDisposition.ARTIFACT_WITH_PREVIEW

        # Non-text MIME types go to artifact
        if not is_text_based_mime_type(data_obj.mime_type):
            return DataDisposition.ARTIFACT_WITH_PREVIEW

        # Large text content goes to artifact with preview
        if content_size > self.config.auto_artifact_threshold_bytes:
            return DataDisposition.ARTIFACT_WITH_PREVIEW

        # Small text content stays inline
        return DataDisposition.INLINE

    async def _store_as_artifact(
        self,
        data_obj: DataObject,
        tool_context: ToolContext,
        log_id: str,
        disposition: DataDisposition,
    ) -> Dict[str, Any]:
        """Store a DataObject as an artifact."""
        # Validate filename
        filename = data_obj.name
        if not filename:
            filename = self._generate_filename(data_obj.mime_type)
            log.debug("%s Generated filename: %s", log_id, filename)

        if not is_filename_safe(filename):
            log.warning("%s Invalid filename '%s', cannot store as artifact", log_id, filename)
            return {
                "name": data_obj.name,
                "stored_as_artifact": False,
                "error": f"Invalid filename: {filename}",
            }

        try:
            inv_context = tool_context._invocation_context
            artifact_service = inv_context.artifact_service

            if not artifact_service:
                raise ValueError("ArtifactService not available in context")

            # Prepare content bytes
            content = data_obj.content
            if isinstance(content, bytes):
                content_bytes = content
            else:
                content_bytes = content.encode("utf-8") if content else b""

            content_size = len(content_bytes)

            # Prepare metadata
            metadata_dict = dict(data_obj.metadata) if data_obj.metadata else {}
            if data_obj.description:
                metadata_dict["description"] = data_obj.description
            metadata_dict["source"] = "tool_result"

            # Save artifact
            result = await save_artifact_with_metadata(
                artifact_service=artifact_service,
                app_name=inv_context.app_name,
                user_id=inv_context.user_id,
                session_id=get_original_session_id(inv_context),
                filename=filename,
                content_bytes=content_bytes,
                mime_type=data_obj.mime_type,
                metadata_dict=metadata_dict,
                timestamp=datetime.now(timezone.utc),
                schema_max_keys=DEFAULT_SCHEMA_MAX_KEYS,
                tool_context=tool_context,
            )

            # Generate preview if needed
            preview = None
            if disposition == DataDisposition.ARTIFACT_WITH_PREVIEW:
                preview = data_obj.preview or self._generate_preview(data_obj)

            version = result.get("data_version")
            log.info(
                "%s Stored artifact '%s' version %s (%d bytes)",
                log_id,
                filename,
                version,
                content_size,
            )

            return {
                "name": data_obj.name,
                "filename": filename,
                "stored_as_artifact": True,
                "version": version,
                "description": data_obj.description,
                "mime_type": data_obj.mime_type,
                "size_bytes": content_size,
                "preview": preview,
            }

        except Exception as e:
            log.exception("%s Failed to store artifact '%s': %s", log_id, filename, e)
            return {
                "name": data_obj.name,
                "stored_as_artifact": False,
                "error": str(e),
            }

    def _return_inline(self, data_obj: DataObject, log_id: str) -> Dict[str, Any]:
        """Return DataObject content inline, potentially truncated."""
        content = data_obj.content
        truncated = False

        if isinstance(content, str):
            if len(content) > self.config.inline_truncation_bytes:
                content = content[: self.config.inline_truncation_bytes] + "...[truncated]"
                truncated = True
                log.debug(
                    "%s Truncated inline content for '%s' to %d bytes",
                    log_id,
                    data_obj.name,
                    self.config.inline_truncation_bytes,
                )
        elif isinstance(content, bytes):
            # Binary content should not be returned inline - this shouldn't happen
            # if disposition resolution is working correctly
            content = f"[Binary content: {len(content)} bytes - use ARTIFACT disposition]"
            log.warning(
                "%s Binary content returned inline for '%s'. Consider using ARTIFACT disposition.",
                log_id,
                data_obj.name,
            )

        return {
            "name": data_obj.name,
            "stored_as_artifact": False,
            "content": content,
            "truncated": truncated,
        }

    def _generate_preview(self, data_obj: DataObject) -> str:
        """Generate a preview string for content."""
        # Use explicit preview if provided
        if data_obj.preview:
            return data_obj.preview

        content = data_obj.content

        # Binary content - just describe it
        if isinstance(content, bytes):
            return f"[Binary content: {len(content)} bytes, mime_type: {data_obj.mime_type}]"

        # Text content - truncate
        if not content:
            return "[Empty content]"

        if len(content) <= self.config.preview_length_chars:
            return content

        return content[: self.config.preview_length_chars] + "..."

    def _generate_filename(self, mime_type: str) -> str:
        """Generate a filename based on mime type."""
        ext_map = {
            "text/plain": ".txt",
            "text/csv": ".csv",
            "text/html": ".html",
            "text/markdown": ".md",
            "application/json": ".json",
            "application/xml": ".xml",
            "text/xml": ".xml",
            "application/yaml": ".yaml",
            "text/yaml": ".yaml",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/svg+xml": ".svg",
            "application/pdf": ".pdf",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
        }
        ext = ext_map.get(mime_type, ".bin")
        unique_id = uuid.uuid4().hex[:8]
        return f"output_{unique_id}{ext}"
