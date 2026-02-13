"""Unit tests for file converter service."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from io import BytesIO

from solace_agent_mesh.gateway.http_sse.services.file_converter_service import (
    create_line_range_citations,
    convert_pdf_to_text,
    convert_docx_to_text,
    convert_pptx_to_text,
    should_convert_file,
    convert_and_save_artifact,
    LINES_PER_CITATION_CHUNK,
)


class TestCreateLineRangeCitations:
    """Tests for line-range citation creation for text files."""

    def test_empty_text_creates_empty_citations(self):
        """Test that empty text produces empty citation map."""
        metadata = create_line_range_citations("", lines_per_chunk=50)

        assert metadata["citation_type"] == "line_range"
        assert metadata["line_count"] == 0
        assert metadata["char_count"] == 0
        assert len(metadata["citation_map"]) == 0

    def test_single_chunk_text(self):
        """Test text with less than lines_per_chunk creates single citation."""
        # 30 lines (less than default 50)
        text = "\n".join([f"line {i}" for i in range(30)])

        metadata = create_line_range_citations(text, lines_per_chunk=50)

        assert metadata["line_count"] == 30
        assert len(metadata["citation_map"]) == 1
        assert metadata["citation_map"][0]["location"] == "lines_1_30"

    def test_multiple_chunk_text(self):
        """Test text with multiple chunks creates multiple citations."""
        # 120 lines (3 chunks of 50)
        text = "\n".join([f"line {i}" for i in range(120)])

        metadata = create_line_range_citations(text, lines_per_chunk=50)

        assert metadata["line_count"] == 120
        assert len(metadata["citation_map"]) == 3

        # First chunk: lines 1-50
        assert metadata["citation_map"][0]["location"] == "lines_1_50"
        # Second chunk: lines 51-100
        assert metadata["citation_map"][1]["location"] == "lines_51_100"
        # Third chunk: lines 101-120
        assert metadata["citation_map"][2]["location"] == "lines_101_120"

    def test_char_positions_are_accurate(self):
        """Test that character positions in citation map are accurate."""
        lines = ["abc", "def", "ghi"]
        text = "\n".join(lines)  # "abc\ndef\nghi"

        metadata = create_line_range_citations(text, lines_per_chunk=2)

        # First chunk: "abc\ndef" (chars 0-7)
        assert metadata["citation_map"][0]["char_start"] == 0
        assert metadata["citation_map"][0]["char_end"] == 7

        # Second chunk: "ghi" (chars 8-10)
        assert metadata["citation_map"][1]["char_start"] == 8
        assert metadata["citation_map"][1]["char_end"] == 11


class TestConvertPdfToText:
    """Tests for PDF to text conversion."""

    def test_pdf_conversion_extracts_text(self):
        """Test that PDF text extraction works."""
        # Mock PDF with 2 pages
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 content"

        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 content"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page1, mock_page2]

        with patch('pypdf.PdfReader') as mock_pdf_reader:
            mock_pdf_reader.return_value = mock_reader

            text, metadata = convert_pdf_to_text(b"fake pdf bytes")

            assert "Page 1 content" in text
            assert "Page 2 content" in text
            assert metadata["converter"] == "pypdf"
            assert metadata["page_count"] == 2
            assert metadata["citation_type"] == "page"

    def test_pdf_citation_map_created(self):
        """Test that PDF conversion creates citation map."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Test content"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch('pypdf.PdfReader') as mock_pdf_reader:
            mock_pdf_reader.return_value = mock_reader

            text, metadata = convert_pdf_to_text(b"pdf bytes")

            # Should have citation for page 1
            assert len(metadata["citation_map"]) == 1
            assert metadata["citation_map"][0]["location"] == "physical_page_1"
            assert metadata["citation_map"][0]["char_start"] == 0

    def test_pdf_multiple_pages_citation_positions(self):
        """Test that multi-page PDF has correct citation positions."""
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "First"  # 5 chars

        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Second"  # 6 chars

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page1, mock_page2]

        with patch('pypdf.PdfReader') as mock_pdf_reader:
            mock_pdf_reader.return_value = mock_reader

            text, metadata = convert_pdf_to_text(b"pdf bytes")

            # Page 1: chars 0-5
            assert metadata["citation_map"][0]["char_start"] == 0
            assert metadata["citation_map"][0]["char_end"] == 5

            # Page 2: chars 6-12 (5 + 1 for newline + 6)
            assert metadata["citation_map"][1]["char_start"] == 6
            # Last page should end at exact text length
            assert metadata["citation_map"][1]["char_end"] == len(text)

    def test_pdf_conversion_error_handling(self):
        """Test that PDF conversion errors are handled."""
        with patch('pypdf.PdfReader') as mock_pdf_reader:
            mock_pdf_reader.side_effect = Exception("Corrupted PDF")

            with pytest.raises(ValueError, match="Failed to convert PDF"):
                convert_pdf_to_text(b"bad pdf")


class TestConvertDocxToText:
    """Tests for DOCX to text conversion."""

    def test_docx_conversion_extracts_paragraphs(self):
        """Test that DOCX paragraph extraction works."""
        mock_para1 = MagicMock()
        mock_para1.text = "Paragraph 1"

        mock_para2 = MagicMock()
        mock_para2.text = "Paragraph 2"

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2]

        with patch('docx.Document') as mock_document:
            mock_document.return_value = mock_doc

            text, metadata = convert_docx_to_text(b"fake docx bytes")

            assert "Paragraph 1" in text
            assert "Paragraph 2" in text
            assert metadata["converter"] == "python-docx"
            assert metadata["citation_type"] == "paragraph"

    def test_docx_skips_empty_paragraphs(self):
        """Test that empty paragraphs are skipped."""
        mock_para1 = MagicMock()
        mock_para1.text = "Content"

        mock_para2 = MagicMock()
        mock_para2.text = "   "  # Whitespace only

        mock_para3 = MagicMock()
        mock_para3.text = "More content"

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]

        with patch('docx.Document') as mock_document:
            mock_document.return_value = mock_doc

            text, metadata = convert_docx_to_text(b"docx bytes")

            # Only 2 non-empty paragraphs in citation map
            assert len(metadata["citation_map"]) == 2
            assert metadata["citation_map"][0]["location"] == "physical_paragraph_1"
            assert metadata["citation_map"][1]["location"] == "physical_paragraph_3"

    def test_docx_citation_positions(self):
        """Test that DOCX citation positions are correct."""
        mock_para1 = MagicMock()
        mock_para1.text = "ABC"

        mock_para2 = MagicMock()
        mock_para2.text = "DEF"

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2]

        with patch('docx.Document') as mock_document:
            mock_document.return_value = mock_doc

            text, metadata = convert_docx_to_text(b"docx bytes")

            # Para 1: chars 0-3
            assert metadata["citation_map"][0]["char_start"] == 0
            assert metadata["citation_map"][0]["char_end"] == 3

            # Para 2: chars 4-7 (3 + 1 for newline + 3)
            assert metadata["citation_map"][1]["char_start"] == 4
            assert metadata["citation_map"][1]["char_end"] == len(text)


class TestConvertPptxToText:
    """Tests for PPTX to text conversion."""

    def test_pptx_conversion_extracts_slides(self):
        """Test that PPTX slide extraction works."""
        mock_shape1 = MagicMock()
        mock_shape1.text = "Slide 1 title"

        mock_shape2 = MagicMock()
        mock_shape2.text = "Slide 1 content"

        mock_slide1 = MagicMock()
        mock_slide1.shapes = [mock_shape1, mock_shape2]

        mock_shape3 = MagicMock()
        mock_shape3.text = "Slide 2 content"

        mock_slide2 = MagicMock()
        mock_slide2.shapes = [mock_shape3]

        mock_prs = MagicMock()
        mock_prs.slides = [mock_slide1, mock_slide2]

        with patch('pptx.Presentation') as mock_presentation:
            mock_presentation.return_value = mock_prs

            text, metadata = convert_pptx_to_text(b"fake pptx bytes")

            assert "Slide 1 title" in text
            assert "Slide 1 content" in text
            assert "Slide 2 content" in text
            assert metadata["converter"] == "python-pptx"
            assert metadata["citation_type"] == "slide"
            assert metadata["slide_count"] == 2

    def test_pptx_citation_map_created(self):
        """Test that PPTX conversion creates citation map."""
        mock_shape = MagicMock()
        mock_shape.text = "Test"

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape]

        mock_prs = MagicMock()
        mock_prs.slides = [mock_slide]

        with patch('pptx.Presentation') as mock_presentation:
            mock_presentation.return_value = mock_prs

            text, metadata = convert_pptx_to_text(b"pptx bytes")

            assert len(metadata["citation_map"]) == 1
            assert metadata["citation_map"][0]["location"] == "physical_slide_1"

    def test_pptx_uses_double_newlines(self):
        """Test that PPTX uses double newlines between slides."""
        mock_shape1 = MagicMock()
        mock_shape1.text = "Slide1"

        mock_slide1 = MagicMock()
        mock_slide1.shapes = [mock_shape1]

        mock_shape2 = MagicMock()
        mock_shape2.text = "Slide2"

        mock_slide2 = MagicMock()
        mock_slide2.shapes = [mock_shape2]

        mock_prs = MagicMock()
        mock_prs.slides = [mock_slide1, mock_slide2]

        with patch('pptx.Presentation') as mock_presentation:
            mock_presentation.return_value = mock_prs

            text, metadata = convert_pptx_to_text(b"pptx bytes")

            # Should have double newline separator
            assert "Slide1\n\nSlide2" in text


class TestShouldConvertFile:
    """Tests for file conversion decision logic."""

    def test_pdf_should_convert(self):
        """Test that PDF files should be converted."""
        assert should_convert_file("application/pdf", "doc.pdf") is True

    def test_docx_should_convert(self):
        """Test that DOCX files should be converted."""
        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert should_convert_file(mime_type, "doc.docx") is True

    def test_pptx_should_convert(self):
        """Test that PPTX files should be converted."""
        mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        assert should_convert_file(mime_type, "slides.pptx") is True

    def test_text_file_should_not_convert(self):
        """Test that text files should not be converted."""
        assert should_convert_file("text/plain", "doc.txt") is False

    def test_image_should_not_convert(self):
        """Test that images should not be converted."""
        assert should_convert_file("image/png", "photo.png") is False

    def test_empty_mime_type(self):
        """Test that empty MIME type returns False."""
        assert should_convert_file("", "file.dat") is False


class TestConvertAndSaveArtifact:
    """Tests for the full conversion and save workflow."""

    @pytest.mark.asyncio
    async def test_skip_non_convertible_files(self):
        """Test that non-convertible files are skipped."""
        result = await convert_and_save_artifact(
            AsyncMock(),
            "app",
            "user",
            "session",
            "image.png",
            1,
            "image/png"
        )

        assert result["status"] == "skipped"
        assert "not supported" in result["reason"]

    @pytest.mark.asyncio
    async def test_pdf_conversion_and_save_success(self):
        """Test successful PDF conversion and save."""
        mock_artifact_service = AsyncMock()

        # Mock source file load
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load:
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": b"fake pdf content"
            }

            # Mock PDF converter
            with patch('solace_agent_mesh.gateway.http_sse.services.file_converter_service.convert_pdf_to_text') as mock_convert:
                mock_convert.return_value = (
                    "Extracted text",
                    {
                        "converter": "pypdf",
                        "page_count": 1,
                        "char_count": 14,
                        "citation_type": "page",
                        "citation_map": []
                    }
                )

                # Mock save
                with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata') as mock_save:
                    mock_save.return_value = {
                        "status": "success",
                        "data_version": 1
                    }

                    result = await convert_and_save_artifact(
                        mock_artifact_service,
                        "app",
                        "user",
                        "session",
                        "doc.pdf",
                        1,
                        "application/pdf"
                    )

                    assert result["status"] == "success"
                    assert result["data_version"] == 1

                    # Verify save was called with correct filename
                    mock_save.assert_called_once()
                    call_args = mock_save.call_args
                    assert call_args[1]["filename"] == "doc.pdf.converted.txt"
                    assert call_args[1]["mime_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_conversion_preserves_source_metadata(self):
        """Test that conversion preserves source file metadata."""
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load:
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": b"pdf"
            }

            with patch('solace_agent_mesh.gateway.http_sse.services.file_converter_service.convert_pdf_to_text') as mock_convert:
                mock_convert.return_value = (
                    "Text",
                    {
                        "converter": "pypdf",
                        "page_count": 1,
                        "char_count": 4,
                        "citation_type": "page",
                        "citation_map": [{"location": "physical_page_1"}]
                    }
                )

                with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata') as mock_save:
                    mock_save.return_value = {"status": "success", "data_version": 2}

                    await convert_and_save_artifact(
                        AsyncMock(),
                        "app",
                        "user",
                        "session",
                        "report.pdf",
                        2,
                        "application/pdf"
                    )

                    # Verify metadata includes source info
                    call_args = mock_save.call_args
                    metadata = call_args[1]["metadata_dict"]

                    assert metadata["source"] == "conversion"
                    assert "conversion" in metadata
                    assert metadata["conversion"]["source_file"] == "report.pdf"
                    assert metadata["conversion"]["source_version"] == 2
                    assert metadata["conversion"]["citation_type"] == "page"

    @pytest.mark.asyncio
    async def test_conversion_error_handling(self):
        """Test that conversion errors are handled properly."""
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load:
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": b"bad pdf"
            }

            with patch('solace_agent_mesh.gateway.http_sse.services.file_converter_service.convert_pdf_to_text') as mock_convert:
                mock_convert.side_effect = ValueError("Corrupted PDF")

                result = await convert_and_save_artifact(
                    AsyncMock(),
                    "app",
                    "user",
                    "session",
                    "bad.pdf",
                    1,
                    "application/pdf"
                )

                assert result["status"] == "error"
                assert "Corrupted PDF" in result["error"]

    @pytest.mark.asyncio
    async def test_source_file_not_found(self):
        """Test handling when source file cannot be loaded."""
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load:
            mock_load.return_value = {
                "status": "error",
                "message": "File not found"
            }

            result = await convert_and_save_artifact(
                AsyncMock(),
                "app",
                "user",
                "session",
                "missing.pdf",
                1,
                "application/pdf"
            )

            assert result["status"] == "error"
            assert "Failed to load source file" in result["error"]
