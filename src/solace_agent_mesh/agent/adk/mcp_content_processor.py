"""
MCP Content Processor for Intelligent Artifact Saving

This module provides intelligent processing of MCP tool responses, converting
raw MCP content into appropriately typed and formatted artifacts based on
the MCP specification content types.

Supports:
- Text content with format detection (CSV, JSON, YAML)
- Image content with base64 decoding
- Audio content with base64 decoding
- Resource content with URI-based filename extraction
"""

import logging
import base64
import csv
import json
import re
import uuid
import yaml
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

log = logging.getLogger(__name__)

from ...common.utils.mime_helpers import (
    is_text_based_mime_type,
    get_extension_for_mime_type,
)


class MCPContentType:
    """Constants for MCP content types as defined in the MCP specification."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    RESOURCE = "resource"


class TextFormat:
    """Constants for detected text formats."""

    CSV = "csv"
    JSON = "json"
    YAML = "yaml"
    PLAIN = "plain"
    MARKDOWN = "markdown"


class MCPContentItem:
    """Represents a processed MCP content item with metadata."""

    def __init__(
        self,
        content_type: str,
        content_bytes: bytes,
        mime_type: str,
        filename: str,
        metadata: Dict[str, Any],
        original_content: Dict[str, Any],
    ):
        self.content_type = content_type
        self.content_bytes = content_bytes
        self.mime_type = mime_type
        self.filename = filename
        self.metadata = metadata
        self.original_content = original_content


class MCPContentProcessor:
    """Main processor for MCP tool response content."""

    def __init__(self, tool_name: str, tool_args: Dict[str, Any]):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.log_identifier = f"[MCPContentProcessor:{tool_name}]"

    def process_mcp_response(
        self, mcp_response_dict: Dict[str, Any]
    ) -> List[MCPContentItem]:
        """
        Process an MCP tool response and extract content items.

        Args:
            mcp_response_dict: The raw MCP tool response dictionary

        Returns:
            List of processed MCPContentItem objects
        """
        log.debug(
            "%s Processing MCP response for intelligent artifact saving",
            self.log_identifier,
        )

        content_items = []

        # Extract content array from MCP response
        content_array = self._extract_content_array(mcp_response_dict)

        if not content_array:
            log.warning(
                "%s No content array found in MCP response", self.log_identifier
            )
            return content_items

        # Process each content item
        for idx, content_item in enumerate(content_array):
            try:
                processed_item = self._process_content_item(content_item, idx)
                if processed_item:
                    content_items.append(processed_item)
            except Exception as e:
                log.exception(
                    "%s Error processing content item %d: %s",
                    self.log_identifier,
                    idx,
                    e,
                )
                continue

        log.info(
            "%s Successfully processed %d content items from MCP response",
            self.log_identifier,
            len(content_items),
        )

        return content_items

    def _extract_content_array(
        self, mcp_response_dict: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract the content array from various possible MCP response structures."""

        # Try common MCP response structures
        if "content" in mcp_response_dict:
            content = mcp_response_dict["content"]
            if isinstance(content, list):
                return content
            elif isinstance(content, dict):
                return [content]

        # Check for nested structures
        if "result" in mcp_response_dict:
            result = mcp_response_dict["result"]
            if isinstance(result, dict) and "content" in result:
                content = result["content"]
                if isinstance(content, list):
                    return content
                elif isinstance(content, dict):
                    return [content]

        # Check for direct content items at root level
        if "type" in mcp_response_dict:
            return [mcp_response_dict]

        log.debug("%s No recognizable content structure found", self.log_identifier)
        return []

    def _process_content_item(
        self, content_item: Dict[str, Any], index: int
    ) -> Optional[MCPContentItem]:
        """Process a single content item based on its type."""

        content_type = content_item.get("type")
        if not content_type:
            log.warning(
                "%s Content item %d missing type field", self.log_identifier, index
            )
            return None

        log.debug(
            "%s Processing content item %d of type: %s",
            self.log_identifier,
            index,
            content_type,
        )

        # Route to appropriate processor based on content type
        if content_type == MCPContentType.TEXT:
            return self._process_text_content(content_item, index)
        elif content_type == MCPContentType.IMAGE:
            return self._process_image_content(content_item, index)
        elif content_type == MCPContentType.AUDIO:
            return self._process_audio_content(content_item, index)
        elif content_type == MCPContentType.RESOURCE:
            return self._process_resource_content(content_item, index)
        else:
            log.warning(
                "%s Unknown content type: %s", self.log_identifier, content_type
            )
            return None

    def _log_empty_content(self, content_type: str, index: int):
        """Log warning for empty content and return None."""
        log.warning(
            "%s %s content item %d is empty", self.log_identifier, content_type, index
        )

    def _create_content_item(
        self,
        content_type: str,
        content_bytes: bytes,
        mime_type: str,
        filename: str,
        index: int,
        specific_metadata: Dict[str, Any],
        original_content: Dict[str, Any],
    ) -> MCPContentItem:
        """Create an MCPContentItem with common metadata structure."""
        # Create base metadata that's common to all content types
        metadata = {
            "description": f"{content_type.title()} content from MCP tool {self.tool_name}",
            "source_tool_name": self.tool_name,
            "source_tool_args": self.tool_args,
            "content_type": content_type,
            "content_index": index,
        }

        # Add MIME type info for binary content
        if content_type in [
            MCPContentType.IMAGE,
            MCPContentType.AUDIO,
            MCPContentType.RESOURCE,
        ]:
            metadata["original_mime_type"] = mime_type

        # Merge in specific metadata
        metadata.update(specific_metadata)

        return MCPContentItem(
            content_type=content_type,
            content_bytes=content_bytes,
            mime_type=mime_type,
            filename=filename,
            metadata=metadata,
            original_content=original_content,
        )

    def _process_binary_content(
        self,
        content_item: Dict[str, Any],
        index: int,
        content_type: str,
        data_key: str,
        mime_type_key: str,
        default_mime_type: str,
        default_extension: str,
        size_metadata_key: str,
    ) -> Optional[MCPContentItem]:
        """Generic processor for binary content (images, audio) with base64 decoding."""
        binary_data = content_item.get(data_key, "")
        mime_type = content_item.get(mime_type_key, default_mime_type)

        if not binary_data:
            return self._log_empty_content(content_type.title(), index)

        try:
            # Decode base64 data
            content_bytes = base64.b64decode(binary_data)
        except Exception as e:
            log.error(
                "%s Failed to decode base64 %s data for item %d: %s",
                self.log_identifier,
                content_type,
                index,
                e,
            )
            return None

        # Generate filename with appropriate extension
        extension = get_extension_for_mime_type(mime_type, default_extension)
        filename = (
            f"{self.tool_name}_{content_type}_{index}_{uuid.uuid4().hex[:8]}{extension}"
        )

        # Create specific metadata for binary content
        specific_metadata = {
            size_metadata_key: len(content_bytes),
        }

        log.debug(
            "%s Processed %s content item %d: mime_type=%s, size=%d bytes",
            self.log_identifier,
            content_type,
            index,
            mime_type,
            len(content_bytes),
        )

        return self._create_content_item(
            content_type=content_type,
            content_bytes=content_bytes,
            mime_type=mime_type,
            filename=filename,
            index=index,
            specific_metadata=specific_metadata,
            original_content=content_item,
        )

    def _process_text_content(
        self, content_item: Dict[str, Any], index: int
    ) -> Optional[MCPContentItem]:
        """Process text content with format detection and parsing."""
        text_content = content_item.get("text", "")
        if not text_content:
            return self._log_empty_content("Text", index)

        # Detect text format
        detected_format, parse_success, parsed_data = (
            self._detect_and_parse_text_format(text_content)
        )

        # Determine MIME type and file extension
        mime_type, extension = self._get_text_mime_type_and_extension(detected_format)

        # Generate filename
        filename = self._generate_text_filename(detected_format, extension, index)

        # Create specific metadata for text content
        specific_metadata = {
            "detected_format": detected_format,
            "format_parse_success": parse_success,
        }

        if parse_success and parsed_data is not None:
            specific_metadata["parsed_data_summary"] = self._create_parsed_data_summary(
                parsed_data, detected_format
            )

        # If CSV was detected, use the version with unescaped newlines for saving.
        if detected_format == TextFormat.CSV:
            content_to_save = text_content.replace("\\n", "\n")
        else:
            content_to_save = text_content

        # Convert to bytes
        content_bytes = content_to_save.encode("utf-8")

        log.debug(
            "%s Processed text content item %d: format=%s, parse_success=%s, size=%d bytes",
            self.log_identifier,
            index,
            detected_format,
            parse_success,
            len(content_bytes),
        )

        return self._create_content_item(
            content_type=MCPContentType.TEXT,
            content_bytes=content_bytes,
            mime_type=mime_type,
            filename=filename,
            index=index,
            specific_metadata=specific_metadata,
            original_content=content_item,
        )

    def _process_image_content(
        self, content_item: Dict[str, Any], index: int
    ) -> Optional[MCPContentItem]:
        """Process image content with base64 decoding."""
        return self._process_binary_content(
            content_item=content_item,
            index=index,
            content_type=MCPContentType.IMAGE,
            data_key="data",
            mime_type_key="mimeType",
            default_mime_type="image/png",
            default_extension=".png",
            size_metadata_key="image_size_bytes",
        )

    def _process_audio_content(
        self, content_item: Dict[str, Any], index: int
    ) -> Optional[MCPContentItem]:
        """Process audio content with base64 decoding."""
        return self._process_binary_content(
            content_item=content_item,
            index=index,
            content_type=MCPContentType.AUDIO,
            data_key="data",
            mime_type_key="mimeType",
            default_mime_type="audio/wav",
            default_extension=".wav",
            size_metadata_key="audio_size_bytes",
        )

    def _process_resource_content(
        self, content_item: Dict[str, Any], index: int
    ) -> Optional[MCPContentItem]:
        """Process resource content with URI-based filename extraction and MIME type detection."""
        resource = content_item.get("resource", {})
        if not resource:
            log.warning(
                "%s Resource content item %d missing resource field",
                self.log_identifier,
                index,
            )
            return None

        uri = resource.get("uri", "")
        mime_type = resource.get("mimeType", "application/octet-stream")
        text_content = resource.get("text")
        blob_content = resource.get("blob")

        if uri:
            uri = str(uri)

        # Extract filename from URI
        filename = self._extract_filename_from_uri(uri, mime_type, index)

        # Determine if the resource is text-based or binary using MIME type detection
        is_text_based = is_text_based_mime_type(mime_type)

        if blob_content:
            # Handle binary blob content
            try:
                content_bytes = base64.b64decode(blob_content)
                specific_metadata = {
                    "resource_uri": uri,
                    "has_text_content": False,
                    "has_blob_content": True,
                    "is_text_based": False,
                    "decoded_from_base64": True,
                    "original_size_bytes": len(blob_content),
                    "decoded_size_bytes": len(content_bytes),
                    "is_placeholder": False,
                }
                log.debug(
                    "%s Resource content item %d: decoded base64 blob content, original=%d bytes, decoded=%d bytes",
                    self.log_identifier,
                    index,
                    len(blob_content),
                    len(content_bytes),
                )
            except Exception as e:
                log.error(
                    "%s Resource content item %d: failed to decode blob as base64: %s",
                    self.log_identifier,
                    index,
                    str(e),
                )
                return None  # Fail processing for this item
        elif text_content:
            # Handle text content
            content_bytes = text_content.encode("utf-8")
            specific_metadata = {
                "resource_uri": uri,
                "has_text_content": True,
                "has_blob_content": False,
                "is_text_based": True,
                "is_placeholder": False,
            }
        else:
            # No content - create placeholder
            content_bytes = f"Resource reference: {uri}".encode("utf-8")
            specific_metadata = {
                "resource_uri": uri,
                "has_text_content": False,
                "has_blob_content": False,
                "is_text_based": is_text_based,
                "is_placeholder": True,
            }

        log.debug(
            "%s Processed resource content item %d: uri=%s, mime_type=%s, is_text_based=%s, size=%d bytes",
            self.log_identifier,
            index,
            uri,
            mime_type,
            is_text_based,
            len(content_bytes),
        )

        return self._create_content_item(
            content_type=MCPContentType.RESOURCE,
            content_bytes=content_bytes,
            mime_type=mime_type,
            filename=filename,
            index=index,
            specific_metadata=specific_metadata,
            original_content=content_item,
        )

    def _detect_and_parse_text_format(self, text_content: str) -> Tuple[str, bool, Any]:
        """
        Detect text format and attempt to parse it.

        Returns:
            Tuple of (detected_format, parse_success, parsed_data)
        """

        # Try JSON first
        try:
            # Only consider it JSON if it's a structured type (dict or list)
            parsed_data = json.loads(text_content)
            if isinstance(parsed_data, (dict, list)):
                return TextFormat.JSON, True, parsed_data
        except (json.JSONDecodeError, ValueError):
            pass

        # Try YAML
        try:
            parsed_data = yaml.safe_load(text_content)
            # Only consider it YAML if it's not just a plain string
            if isinstance(parsed_data, (dict, list)):
                return TextFormat.YAML, True, parsed_data
        except (yaml.YAMLError, ValueError):
            pass

        # Try CSV
        try:
            # Unescape newlines for robust CSV detection and parsing
            processed_text_for_csv = text_content.replace("\\n", "\n")
            # Check if it looks like CSV (has commas and multiple lines)
            if "," in processed_text_for_csv and "\n" in processed_text_for_csv:
                csv_reader = csv.reader(StringIO(processed_text_for_csv))
                rows = list(csv_reader)
                if len(rows) > 1 and len(rows[0]) > 1:  # At least 2 rows and 2 columns
                    return TextFormat.CSV, True, rows
        except Exception:
            pass

        # Check for Markdown indicators
        markdown_indicators = ["#", "##", "###", "**", "*", "`", "```", "[", "]("]
        if any(indicator in text_content for indicator in markdown_indicators):
            return TextFormat.MARKDOWN, True, None

        # Default to plain text
        return TextFormat.PLAIN, True, None

    def _get_text_mime_type_and_extension(
        self, detected_format: str
    ) -> Tuple[str, str]:
        """Get MIME type and file extension for detected text format."""

        format_mapping = {
            TextFormat.JSON: ("application/json", ".json"),
            TextFormat.YAML: ("application/yaml", ".yaml"),
            TextFormat.CSV: ("text/csv", ".csv"),
            TextFormat.MARKDOWN: ("text/markdown", ".md"),
            TextFormat.PLAIN: ("text/plain", ".txt"),
        }

        return format_mapping.get(detected_format, ("text/plain", ".txt"))

    def _generate_text_filename(
        self, detected_format: str, extension: str, index: int
    ) -> str:
        """Generate filename for text content based on format."""

        format_prefix = {
            TextFormat.JSON: "json",
            TextFormat.YAML: "yaml",
            TextFormat.CSV: "csv",
            TextFormat.MARKDOWN: "markdown",
            TextFormat.PLAIN: "text",
        }.get(detected_format, "text")

        return f"{self.tool_name}_{format_prefix}_{index}_{uuid.uuid4().hex[:8]}{extension}"

    def _create_parsed_data_summary(
        self, parsed_data: Any, detected_format: str
    ) -> Dict[str, Any]:
        """Create a summary of parsed data for metadata."""

        summary = {"format": detected_format}

        if detected_format == TextFormat.JSON:
            if isinstance(parsed_data, dict):
                summary["type"] = "object"
                summary["keys"] = list(parsed_data.keys())[:10]  # First 10 keys
                summary["key_count"] = len(parsed_data)
            elif isinstance(parsed_data, list):
                summary["type"] = "array"
                summary["length"] = len(parsed_data)
                if parsed_data and isinstance(parsed_data[0], dict):
                    summary["first_item_keys"] = list(parsed_data[0].keys())[:5]

        elif detected_format == TextFormat.YAML:
            if isinstance(parsed_data, dict):
                summary["type"] = "object"
                summary["keys"] = list(parsed_data.keys())[:10]
                summary["key_count"] = len(parsed_data)
            elif isinstance(parsed_data, list):
                summary["type"] = "array"
                summary["length"] = len(parsed_data)

        elif detected_format == TextFormat.CSV:
            if isinstance(parsed_data, list) and parsed_data:
                summary["type"] = "table"
                summary["rows"] = len(parsed_data)
                summary["columns"] = len(parsed_data[0]) if parsed_data[0] else 0
                summary["headers"] = parsed_data[0][:5] if parsed_data[0] else []

        return summary

    def _extract_filename_from_uri(self, uri: str, mime_type: str, index: int) -> str:
        """Extract filename from URI or generate one based on URI components."""
        try:
            parsed_uri = urlparse(uri)

            # Try to get filename from path
            if parsed_uri.path:
                path_parts = parsed_uri.path.strip("/").split("/")
                if path_parts and path_parts[-1]:
                    filename_part = path_parts[-1]
                    # Clean filename and ensure it has an extension
                    clean_filename = re.sub(r'[<>:"/\\|?*]', "_", filename_part)
                    if "." not in clean_filename:
                        extension = get_extension_for_mime_type(mime_type)
                        clean_filename += extension
                    return f"{self.tool_name}_resource_{index}_{clean_filename}"

            # Use hostname if available
            if parsed_uri.hostname:
                hostname = re.sub(r'[<>:"/\\|?*.]', "_", parsed_uri.hostname)
                extension = get_extension_for_mime_type(mime_type)
                return f"{self.tool_name}_resource_{index}_{hostname}{extension}"

        except Exception as e:
            log.debug("%s Error parsing URI %s: %s", self.log_identifier, uri, e)

        # Fallback to generic filename
        extension = get_extension_for_mime_type(mime_type)
        return f"{self.tool_name}_resource_{index}_{uuid.uuid4().hex[:8]}{extension}"


class MCPContentProcessorConfig:
    """Configuration for MCP content processing."""

    def __init__(
        self,
        enable_intelligent_processing: bool = True,
        enable_text_format_detection: bool = True,
        enable_content_parsing: bool = True,
        fallback_to_raw_on_error: bool = True,
        max_content_items: int = 50,
        max_single_item_size_mb: int = 100,
    ):
        self.enable_intelligent_processing = enable_intelligent_processing
        self.enable_text_format_detection = enable_text_format_detection
        self.enable_content_parsing = enable_content_parsing
        self.fallback_to_raw_on_error = fallback_to_raw_on_error
        self.max_content_items = max_content_items
        self.max_single_item_size_mb = max_single_item_size_mb

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "MCPContentProcessorConfig":
        """Create config from dictionary."""
        return cls(
            enable_intelligent_processing=config_dict.get(
                "enable_intelligent_processing", True
            ),
            enable_text_format_detection=config_dict.get(
                "enable_text_format_detection", True
            ),
            enable_content_parsing=config_dict.get("enable_content_parsing", True),
            fallback_to_raw_on_error=config_dict.get("fallback_to_raw_on_error", True),
            max_content_items=config_dict.get("max_content_items", 50),
            max_single_item_size_mb=config_dict.get("max_single_item_size_mb", 100),
        )
