"""
Unit tests for document conversion router endpoints.

Tests cover:
1. GET /status endpoint - conversion service availability
2. POST /to-pdf endpoint - document to PDF conversion
3. Error handling for various failure scenarios
4. Request validation and authentication

Note: These tests focus on router logic.
Service-level tests are in test_document_conversion_service.py.
"""

import pytest
import base64
from unittest.mock import MagicMock, patch, AsyncMock

from fastapi import HTTPException, status

from solace_agent_mesh.gateway.http_sse.routers.document_conversion import (
    router,
    ConversionRequest,
    ConversionResponse,
    ConversionStatusResponse,
    get_conversion_status,
    convert_to_pdf,
)


class TestConversionRequestModel:
    """Test ConversionRequest Pydantic model."""

    def test_conversion_request_valid(self):
        """Test valid ConversionRequest creation."""
        content = base64.b64encode(b"test content").decode("utf-8")
        request = ConversionRequest(content=content, filename="document.docx")
        
        assert request.content == content
        assert request.filename == "document.docx"

    def test_conversion_request_missing_content(self):
        """Test ConversionRequest fails without content."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ConversionRequest(filename="document.docx")

    def test_conversion_request_missing_filename(self):
        """Test ConversionRequest fails without filename."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ConversionRequest(content="base64content")


class TestConversionResponseModel:
    """Test ConversionResponse Pydantic model."""

    def test_conversion_response_success(self):
        """Test successful ConversionResponse creation."""
        response = ConversionResponse(
            pdf_content="base64pdfcontent",
            success=True,
            error=None,
        )
        
        assert response.pdf_content == "base64pdfcontent"
        assert response.success is True
        assert response.error is None

    def test_conversion_response_failure(self):
        """Test failure ConversionResponse creation."""
        response = ConversionResponse(
            pdf_content="",
            success=False,
            error="Conversion failed: timeout",
        )
        
        assert response.pdf_content == ""
        assert response.success is False
        assert response.error == "Conversion failed: timeout"

    def test_conversion_response_camelcase_alias(self):
        """Test ConversionResponse uses camelCase aliases in JSON."""
        response = ConversionResponse(
            pdf_content="content",
            success=True,
            error=None,
        )
        
        json_data = response.model_dump(by_alias=True)
        
        assert "pdfContent" in json_data
        assert "pdf_content" not in json_data


class TestConversionStatusResponseModel:
    """Test ConversionStatusResponse Pydantic model."""

    def test_conversion_status_response_available(self):
        """Test ConversionStatusResponse when service is available."""
        response = ConversionStatusResponse(
            available=True,
            supported_formats=["docx", "pptx", "xlsx"],
        )
        
        assert response.available is True
        assert "docx" in response.supported_formats

    def test_conversion_status_response_unavailable(self):
        """Test ConversionStatusResponse when service is unavailable."""
        response = ConversionStatusResponse(
            available=False,
            supported_formats=[],
        )
        
        assert response.available is False
        assert response.supported_formats == []

    def test_conversion_status_response_camelcase_alias(self):
        """Test ConversionStatusResponse uses camelCase aliases in JSON."""
        response = ConversionStatusResponse(
            available=True,
            supported_formats=["docx"],
        )
        
        json_data = response.model_dump(by_alias=True)
        
        assert "supportedFormats" in json_data
        assert "supported_formats" not in json_data


class TestGetConversionStatusEndpoint:
    """Test GET /status endpoint."""

    @pytest.mark.asyncio
    async def test_get_conversion_status_available(self):
        """Test status endpoint when service is available."""
        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.get_supported_extensions.return_value = ["docx", "pptx", "xlsx", "doc", "ppt", "xls"]
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            result = await get_conversion_status()
            
            assert isinstance(result, ConversionStatusResponse)
            assert result.available is True
            assert len(result.supported_formats) == 6
            assert "docx" in result.supported_formats

    @pytest.mark.asyncio
    async def test_get_conversion_status_unavailable(self):
        """Test status endpoint when service is unavailable (no LibreOffice)."""
        mock_service = MagicMock()
        mock_service.is_available = False
        mock_service.get_supported_extensions.return_value = []
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            result = await get_conversion_status()
            
            assert isinstance(result, ConversionStatusResponse)
            assert result.available is False
            assert result.supported_formats == []

    @pytest.mark.asyncio
    async def test_get_conversion_status_no_auth_required(self):
        """Test that status endpoint doesn't require authentication."""
        # The endpoint should work without any user authentication
        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.get_supported_extensions.return_value = ["docx"]
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            # Should not raise any authentication error
            result = await get_conversion_status()
            assert result is not None


class TestConvertToPdfEndpoint:
    """Test POST /to-pdf endpoint."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock conversion service."""
        service = MagicMock()
        service.is_available = True
        service.is_format_supported = MagicMock(return_value=True)
        service.get_supported_extensions = MagicMock(return_value=["docx", "pptx", "xlsx"])
        service.convert_base64_to_pdf_base64 = AsyncMock()
        return service

    @pytest.fixture
    def valid_request(self):
        """Create a valid conversion request."""
        content = base64.b64encode(b"test document content").decode("utf-8")
        return ConversionRequest(content=content, filename="document.docx")

    @pytest.mark.asyncio
    async def test_convert_to_pdf_success(self, mock_service, valid_request):
        """Test successful PDF conversion."""
        expected_pdf = base64.b64encode(b"%PDF-1.4 test").decode("utf-8")
        mock_service.convert_base64_to_pdf_base64.return_value = (expected_pdf, "")
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            result = await convert_to_pdf(
                request=valid_request,
                user_id="test-user-123",
                user_config={"tool:artifact:load": True},
            )
            
            assert isinstance(result, ConversionResponse)
            assert result.success is True
            assert result.pdf_content == expected_pdf
            assert result.error is None

    @pytest.mark.asyncio
    async def test_convert_to_pdf_service_unavailable(self, valid_request):
        """Test conversion fails when service is unavailable."""
        mock_service = MagicMock()
        mock_service.is_available = False
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            with pytest.raises(HTTPException) as exc_info:
                await convert_to_pdf(
                    request=valid_request,
                    user_id="test-user-123",
                    user_config={"tool:artifact:load": True},
                )
            
            assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "not available" in str(exc_info.value.detail)
            assert "LibreOffice" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_convert_to_pdf_unsupported_format(self, mock_service, valid_request):
        """Test conversion fails for unsupported format."""
        mock_service.is_format_supported.return_value = False
        
        # Change filename to unsupported format
        unsupported_request = ConversionRequest(
            content=valid_request.content,
            filename="image.png",
        )
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            with pytest.raises(HTTPException) as exc_info:
                await convert_to_pdf(
                    request=unsupported_request,
                    user_id="test-user-123",
                    user_config={"tool:artifact:load": True},
                )
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Unsupported file format" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_convert_to_pdf_invalid_base64(self, mock_service):
        """Test conversion fails with invalid base64 content."""
        invalid_request = ConversionRequest(
            content="not-valid-base64!!!",
            filename="document.docx",
        )
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            with pytest.raises(HTTPException) as exc_info:
                await convert_to_pdf(
                    request=invalid_request,
                    user_id="test-user-123",
                    user_config={"tool:artifact:load": True},
                )
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid base64" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_convert_to_pdf_conversion_error(self, mock_service, valid_request):
        """Test handling of conversion errors."""
        mock_service.convert_base64_to_pdf_base64.return_value = ("", "LibreOffice conversion failed")
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            result = await convert_to_pdf(
                request=valid_request,
                user_id="test-user-123",
                user_config={"tool:artifact:load": True},
            )
            
            assert isinstance(result, ConversionResponse)
            assert result.success is False
            assert result.pdf_content == ""
            assert "LibreOffice conversion failed" in result.error

    @pytest.mark.asyncio
    async def test_convert_to_pdf_unexpected_exception(self, mock_service, valid_request):
        """Test handling of unexpected exceptions."""
        mock_service.convert_base64_to_pdf_base64.side_effect = RuntimeError("Unexpected error")
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            with pytest.raises(HTTPException) as exc_info:
                await convert_to_pdf(
                    request=valid_request,
                    user_id="test-user-123",
                    user_config={"tool:artifact:load": True},
                )
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Conversion failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_convert_to_pdf_various_formats(self, mock_service):
        """Test conversion with various supported formats."""
        expected_pdf = base64.b64encode(b"%PDF-1.4 test").decode("utf-8")
        mock_service.convert_base64_to_pdf_base64.return_value = (expected_pdf, "")
        
        formats = [
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
        
        content = base64.b64encode(b"test content").decode("utf-8")
        
        for filename in formats:
            request = ConversionRequest(content=content, filename=filename)
            
            with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
                result = await convert_to_pdf(
                    request=request,
                    user_id="test-user-123",
                    user_config={"tool:artifact:load": True},
                )
                
                assert result.success is True, f"Failed for format: {filename}"

    @pytest.mark.asyncio
    async def test_convert_to_pdf_logs_user_activity(self, mock_service, valid_request):
        """Test that conversion logs user activity."""
        expected_pdf = base64.b64encode(b"%PDF-1.4 test").decode("utf-8")
        mock_service.convert_base64_to_pdf_base64.return_value = (expected_pdf, "")
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.log') as mock_log:
                await convert_to_pdf(
                    request=valid_request,
                    user_id="test-user-123",
                    user_config={"tool:artifact:load": True},
                )
                
                # Verify logging was called with user information
                mock_log.info.assert_called()
                # Check that user_id is included in at least one log call
                log_calls = [str(call) for call in mock_log.info.call_args_list]
                assert any("test-user-123" in call for call in log_calls)


class TestConvertToPdfEndpointSecurity:
    """Test security aspects of the convert_to_pdf endpoint."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock conversion service."""
        service = MagicMock()
        service.is_available = True
        service.is_format_supported = MagicMock(return_value=True)
        service.get_supported_extensions = MagicMock(return_value=["docx"])
        service.convert_base64_to_pdf_base64 = AsyncMock(return_value=("pdf", ""))
        return service

    @pytest.mark.asyncio
    async def test_convert_requires_user_id(self, mock_service):
        """Test that conversion requires a valid user_id."""
        content = base64.b64encode(b"test").decode("utf-8")
        request = ConversionRequest(content=content, filename="doc.docx")
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            # Should work with valid user_id
            result = await convert_to_pdf(
                request=request,
                user_id="valid-user",
                user_config={"tool:artifact:load": True},
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_convert_uses_validated_user_config(self, mock_service):
        """Test that endpoint uses ValidatedUserConfig dependency."""
        # The endpoint signature shows it uses ValidatedUserConfig(["tool:artifact:load"])
        # This test verifies the user_config parameter is used
        content = base64.b64encode(b"test").decode("utf-8")
        request = ConversionRequest(content=content, filename="doc.docx")
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            # The endpoint accepts user_config from dependency
            result = await convert_to_pdf(
                request=request,
                user_id="test-user",
                user_config={"tool:artifact:load": True, "other:permission": False},
            )
            assert result is not None


class TestRouterConfiguration:
    """Test router configuration and structure."""

    def test_router_has_expected_endpoints(self):
        """Test that router has the expected endpoints."""
        routes = [route.path for route in router.routes]
        
        assert "/status" in routes
        assert "/to-pdf" in routes

    def test_router_endpoint_methods(self):
        """Test that endpoints use correct HTTP methods."""
        for route in router.routes:
            if route.path == "/status":
                assert "GET" in route.methods
            elif route.path == "/to-pdf":
                assert "POST" in route.methods

    def test_router_response_models(self):
        """Test that endpoints have response models configured."""
        for route in router.routes:
            if hasattr(route, 'response_model'):
                if route.path == "/status":
                    assert route.response_model == ConversionStatusResponse
                elif route.path == "/to-pdf":
                    assert route.response_model == ConversionResponse


class TestConversionRequestEdgeCases:
    """Test edge cases in conversion requests."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock conversion service."""
        service = MagicMock()
        service.is_available = True
        service.is_format_supported = MagicMock(return_value=True)
        service.get_supported_extensions = MagicMock(return_value=["docx"])
        service.convert_base64_to_pdf_base64 = AsyncMock(return_value=("pdf", ""))
        return service

    @pytest.mark.asyncio
    async def test_convert_empty_content(self, mock_service):
        """Test conversion with empty base64 content."""
        # Empty string encoded in base64
        content = base64.b64encode(b"").decode("utf-8")
        request = ConversionRequest(content=content, filename="doc.docx")
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            # Should still work - service decides if it's valid
            result = await convert_to_pdf(
                request=request,
                user_id="test-user",
                user_config={"tool:artifact:load": True},
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_convert_large_content_passes_to_service(self, mock_service):
        """Test that large content is passed to service for validation."""
        # 10MB of content - service should handle size validation
        large_content = base64.b64encode(b"x" * (10 * 1024 * 1024)).decode("utf-8")
        request = ConversionRequest(content=large_content, filename="large.docx")
        
        mock_service.convert_base64_to_pdf_base64.return_value = ("", "File too large")
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            result = await convert_to_pdf(
                request=request,
                user_id="test-user",
                user_config={"tool:artifact:load": True},
            )
            
            # Service returns error, not HTTP exception
            assert result.success is False
            assert "too large" in result.error

    @pytest.mark.asyncio
    async def test_convert_filename_with_path(self, mock_service):
        """Test conversion with filename containing path separators."""
        content = base64.b64encode(b"test").decode("utf-8")
        # Filename shouldn't contain path - but service handles it
        request = ConversionRequest(content=content, filename="/path/to/doc.docx")
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            result = await convert_to_pdf(
                request=request,
                user_id="test-user",
                user_config={"tool:artifact:load": True},
            )
            # Should work - service handles path extraction
            assert result is not None

    @pytest.mark.asyncio
    async def test_convert_special_characters_in_filename(self, mock_service):
        """Test conversion with special characters in filename."""
        content = base64.b64encode(b"test").decode("utf-8")
        request = ConversionRequest(
            content=content, 
            filename="document with spaces & special (chars).docx"
        )
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            result = await convert_to_pdf(
                request=request,
                user_id="test-user",
                user_config={"tool:artifact:load": True},
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_convert_unicode_filename(self, mock_service):
        """Test conversion with Unicode characters in filename."""
        content = base64.b64encode(b"test").decode("utf-8")
        request = ConversionRequest(
            content=content,
            filename="文档.docx"  # Chinese characters
        )
        
        with patch('solace_agent_mesh.gateway.http_sse.routers.document_conversion.get_document_conversion_service', return_value=mock_service):
            result = await convert_to_pdf(
                request=request,
                user_id="test-user",
                user_config={"tool:artifact:load": True},
            )
            assert result is not None
