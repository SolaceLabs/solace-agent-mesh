"""
Document conversion service for converting Office documents to PDF.
Uses LibreOffice (soffice) for high-fidelity conversion.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Default maximum file size for conversion (50MB)
DEFAULT_MAX_CONVERSION_SIZE_BYTES = 50 * 1024 * 1024

# Default conversion timeout (30 seconds)
DEFAULT_CONVERSION_TIMEOUT_SECONDS = 30

# Retry configuration for finding output PDF
MAX_OUTPUT_RETRIES = 10
INITIAL_RETRY_DELAY = 0.2  # seconds
MAX_RETRY_DELAY = 2.0  # seconds


class DocumentConversionService:
    """Service for converting documents to PDF using LibreOffice."""

    # Supported input formats for conversion
    SUPPORTED_FORMATS = {
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ppt": "application/vnd.ms-powerpoint",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "odt": "application/vnd.oasis.opendocument.text",
        "odp": "application/vnd.oasis.opendocument.presentation",
        "ods": "application/vnd.oasis.opendocument.spreadsheet",
    }

    def __init__(
        self,
        libreoffice_path: Optional[str] = None,
        timeout_seconds: int = DEFAULT_CONVERSION_TIMEOUT_SECONDS,
        max_file_size_bytes: int = DEFAULT_MAX_CONVERSION_SIZE_BYTES,
    ):
        """
        Initialize the document conversion service.

        Args:
            libreoffice_path: Path to LibreOffice executable. If None, will search common locations.
            timeout_seconds: Maximum time to wait for conversion (default: 30 seconds)
            max_file_size_bytes: Maximum file size allowed for conversion (default: 50MB)
        """
        self.timeout_seconds = timeout_seconds
        self.max_file_size_bytes = max_file_size_bytes
        self.libreoffice_path = libreoffice_path or self._find_libreoffice()
        self._available = self.libreoffice_path is not None

        if self._available:
            log.info(
                "DocumentConversionService initialized with LibreOffice at: %s (timeout: %ds)",
                self.libreoffice_path,
                self.timeout_seconds,
            )
        else:
            log.warning(
                "DocumentConversionService: LibreOffice not found. "
                "Document conversion will not be available. "
                "Install LibreOffice to enable PPTX/DOCX to PDF conversion."
            )

    def _find_libreoffice(self) -> Optional[str]:
        """Find LibreOffice executable on the system."""
        # Common paths for LibreOffice
        common_paths = [
            # Linux
            "/usr/bin/soffice",
            "/usr/bin/libreoffice",
            "/usr/local/bin/soffice",
            "/usr/local/bin/libreoffice",
            # macOS
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/opt/homebrew/bin/soffice",
            # Windows (via WSL or native)
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
            "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",
        ]

        # First check if soffice is in PATH
        soffice_in_path = shutil.which("soffice")
        if soffice_in_path:
            return soffice_in_path

        libreoffice_in_path = shutil.which("libreoffice")
        if libreoffice_in_path:
            return libreoffice_in_path

        # Check common paths
        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        return None

    @property
    def is_available(self) -> bool:
        """Check if document conversion is available."""
        return self._available

    def get_supported_extensions(self) -> list[str]:
        """Get list of supported file extensions."""
        return list(self.SUPPORTED_FORMATS.keys())

    def is_format_supported(self, filename: str) -> bool:
        """Check if a file format is supported for conversion."""
        ext = Path(filename).suffix.lower().lstrip(".")
        return ext in self.SUPPORTED_FORMATS

    async def convert_binary_to_pdf(
        self,
        input_data: bytes,
        input_filename: str,
    ) -> tuple[bytes | None, str | None]:
        """
        Convert binary document data to PDF bytes.
        
        This method accepts raw binary data directly, avoiding unnecessary
        base64 encode/decode operations.

        Args:
            input_data: The document content as bytes
            input_filename: Original filename (used to determine format)

        Returns:
            Tuple of (pdf_bytes, error_message). 
            If successful, pdf_bytes contains the PDF and error_message is None.
            If failed, pdf_bytes is None and error_message contains the error.
        """
        try:
            # Wrap the conversion in a timeout
            pdf_bytes, error = await asyncio.wait_for(
                self._do_conversion(input_data, input_filename),
                timeout=self.timeout_seconds,
            )
            return pdf_bytes, error
        except asyncio.TimeoutError:
            log.error(
                "Conversion timeout for %s after %d seconds",
                input_filename,
                self.timeout_seconds,
            )
            return None, "Conversion timed out. The document may be too large or complex."
        except Exception as e:
            log.exception("Unexpected conversion error for %s: %s", input_filename, e)
            return None, "Conversion failed due to an internal error."

    async def _do_conversion(
        self,
        input_data: bytes,
        input_filename: str,
    ) -> tuple[bytes | None, str | None]:
        """
        Internal conversion logic.
        
        Args:
            input_data: The document content as bytes
            input_filename: Original filename (used to determine format)

        Returns:
            Tuple of (pdf_bytes, error_message).
        """
        if not self._available:
            return None, "Document conversion is not available. LibreOffice is not installed."

        # Check file size before processing
        input_size = len(input_data)
        if input_size > self.max_file_size_bytes:
            max_mb = self.max_file_size_bytes / (1024 * 1024)
            actual_mb = input_size / (1024 * 1024)
            log.warning(
                "Document conversion rejected: file too large (%s is %.1fMB, max is %.1fMB)",
                input_filename,
                actual_mb,
                max_mb,
            )
            return None, f"File too large for conversion. Maximum size is {max_mb:.0f}MB."

        ext = Path(input_filename).suffix.lower().lstrip(".")
        if ext not in self.SUPPORTED_FORMATS:
            return None, f"Unsupported format: {ext}. Supported formats: {', '.join(self.SUPPORTED_FORMATS.keys())}"

        # Create temporary directory for conversion
        with tempfile.TemporaryDirectory(prefix="doc_convert_") as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Write input file
            input_path = temp_dir_path / f"input.{ext}"
            input_path.write_bytes(input_data)

            log.debug(
                "Converting %s to PDF (size: %d bytes)",
                input_filename,
                len(input_data),
            )

            try:
                # Run LibreOffice conversion
                # --headless: Run without GUI
                # --convert-to pdf: Convert to PDF format
                # --outdir: Output directory
                cmd = [
                    self.libreoffice_path,
                    "--headless",
                    "--invisible",
                    "--nologo",
                    "--nofirststartwizard",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(temp_dir_path),
                    str(input_path),
                ]

                log.debug("Running conversion command: %s", " ".join(cmd))

                # Run conversion asynchronously
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(temp_dir_path),
                )

                # Wait for process with subprocess-level timeout
                # (This is separate from the overall method timeout)
                subprocess_timeout = min(self.timeout_seconds, 60)
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=subprocess_timeout,
                    )
                except asyncio.TimeoutError:
                    log.error(
                        "LibreOffice subprocess timed out for %s after %d seconds",
                        input_filename,
                        subprocess_timeout,
                    )
                    process.kill()
                    await process.wait()
                    return None, f"Conversion subprocess timed out after {subprocess_timeout} seconds"

                if process.returncode != 0:
                    error_msg = stderr.decode("utf-8", errors="replace")
                    log.error(
                        "LibreOffice conversion failed (exit code %d): %s",
                        process.returncode,
                        error_msg[:500],  # Truncate for logging
                    )
                    return None, "LibreOffice conversion failed"

                # Find the output PDF file with exponential backoff retry
                # LibreOffice may take a moment to write the file, especially for large docs
                output_path = await self._find_output_pdf(temp_dir_path, input_filename)

                if output_path is None:
                    return None, "Conversion completed but no PDF output was generated"

                # Read the PDF content
                pdf_bytes = output_path.read_bytes()

                log.info(
                    "Successfully converted %s to PDF (output size: %d bytes)",
                    input_filename,
                    len(pdf_bytes),
                )

                return pdf_bytes, None

            except Exception as e:
                log.exception("Unexpected error during document conversion: %s", e)
                return None, "Conversion failed due to an internal error"

    async def _find_output_pdf(
        self,
        temp_dir_path: Path,
        input_filename: str,
    ) -> Optional[Path]:
        """
        Find the output PDF file with exponential backoff retry.
        
        LibreOffice may take some time to write the output file, especially
        for large or complex documents. This method uses exponential backoff
        to wait for the file to appear.
        
        Args:
            temp_dir_path: Directory where output should be written
            input_filename: Original filename (for logging)
            
        Returns:
            Path to the output PDF, or None if not found after retries
        """
        total_wait_time = 0.0
        delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_OUTPUT_RETRIES):
            # Check for expected output filename
            candidate_path = temp_dir_path / "input.pdf"
            if candidate_path.exists():
                if attempt > 0:
                    log.debug(
                        "Found PDF output for %s after %d retries (%.1fs)",
                        input_filename,
                        attempt,
                        total_wait_time,
                    )
                return candidate_path

            # Sometimes LibreOffice uses the original filename
            possible_outputs = list(temp_dir_path.glob("*.pdf"))
            if possible_outputs:
                if attempt > 0:
                    log.debug(
                        "Found PDF output for %s after %d retries (%.1fs)",
                        input_filename,
                        attempt,
                        total_wait_time,
                    )
                return possible_outputs[0]

            # Wait before retrying with exponential backoff
            if attempt < MAX_OUTPUT_RETRIES - 1:
                await asyncio.sleep(delay)
                total_wait_time += delay
                # Exponential backoff: 0.2, 0.4, 0.8, 1.6, 2.0, 2.0, ...
                delay = min(delay * 2, MAX_RETRY_DELAY)

        log.warning(
            "PDF output not found for %s after %d retries (%.1fs total wait)",
            input_filename,
            MAX_OUTPUT_RETRIES,
            total_wait_time,
        )
        return None

    async def convert_to_pdf(
        self,
        input_data: bytes,
        input_filename: str,
    ) -> tuple[bytes, str]:
        """
        Convert a document to PDF.

        Args:
            input_data: The document content as bytes
            input_filename: Original filename (used to determine format)

        Returns:
            Tuple of (pdf_bytes, error_message). If successful, error_message is empty.

        Raises:
            ValueError: If format is not supported or LibreOffice is not available
            RuntimeError: If conversion fails
        """
        pdf_bytes, error = await self.convert_binary_to_pdf(input_data, input_filename)
        
        if error:
            if "not available" in error or "not installed" in error:
                raise ValueError(error)
            raise RuntimeError(error)
        
        return pdf_bytes, ""

    async def convert_base64_to_pdf_base64(
        self,
        input_base64: str,
        input_filename: str,
    ) -> tuple[str, str]:
        """
        Convert a base64-encoded document to base64-encoded PDF.

        Args:
            input_base64: The document content as base64 string
            input_filename: Original filename (used to determine format)

        Returns:
            Tuple of (pdf_base64, error_message). If successful, error_message is empty.
        """
        try:
            # Decode input
            input_data = base64.b64decode(input_base64)

            # Convert
            pdf_bytes, error = await self.convert_binary_to_pdf(input_data, input_filename)

            if error:
                return "", error

            # Encode output
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
            return pdf_base64, ""

        except Exception as e:
            log.exception("Error in base64 conversion: %s", e)
            return "", str(e)


# Singleton instance
_conversion_service: Optional[DocumentConversionService] = None


def get_document_conversion_service(
    libreoffice_path: Optional[str] = None,
    timeout_seconds: int = DEFAULT_CONVERSION_TIMEOUT_SECONDS,
    max_file_size_bytes: int = DEFAULT_MAX_CONVERSION_SIZE_BYTES,
) -> DocumentConversionService:
    """
    Get or create the document conversion service singleton.

    Args:
        libreoffice_path: Optional path to LibreOffice executable
        timeout_seconds: Conversion timeout in seconds (default: 30)
        max_file_size_bytes: Maximum file size allowed for conversion (default: 50MB)

    Returns:
        DocumentConversionService instance
    """
    global _conversion_service
    if _conversion_service is None:
        _conversion_service = DocumentConversionService(
            libreoffice_path=libreoffice_path,
            timeout_seconds=timeout_seconds,
            max_file_size_bytes=max_file_size_bytes,
        )
    return _conversion_service
