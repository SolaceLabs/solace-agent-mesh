"""
File conversion utilities for the HTTP/SSE gateway.
Provides functionality to convert various file formats to markdown/text.
"""

import logging
import tempfile
import os
from typing import Tuple, Optional
from markitdown import MarkItDown, UnsupportedFormatException

log = logging.getLogger(__name__)


class FileConverter:
    """
    Handles file conversion operations for uploaded artifacts.
    Uses MarkItDown library to convert various formats to markdown.
    """

    # File extensions that should be converted to markdown
    CONVERTIBLE_EXTENSIONS = {
        '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt',
        '.html', '.htm', '.zip', '.xml', '.json', '.csv'
    }

    # File extensions that are already text-based and don't need conversion
    TEXT_EXTENSIONS = {
        '.txt', '.md', '.markdown', '.rst', '.log', '.yaml', '.yml',
        '.json', '.xml', '.csv', '.tsv', '.py', '.js', '.java', '.c',
        '.cpp', '.h', '.sh', '.bash', '.sql', '.r', '.go', '.rs'
    }

    def __init__(self):
        """Initialize the file converter with MarkItDown."""
        self.converter = MarkItDown()

    def should_convert(self, filename: str, mime_type: Optional[str] = None) -> bool:
        """
        Determine if a file should be converted to markdown.

        Args:
            filename: The name of the file
            mime_type: Optional MIME type of the file

        Returns:
            True if the file should be converted, False otherwise
        """
        _, ext = os.path.splitext(filename.lower())
        
        # Don't convert if already text/markdown
        if ext in self.TEXT_EXTENSIONS:
            return False
        
        # Convert if it's a known convertible format
        if ext in self.CONVERTIBLE_EXTENSIONS:
            return True
        
        # Check MIME type if extension is not recognized
        if mime_type:
            convertible_mime_types = {
                'application/pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'application/vnd.ms-powerpoint',
                'text/html',
                'application/zip',
            }
            return mime_type in convertible_mime_types
        
        return False

    async def convert_to_markdown(
        self,
        content_bytes: bytes,
        original_filename: str,
        mime_type: str
    ) -> Tuple[bytes, str, str, dict]:
        """
        Convert file content to markdown format.

        Args:
            content_bytes: The raw file content
            original_filename: Original filename (used for extension detection)
            mime_type: MIME type of the original file

        Returns:
            Tuple of (converted_content_bytes, new_filename, new_mime_type, conversion_metadata)

        Raises:
            UnsupportedFormatException: If the file format is not supported
            Exception: For other conversion errors
        """
        log_identifier = f"[FileConverter:convert:{original_filename}]"
        log.info("%s Starting conversion to markdown", log_identifier)

        temp_file = None
        try:
            # Get file extension for temp file
            _, ext = os.path.splitext(original_filename)
            
            # Create temporary file with original extension
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=ext if ext else None
            )
            temp_file.write(content_bytes)
            temp_file.close()
            
            log.debug(
                "%s Wrote %d bytes to temporary file: %s",
                log_identifier,
                len(content_bytes),
                temp_file.name
            )

            # Perform conversion using MarkItDown
            log.debug("%s Calling MarkItDown.convert()", log_identifier)
            conversion_result = self.converter.convert(temp_file.name)

            markdown_content = (
                conversion_result.text_content
                if conversion_result and conversion_result.text_content
                else ""
            )

            if not markdown_content:
                log.warning(
                    "%s MarkItDown conversion resulted in empty content",
                    log_identifier
                )
                # Return original content if conversion fails
                return content_bytes, original_filename, mime_type, {
                    "conversion_attempted": True,
                    "conversion_successful": False,
                    "reason": "Empty conversion result"
                }

            # Convert to bytes
            markdown_bytes = markdown_content.encode('utf-8')
            
            # Generate new filename
            base_name, _ = os.path.splitext(original_filename)
            new_filename = f"{base_name}_converted.md"
            new_mime_type = "text/markdown"

            # Create conversion metadata
            conversion_metadata = {
                "conversion_attempted": True,
                "conversion_successful": True,
                "original_filename": original_filename,
                "original_mime_type": mime_type,
                "original_size_bytes": len(content_bytes),
                "converted_size_bytes": len(markdown_bytes),
                "conversion_tool": "MarkItDown"
            }

            log.info(
                "%s Successfully converted to markdown. Original: %d bytes, Converted: %d bytes",
                log_identifier,
                len(content_bytes),
                len(markdown_bytes)
            )

            return markdown_bytes, new_filename, new_mime_type, conversion_metadata

        except UnsupportedFormatException as e:
            log.warning(
                "%s Unsupported format for conversion: %s",
                log_identifier,
                e
            )
            # Return original content with metadata indicating unsupported format
            return content_bytes, original_filename, mime_type, {
                "conversion_attempted": True,
                "conversion_successful": False,
                "reason": f"Unsupported format: {str(e)}"
            }

        except Exception as e:
            log.error(
                "%s Error during conversion: %s",
                log_identifier,
                e,
                exc_info=True
            )
            # Return original content on error
            return content_bytes, original_filename, mime_type, {
                "conversion_attempted": True,
                "conversion_successful": False,
                "reason": f"Conversion error: {str(e)}"
            }

        finally:
            # Clean up temporary file
            if temp_file and temp_file.name and os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                    log.debug(
                        "%s Removed temporary file: %s",
                        log_identifier,
                        temp_file.name
                    )
                except OSError as e:
                    log.error(
                        "%s Failed to remove temporary file %s: %s",
                        log_identifier,
                        temp_file.name,
                        e
                    )

    def get_converted_filename(self, original_filename: str) -> str:
        """
        Generate the converted filename for a given original filename.

        Args:
            original_filename: The original filename

        Returns:
            The converted filename with .md extension
        """
        base_name, _ = os.path.splitext(original_filename)
        return f"{base_name}_converted.md"


# Singleton instance
_file_converter_instance = None


def get_file_converter() -> FileConverter:
    """
    Get or create the singleton FileConverter instance.

    Returns:
        FileConverter instance
    """
    global _file_converter_instance
    if _file_converter_instance is None:
        _file_converter_instance = FileConverter()
    return _file_converter_instance
