"""
Unit tests for DocumentConversionService.

Tests cover:
1. Service initialization and LibreOffice detection
2. Format support checking
3. File size validation
4. Conversion timeout handling
5. Base64 conversion helpers
6. Singleton pattern for service access

Note: The actual LibreOffice conversion is mocked since it 
requires external software installation, but all other logic is tested directly.
"""

import pytest
import asyncio
import base64
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from solace_agent_mesh.gateway.http_sse.services.document_conversion_service import (
    DocumentConversionService,
    get_document_conversion_service,
    DEFAULT_MAX_CONVERSION_SIZE_BYTES,
)


class TestDocumentConversionServiceInitialization:
    """Test service initialization and LibreOffice detection."""

    def test_initialization_with_explicit_path(self):
        """Test initialization with explicit LibreOffice path."""
        service = DocumentConversionService(
            libreoffice_path="/usr/bin/soffice",
            timeout_seconds=30,
            max_file_size_bytes=10 * 1024 * 1024,
        )
        
        assert service.libreoffice_path == "/usr/bin/soffice"
        assert service.timeout_seconds == 30
        assert service.max_file_size_bytes == 10 * 1024 * 1024
        assert service.is_available is True

    def test_initialization_without_libreoffice(self):
        """Test initialization when LibreOffice is not found."""
        with patch.object(DocumentConversionService, '_find_libreoffice', return_value=None):
            service = DocumentConversionService()
            
            assert service.libreoffice_path is None
            assert service.is_available is False

    def test_initialization_default_values(self):
        """Test initialization uses default values."""
        with patch.object(DocumentConversionService, '_find_libreoffice', return_value="/usr/bin/soffice"):
            service = DocumentConversionService()
            
            assert service.timeout_seconds == 60
            assert service.max_file_size_bytes == DEFAULT_MAX_CONVERSION_SIZE_BYTES
            assert service.max_file_size_bytes == 50 * 1024 * 1024  # 50MB

    def test_find_libreoffice_in_path(self):
        """Test finding LibreOffice via shutil.which."""
        with patch('shutil.which') as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/bin/soffice" if cmd == "soffice" else None
            
            service = DocumentConversionService()
            
            assert service.libreoffice_path == "/usr/bin/soffice"
            assert service.is_available is True

    def test_find_libreoffice_alternative_command(self):
        """Test finding LibreOffice via 'libreoffice' command."""
        with patch('shutil.which') as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/bin/libreoffice" if cmd == "libreoffice" else None
            
            service = DocumentConversionService()
            
            assert service.libreoffice_path == "/usr/bin/libreoffice"
            assert service.is_available is True

    def test_find_libreoffice_common_paths(self):
        """Test finding LibreOffice via common installation paths."""
        with patch('shutil.which', return_value=None):
            with patch('os.path.isfile', return_value=True):
                with patch('os.access', return_value=True):
                    service = DocumentConversionService()
                    
                    # Should find in common paths
                    assert service.is_available is True


class TestDocumentConversionServiceFormatSupport:
    """Test format support checking."""

    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        return DocumentConversionService(libreoffice_path="/usr/bin/soffice")

    def test_supported_formats_list(self, service):
        """Test that all expected formats are supported."""
        expected_formats = ["pptx", "ppt", "docx", "doc", "xlsx", "xls", "odt", "odp", "ods"]
        supported = service.get_supported_extensions()
        
        for fmt in expected_formats:
            assert fmt in supported, f"Expected {fmt} to be supported"

    def test_is_format_supported_valid_formats(self, service):
        """Test format support for valid file types."""
        valid_files = [
            "presentation.pptx",
            "presentation.ppt",
            "document.docx",
            "document.doc",
            "spreadsheet.xlsx",
            "spreadsheet.xls",
            "document.odt",
            "presentation.odp",
            "spreadsheet.ods",
        ]
        
        for filename in valid_files:
            assert service.is_format_supported(filename) is True, f"Expected {filename} to be supported"

    def test_is_format_supported_case_insensitive(self, service):
        """Test format support is case insensitive."""
        case_variants = [
            "DOCUMENT.DOCX",
            "Document.Docx",
            "document.DOCX",
            "PRESENTATION.PPTX",
        ]
        
        for filename in case_variants:
            assert service.is_format_supported(filename) is True, f"Expected {filename} to be supported (case insensitive)"

    def test_is_format_supported_invalid_formats(self, service):
        """Test format support for invalid file types."""
        invalid_files = [
            "image.png",
            "image.jpg",
            "video.mp4",
            "audio.mp3",
            "archive.zip",
            "text.txt",
            "script.py",
            "noextension",
            "",
        ]
        
        for filename in invalid_files:
            assert service.is_format_supported(filename) is False, f"Expected {filename} to NOT be supported"

    def test_is_format_supported_with_path(self, service):
        """Test format support with full file paths."""
        path_variants = [
            "/path/to/document.docx",
            "relative/path/presentation.pptx",
            "./local/spreadsheet.xlsx",
            "../parent/document.odt",
        ]
        
        for path in path_variants:
            assert service.is_format_supported(path) is True, f"Expected {path} to be supported"


class TestDocumentConversionServiceSizeValidation:
    """Test file size validation."""

    @pytest.fixture
    def service(self):
        """Create a service instance with small max size for testing."""
        return DocumentConversionService(
            libreoffice_path="/usr/bin/soffice",
            max_file_size_bytes=1024 * 1024,  # 1MB limit
        )

    @pytest.mark.asyncio
    async def test_file_too_large_rejection(self, service):
        """Test that files exceeding max size are rejected."""
        # Create data larger than 1MB limit
        large_data = b"x" * (2 * 1024 * 1024)  # 2MB
        
        with pytest.raises(ValueError) as exc_info:
            await service.convert_to_pdf(large_data, "large_document.docx")
        
        assert "File too large" in str(exc_info.value)
        assert "1MB" in str(exc_info.value)  # Should mention the limit
        assert "2.0MB" in str(exc_info.value)  # Should mention actual size

    @pytest.mark.asyncio
    async def test_file_at_exact_limit_allowed(self, service):
        """Test that files at exactly the limit are allowed (but may fail conversion)."""
        # Create data exactly at limit
        exact_data = b"x" * (1024 * 1024)  # Exactly 1MB
        
        # This should not raise ValueError for size, but may fail on conversion
        # since we don't have actual LibreOffice. We're testing size validation only.
        with patch.object(service, 'convert_to_pdf', wraps=service.convert_to_pdf) as wrapped:
            try:
                await service.convert_to_pdf(exact_data, "exact.docx")
            except (ValueError, RuntimeError) as e:
                # Size validation should pass - if it's a ValueError, it shouldn't be about size
                if isinstance(e, ValueError):
                    assert "File too large" not in str(e)

    @pytest.mark.asyncio
    async def test_file_under_limit_allowed(self, service):
        """Test that files under the limit proceed to conversion."""
        small_data = b"x" * (512 * 1024)  # 512KB - under 1MB limit
        
        # Mock the subprocess to test that we get past size validation
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            # Should not raise ValueError about size
            try:
                await service.convert_to_pdf(small_data, "small.docx")
            except RuntimeError:
                # Expected - conversion will fail without actual output file
                pass


class TestDocumentConversionServiceConversion:
    """Test actual conversion logic."""

    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        return DocumentConversionService(
            libreoffice_path="/usr/bin/soffice",
            timeout_seconds=10,
        )

    @pytest.mark.asyncio
    async def test_convert_unavailable_service(self):
        """Test conversion fails when service is not available."""
        with patch.object(DocumentConversionService, '_find_libreoffice', return_value=None):
            service = DocumentConversionService()
            assert service.is_available is False
            
            with pytest.raises(ValueError) as exc_info:
                await service.convert_to_pdf(b"content", "document.docx")
            
            assert "not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_convert_unsupported_format(self, service):
        """Test conversion fails for unsupported formats."""
        with pytest.raises(ValueError) as exc_info:
            await service.convert_to_pdf(b"content", "image.png")
        
        assert "Unsupported format" in str(exc_info.value)
        assert "png" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_convert_timeout_handling(self, service):
        """Test that conversion timeout is properly handled."""
        test_data = b"test document content"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            # Simulate timeout by making communicate raise TimeoutError
            mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_process.kill = MagicMock()
            mock_process.wait = AsyncMock()
            mock_subprocess.return_value = mock_process
            
            with pytest.raises(RuntimeError) as exc_info:
                await service.convert_to_pdf(test_data, "document.docx")
            
            assert "timed out" in str(exc_info.value)
            mock_process.kill.assert_called_once()
            mock_process.wait.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_convert_libreoffice_error(self, service):
        """Test handling of LibreOffice conversion errors."""
        test_data = b"test document content"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b"Error: could not convert"))
            mock_process.returncode = 1  # Non-zero exit code
            mock_subprocess.return_value = mock_process
            
            with pytest.raises(RuntimeError) as exc_info:
                await service.convert_to_pdf(test_data, "document.docx")
            
            assert "Conversion failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_convert_no_output_file(self, service):
        """Test handling when LibreOffice produces no output file."""
        test_data = b"test document content"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"success", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            # Don't create any output file - service should detect this
            with pytest.raises(RuntimeError) as exc_info:
                await service.convert_to_pdf(test_data, "document.docx")
            
            assert "no PDF output" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_convert_successful(self, service):
        """Test successful conversion produces PDF bytes."""
        test_data = b"test document content"
        expected_pdf = b"%PDF-1.4 test pdf content"
        
        # We need to mock the subprocess and also ensure the output file exists
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            with patch('pathlib.Path.glob') as mock_glob:
                mock_process = AsyncMock()
                mock_process.communicate = AsyncMock(return_value=(b"success", b""))
                mock_process.returncode = 0
                mock_subprocess.return_value = mock_process
                
                # Create a temp file to simulate LibreOffice output
                with tempfile.TemporaryDirectory() as temp_dir:
                    output_path = Path(temp_dir) / "input.pdf"
                    output_path.write_bytes(expected_pdf)
                    
                    mock_glob.return_value = [output_path]
                    
                    # Patch Path.exists to return True for our mock file
                    with patch.object(Path, 'exists', return_value=True):
                        with patch.object(Path, 'read_bytes', return_value=expected_pdf):
                            pdf_bytes, error = await service.convert_to_pdf(test_data, "document.docx")
                            
                            assert error == ""
                            assert pdf_bytes == expected_pdf


class TestDocumentConversionServiceBase64:
    """Test base64 conversion methods."""

    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        return DocumentConversionService(libreoffice_path="/usr/bin/soffice")

    @pytest.mark.asyncio
    async def test_convert_base64_to_pdf_base64_success(self, service):
        """Test successful base64-to-base64 conversion."""
        test_content = b"test document content"
        test_base64 = base64.b64encode(test_content).decode("utf-8")
        expected_pdf = b"%PDF-1.4 test pdf content"
        expected_pdf_base64 = base64.b64encode(expected_pdf).decode("utf-8")
        
        with patch.object(service, 'convert_to_pdf', new_callable=AsyncMock) as mock_convert:
            mock_convert.return_value = (expected_pdf, "")
            
            pdf_base64, error = await service.convert_base64_to_pdf_base64(
                test_base64, "document.docx"
            )
            
            assert error == ""
            assert pdf_base64 == expected_pdf_base64
            mock_convert.assert_called_once()
            # Verify the decoded content was passed
            call_args = mock_convert.call_args
            assert call_args[0][0] == test_content

    @pytest.mark.asyncio
    async def test_convert_base64_to_pdf_base64_conversion_error(self, service):
        """Test base64 conversion when underlying conversion fails."""
        test_content = b"test document content"
        test_base64 = base64.b64encode(test_content).decode("utf-8")
        
        with patch.object(service, 'convert_to_pdf', new_callable=AsyncMock) as mock_convert:
            mock_convert.return_value = (b"", "Conversion failed: timeout")
            
            pdf_base64, error = await service.convert_base64_to_pdf_base64(
                test_base64, "document.docx"
            )
            
            assert pdf_base64 == ""
            assert error == "Conversion failed: timeout"

    @pytest.mark.asyncio
    async def test_convert_base64_to_pdf_base64_invalid_base64(self, service):
        """Test handling of invalid base64 input."""
        invalid_base64 = "not-valid-base64!!!"
        
        pdf_base64, error = await service.convert_base64_to_pdf_base64(
            invalid_base64, "document.docx"
        )
        
        assert pdf_base64 == ""
        assert error != ""  # Should have an error message

    @pytest.mark.asyncio
    async def test_convert_base64_to_pdf_base64_exception_handling(self, service):
        """Test that exceptions are caught and returned as error strings."""
        test_base64 = base64.b64encode(b"content").decode("utf-8")
        
        with patch.object(service, 'convert_to_pdf', new_callable=AsyncMock) as mock_convert:
            mock_convert.side_effect = RuntimeError("Unexpected error")
            
            pdf_base64, error = await service.convert_base64_to_pdf_base64(
                test_base64, "document.docx"
            )
            
            assert pdf_base64 == ""
            assert "Unexpected error" in error


class TestDocumentConversionServiceSingleton:
    """Test singleton pattern for service access."""

    def teardown_method(self):
        """Reset singleton between tests."""
        import solace_agent_mesh.gateway.http_sse.services.document_conversion_service as module
        module._conversion_service = None

    def test_get_document_conversion_service_creates_singleton(self):
        """Test that get_document_conversion_service creates a singleton."""
        with patch.object(DocumentConversionService, '_find_libreoffice', return_value="/usr/bin/soffice"):
            service1 = get_document_conversion_service()
            service2 = get_document_conversion_service()
            
            assert service1 is service2

    def test_get_document_conversion_service_with_custom_params(self):
        """Test that first call's parameters are used."""
        with patch.object(DocumentConversionService, '_find_libreoffice', return_value="/usr/bin/soffice"):
            service = get_document_conversion_service(
                timeout_seconds=120,
                max_file_size_bytes=100 * 1024 * 1024,
            )
            
            assert service.timeout_seconds == 120
            assert service.max_file_size_bytes == 100 * 1024 * 1024

    def test_get_document_conversion_service_subsequent_params_ignored(self):
        """Test that subsequent calls ignore parameters (singleton already created)."""
        with patch.object(DocumentConversionService, '_find_libreoffice', return_value="/usr/bin/soffice"):
            service1 = get_document_conversion_service(timeout_seconds=30)
            service2 = get_document_conversion_service(timeout_seconds=120)
            
            # Second call's parameters should be ignored
            assert service2.timeout_seconds == 30
            assert service1 is service2


class TestDocumentConversionServiceCommandGeneration:
    """Test LibreOffice command generation."""

    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        return DocumentConversionService(libreoffice_path="/usr/bin/soffice")

    @pytest.mark.asyncio
    async def test_conversion_command_includes_required_flags(self, service):
        """Test that the conversion command includes all required LibreOffice flags."""
        test_data = b"test content"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            try:
                await service.convert_to_pdf(test_data, "document.docx")
            except RuntimeError:
                pass  # Expected - no output file
            
            # Verify the command was called with correct arguments
            call_args = mock_subprocess.call_args[0]
            
            assert "/usr/bin/soffice" in call_args
            assert "--headless" in call_args
            assert "--invisible" in call_args
            assert "--nologo" in call_args
            assert "--nofirststartwizard" in call_args
            assert "--convert-to" in call_args
            assert "pdf" in call_args

    @pytest.mark.asyncio
    async def test_conversion_uses_temporary_directory(self, service):
        """Test that conversion uses a temporary directory for file operations."""
        test_data = b"test content"
        
        # Use a real temporary directory but mock the subprocess
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            try:
                await service.convert_to_pdf(test_data, "document.docx")
            except RuntimeError:
                pass  # Expected - no output file
            
            # Verify subprocess was called (meaning temp dir was created successfully)
            mock_subprocess.assert_called_once()
            
            # Verify the command includes expected flags
            call_args = mock_subprocess.call_args[0]
            assert "--headless" in call_args
            assert "--convert-to" in call_args
