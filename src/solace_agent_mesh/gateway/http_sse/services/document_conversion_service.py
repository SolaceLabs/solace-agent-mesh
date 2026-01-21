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
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


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

    def __init__(self, libreoffice_path: Optional[str] = None, timeout_seconds: int = 60):
        """
        Initialize the document conversion service.

        Args:
            libreoffice_path: Path to LibreOffice executable. If None, will search common locations.
            timeout_seconds: Maximum time to wait for conversion (default: 60 seconds)
        """
        self.timeout_seconds = timeout_seconds
        self.libreoffice_path = libreoffice_path or self._find_libreoffice()
        self._available = self.libreoffice_path is not None

        if self._available:
            log.info(
                "DocumentConversionService initialized with LibreOffice at: %s",
                self.libreoffice_path,
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
        if not self._available:
            raise ValueError(
                "Document conversion is not available. LibreOffice is not installed."
            )

        ext = Path(input_filename).suffix.lower().lstrip(".")
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {ext}. Supported formats: {', '.join(self.SUPPORTED_FORMATS.keys())}"
            )

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

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    raise RuntimeError(
                        f"Conversion timed out after {self.timeout_seconds} seconds"
                    )

                if process.returncode != 0:
                    error_msg = stderr.decode("utf-8", errors="replace")
                    log.error(
                        "LibreOffice conversion failed (exit code %d): %s",
                        process.returncode,
                        error_msg,
                    )
                    raise RuntimeError(f"Conversion failed: {error_msg}")

                # Find the output PDF file
                # LibreOffice may take a moment to write the file, so we retry a few times
                output_path = None
                for attempt in range(5):
                    candidate_path = temp_dir_path / "input.pdf"
                    if candidate_path.exists():
                        output_path = candidate_path
                        break
                    # Sometimes LibreOffice uses the original filename
                    possible_outputs = list(temp_dir_path.glob("*.pdf"))
                    if possible_outputs:
                        output_path = possible_outputs[0]
                        break
                    # Wait a bit before retrying
                    if attempt < 4:
                        await asyncio.sleep(0.2)

                if output_path is None:
                    raise RuntimeError(
                        "Conversion completed but no PDF output was generated"
                    )

                # Read the PDF content
                pdf_bytes = output_path.read_bytes()

                log.info(
                    "Successfully converted %s to PDF (output size: %d bytes)",
                    input_filename,
                    len(pdf_bytes),
                )

                return pdf_bytes, ""

            except RuntimeError:
                raise
            except Exception as e:
                log.exception("Unexpected error during document conversion: %s", e)
                raise RuntimeError(f"Conversion failed: {str(e)}")

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
            pdf_bytes, error = await self.convert_to_pdf(input_data, input_filename)

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
    timeout_seconds: int = 60,
) -> DocumentConversionService:
    """
    Get or create the document conversion service singleton.

    Args:
        libreoffice_path: Optional path to LibreOffice executable
        timeout_seconds: Conversion timeout in seconds

    Returns:
        DocumentConversionService instance
    """
    global _conversion_service
    if _conversion_service is None:
        _conversion_service = DocumentConversionService(
            libreoffice_path=libreoffice_path,
            timeout_seconds=timeout_seconds,
        )
    return _conversion_service
