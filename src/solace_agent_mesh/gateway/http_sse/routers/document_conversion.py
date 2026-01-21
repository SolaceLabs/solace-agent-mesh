"""
FastAPI router for document conversion endpoints.
Provides PPTX/DOCX to PDF conversion for preview rendering.
"""
from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import get_user_id, ValidatedUserConfig
from ..services.document_conversion_service import get_document_conversion_service

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

router = APIRouter()


class ConversionRequest(BaseModel):
    """Request model for document conversion."""

    content: str = Field(..., description="Base64-encoded document content")
    filename: str = Field(..., description="Original filename with extension")


class ConversionResponse(BaseModel):
    """Response model for document conversion."""

    pdf_content: str = Field(..., alias="pdfContent", description="Base64-encoded PDF content")
    success: bool = Field(..., description="Whether conversion was successful")
    error: str | None = Field(None, description="Error message if conversion failed")

    model_config = {"populate_by_name": True}


class ConversionStatusResponse(BaseModel):
    """Response model for conversion service status."""

    available: bool = Field(..., description="Whether document conversion is available")
    supported_formats: list[str] = Field(
        ..., alias="supportedFormats", description="List of supported file extensions"
    )

    model_config = {"populate_by_name": True}


@router.get(
    "/status",
    response_model=ConversionStatusResponse,
    summary="Check Conversion Service Status",
    description="Check if document conversion service is available and what formats are supported.",
)
async def get_conversion_status():
    """
    Returns the status of the document conversion service.
    This endpoint does not require authentication to allow the frontend
    to check availability before attempting conversion.
    """
    service = get_document_conversion_service()
    return ConversionStatusResponse(
        available=service.is_available,
        supported_formats=service.get_supported_extensions(),
    )


@router.post(
    "/to-pdf",
    response_model=ConversionResponse,
    summary="Convert Document to PDF",
    description="Convert a PPTX, DOCX, or other Office document to PDF for preview.",
)
async def convert_to_pdf(
    request: ConversionRequest,
    user_id: str = Depends(get_user_id),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
):
    """
    Converts a document to PDF format.

    The input document should be base64-encoded. The response will contain
    the converted PDF as a base64-encoded string.

    Supported formats: PPTX, PPT, DOCX, DOC, XLSX, XLS, ODT, ODP, ODS
    """
    log_prefix = f"[DocumentConversion] User={user_id} -"
    log.info("%s Conversion request for: %s", log_prefix, request.filename)

    service = get_document_conversion_service()

    if not service.is_available:
        log.warning("%s Conversion service not available", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document conversion service is not available. LibreOffice is not installed on the server.",
        )

    if not service.is_format_supported(request.filename):
        log.warning("%s Unsupported format: %s", log_prefix, request.filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Supported formats: {', '.join(service.get_supported_extensions())}",
        )

    try:
        # Validate base64 content
        try:
            # Just validate it's valid base64
            base64.b64decode(request.content)
        except Exception as e:
            log.warning("%s Invalid base64 content: %s", log_prefix, e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid base64-encoded content",
            )

        # Perform conversion
        pdf_base64, error = await service.convert_base64_to_pdf_base64(
            request.content,
            request.filename,
        )

        if error:
            log.error("%s Conversion failed: %s", log_prefix, error)
            return ConversionResponse(
                pdf_content="",
                success=False,
                error=error,
            )

        log.info(
            "%s Successfully converted %s to PDF",
            log_prefix,
            request.filename,
        )

        return ConversionResponse(
            pdf_content=pdf_base64,
            success=True,
            error=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        log.exception("%s Unexpected error during conversion: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversion failed: {str(e)}",
        )
